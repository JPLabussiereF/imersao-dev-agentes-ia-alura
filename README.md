# 🤖 Service Desk IA - Carraro Desenvolvimento

Um sistema inteligente de Service Desk que usa IA para triagem automática de solicitações e consulta a políticas internas.

## 🚀 Como rodar o projeto

### 1. Preparar o ambiente

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar o ambiente virtual
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
GOOGLE_API_KEY=sua_chave_api_do_google_gemini_aqui
```

**Como obter a API Key do Google Gemini:**
1. Acesse [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Faça login com sua conta Google
3. Clique em "Create API Key"
4. Copie a chave e cole no arquivo `.env`

### 3. Estrutura de pastas

Crie a seguinte estrutura:

```
projeto/
├── app.py                 # Backend Flask
├── main.py               # Seu código original
├── requirements.txt      # Dependências
├── .env                 # Variáveis de ambiente
├── templates/
│   └── index.html       # Frontend
└── assets/
    └── docs/            # Seus PDFs das políticas
        ├── politica1.pdf
        ├── politica2.pdf
        └── ...
```

### 4. Executar o sistema

```bash
# Rodar o servidor Flask
python app.py
```

Acesse: http://localhost:5000

## 🎯 Como usar

1. **Digite sua pergunta** no campo de texto
2. **Clique em "Enviar Pergunta"** ou use `Ctrl+Enter`
3. **Veja o resultado** com:
   - Status da triagem (AUTO_RESOLVER, PEDIR_INFO, ABRIR_CHAMADO)
   - Resposta do sistema
   - Referências dos documentos (se encontradas)

## 🎨 Paleta de cores Alura

- **Azul principal**: #0066CC
- **Azul escuro**: #051933  
- **Verde**: #00C86F
- **Cinza claro**: #F5F5F5
- **Branco**: #FFFFFF

## 📋 Funcionalidades

- ✅ **Triagem inteligente** de solicitações
- ✅ **RAG (Retrieval Augmented Generation)** com documentos PDF
- ✅ **Interface responsiva** com design Alura
- ✅ **Status em tempo real** do sistema
- ✅ **Citações** dos documentos consultados
- ✅ **Workflow** com LangGraph

## 🔧 Troubleshooting

**Erro de API Key:**
- Verifique se a `GOOGLE_API_KEY` está correta no arquivo `.env`

**Nenhum documento carregado:**
- Certifique-se que os PDFs estão na pasta `assets/docs/`
- Verifique se os arquivos não estão corrompidos

## 📱 Interface

A interface foi desenvolvida com:
- **Responsiva** para desktop e mobile
- **Paleta oficial** da Alura
- **Design limpo** e intuitivo
- **Feedback visual** em tempo real