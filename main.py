import os
import re
import pathlib
from typing import List, Dict, Optional, TypedDict
from dotenv import load_dotenv

# LangChain & Google Gemini
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain

# Document loaders & processing
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Graph
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing import Literal


# 1. Carregar variáveis de ambiente
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 2. Configurar LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    api_key=GOOGLE_API_KEY
)

# 3. Prompt de triagem
TRIAGEM_PROMPT = (
    "Você é um triador de Service Desk para políticas internas da empresa Carraro Desenvolvimento. "
    "Dada a mensagem do usuário, retorne SOMENTE um JSON com:\n"
    "{\n"
    '  "decisao": "AUTO_RESOLVER" | "PEDIR_INFO" | "ABRIR_CHAMADO",\n'
    '  "urgencia": "BAIXA" | "MEDIA" | "ALTA",\n'
    '  "campos_faltantes": ["..."]\n'
    "}\n"
    "Regras:\n"
    '- **AUTO_RESOLVER**: Perguntas claras sobre regras ou procedimentos descritos nas políticas.\n'
    '- **PEDIR_INFO**: Mensagens vagas ou que faltam informações.\n'
    '- **ABRIR_CHAMADO**: Pedidos de exceção, liberação ou abertura explícita de chamado.\n'
)

# 4. Saída estruturada
class TriagemOut(BaseModel):
    decisao: Literal['AUTO_RESOLVER', 'PEDIR_INFO', 'ABRIR_CHAMADO']
    urgencia: Literal['BAIXA', 'MEDIA', 'ALTA']
    campos_faltantes: List[str] = Field(default_factory=list)

llm_triagem = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    api_key=GOOGLE_API_KEY
)
triagem_chain = llm_triagem.with_structured_output(TriagemOut)

def triagem(mensagem: str) -> Dict:
    saida: TriagemOut = triagem_chain.invoke([
        SystemMessage(content=TRIAGEM_PROMPT),
        HumanMessage(content=mensagem)
    ])
    return saida.model_dump()

# 5. Carregar documentos PDF
docs = []
for n in Path("assets/docs/").glob("*.pdf"):
    try:
        loader = PyMuPDFLoader(str(n))
        docs.extend(loader.load())
        print(f'📄 Arquivo "{n.name}" carregado com sucesso!')
    except:
        print(f'❌ Erro ao carregar: {n.name}')

print(f"Total de documentos carregados: {len(docs)}")

# 6. Criar Chunks + Embeddings
splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
chunks = splitter.split_documents(docs)

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GOOGLE_API_KEY
)

vectorstores = FAISS.from_documents(chunks, embeddings)
retriever = vectorstores.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.3, "k": 4}
)

# 7. Prompt RAG
prompt_rag = ChatPromptTemplate.from_messages([
    ("system", "Você é um Assistente de Políticas Internas (RH/IT). "
               "Responda SOMENTE com base no contexto fornecido. "
               "Se não houver base suficiente, responda apenas 'Não sei'."),
    ("human", "Pergunta: {input}\n\nContexto:\n{context}")
])
document_chain = create_stuff_documents_chain(llm_triagem, prompt_rag)

# 8. Funções auxiliares
def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def extrair_trecho(texto: str, query: str, janela: int = 240) -> str:
    txt = _clean_text(texto)
    termos = [t.lower() for t in re.findall(r"\w+", query or "") if len(t) >= 4]
    pos = -1
    for t in termos:
        pos = txt.lower().find(t)
        if pos != -1: break
    if pos == -1: pos = 0
    ini, fim = max(0, pos - janela//2), min(len(txt), pos + janela//2)
    return txt[ini:fim]

def formatar_citacoes(docs_rel: List, query: str) -> List[Dict]:
    cites, seen = [], set()
    for d in docs_rel:
        src = pathlib.Path(d.metadata.get("source","")).name
        page = int(d.metadata.get("page", 0)) + 1
        key = (src, page)
        if key in seen:
            continue
        seen.add(key)
        cites.append({
            "documento": src,
            "pagina": page,
            "trecho": extrair_trecho(d.page_content, query)
        })
    return cites[:3]

def perguntar_politica_RAG(pergunta: str) -> Dict:
    docs_relacionados = retriever.invoke(pergunta)
    if not docs_relacionados:
        return {"answer": "Não sei.", "citacoes": [], "contexto_encontrado": False}

    answer = document_chain.invoke({"input": pergunta, "context": docs_relacionados})
    txt = (answer or "").strip()

    if txt.rstrip(".!?") == "Não sei":
        return {"answer": txt, "citacoes": [], "contexto_encontrado": False}

    return {"answer": txt, "citacoes": formatar_citacoes(docs_relacionados, pergunta), "contexto_encontrado": True}

# 9. Workflow com LangGraph
class AgentState(TypedDict, total=False):
    pergunta: str
    triagem: dict
    resposta: Optional[str]
    citacoes: List[Dict]
    rag_sucesso: bool
    acao_final: str
    logs: List[str]

def node_triagem(state: AgentState) -> AgentState:
    logs = list(state.get("logs", []))
    logs.append("▶ Nó: triagem")
    return {
        **state,
        "triagem": triagem(state["pergunta"]),
        "logs": logs
    }

def node_auto_resolver(state: AgentState) -> AgentState:
    logs = list(state.get("logs", []))
    logs.append("▶ Nó: auto_resolver")
    resposta_rag = perguntar_politica_RAG(state["pergunta"])
    return {
        **state,
        "resposta": resposta_rag["answer"],
        "citacoes": resposta_rag.get("citacoes", []),
        "rag_sucesso": resposta_rag["contexto_encontrado"],
        "acao_final": "AUTO_RESOLVER" if resposta_rag["contexto_encontrado"] else state.get("acao_final"),
        "logs": logs
    }

def node_pedir_info(state: AgentState) -> AgentState:
    logs = list(state.get("logs", []))
    logs.append("▶ Nó: pedir_info")
    faltantes = state["triagem"].get("campos_faltantes", [])
    detalhe = ", ".join(faltantes) if faltantes else "Tema e contexto específico"
    return {
        **state,
        "resposta": f"Para avançar, preciso que detalhe: {detalhe}",
        "citacoes": [],
        "acao_final": "PEDIR_INFO",
        "logs": logs
    }

def node_abrir_chamado(state: AgentState) -> AgentState:
    logs = list(state.get("logs", []))
    logs.append("▶ Nó: abrir_chamado")
    return {
        **state,
        "resposta": f"Abrindo chamado com urgência: {state['triagem']['urgencia']}. "
                    f"Descrição: {state['pergunta'][:140]}",
        "citacoes": [],
        "acao_final": "ABRIR_CHAMADO",
        "logs": logs
    }

KEYWORDS_ABRIR_TICKET = ["aprovação", "exeção", "liberação", "abrir ticket", "abrir chamado", "acesso especial"]

def decidir_pos_triagem(state: AgentState) -> str:
    decisao = state["triagem"]["decisao"]
    if decisao == "AUTO_RESOLVER": return "auto"
    if decisao == "PEDIR_INFO": return "info"
    if decisao == "ABRIR_CHAMADO": return "chamado"

def decidir_pos_auto_resolver(state: AgentState) -> str:
    if state.get("rag_sucesso"): return "end"
    state_da_pergunta = (state["pergunta"] or "").lower()
    if any(k in state_da_pergunta for k in KEYWORDS_ABRIR_TICKET):
        return "chamado"
    return "info"

workflow = StateGraph(AgentState)
workflow.add_node("triagem", node_triagem)
workflow.add_node("auto_resolver", node_auto_resolver)
workflow.add_node("pedir_info", node_pedir_info)
workflow.add_node("abrir_chamado", node_abrir_chamado)

workflow.add_edge(START, "triagem")
workflow.add_conditional_edges("triagem", decidir_pos_triagem, {
    "auto": "auto_resolver",
    "info": "pedir_info",
    "chamado": "abrir_chamado"
})
workflow.add_conditional_edges("auto_resolver", decidir_pos_auto_resolver, {
    "info": "pedir_info",
    "chamado": "abrir_chamado",
    "end": END
})
workflow.add_edge("pedir_info", END)
workflow.add_edge("abrir_chamado", END)

grafo = workflow.compile()

# 10. Testes
if __name__ == "__main__":
    testes = [
        "Posso reembolsar a internet?",
        "Quero mais 5 dias de trabalho remoto. Como faço?",
        "Posso reembolsar cursos ou treinamentos da Alura?",
        "Tem como reembolsar certificações?",
        "Preciso de liberação especial para acessar sistema externo",
        "Quantas lontras tem em Salvador?"
    ]

    for pergunta in testes:
        resposta_final = grafo.invoke({"pergunta": pergunta, "logs": []})
        triag = resposta_final.get("triagem", {})

        print("\n-----------------------------------")
        for log in resposta_final.get("logs", []):
            print(log)

        print(f"❓ Pergunta: {pergunta}")
        print(f"📌 Decisão (triagem): {triag.get('decisao')} | Urgência: {triag.get('urgencia')} | "
              f"Ação Final (fluxo): {resposta_final.get('acao_final')}")
        print(f"💬 Resposta: {resposta_final.get('resposta')}")

        if resposta_final.get("citacoes"):
            print("📚 Citações:")
            for cit in resposta_final["citacoes"]:
                print(f" - {cit['documento']} (pág. {cit['pagina']}) → {cit['trecho']}")
