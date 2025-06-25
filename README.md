# AgentGraph - LangGraph SQL Agent

Um chatbot inteligente que utiliza LangGraph para processar consultas SQL em dados CSV, com interface Gradio e múltiplos modelos LLM.

## Funcionalidades

- 🤖 **Agente SQL Inteligente**: Processa consultas em linguagem natural e gera SQL
- 📊 **Processamento de CSV**: Converte automaticamente CSV para SQLite
- 🔄 **LangGraph**: Arquitetura baseada em nós com paralelismo e async
- 🎯 **Múltiplos Modelos**: Suporte a LLaMA 70B, LLaMA 8B e Qwen 32B
- 🌐 **Interface Gradio**: Interface web intuitiva
- 💾 **Cache Inteligente**: Sistema de cache para otimização
- 📈 **Modo Avançado**: Refinamento de respostas com LLM adicional

## Estrutura do Projeto

```
agentgraph/
├── app.py                     # Entry point: Gradio + LangGraph
├── graphs/
│   └── main_graph.py          # StateGraph principal
├── nodes/
│   ├── agent_node.py          # Nó com AgentExecutor
│   └── custom_nodes.py        # Nós personalizados
├── agents/
│   ├── sql_agent.py           # Criação do agente SQL
│   └── tools.py               # Ferramentas do agente
├── utils/
│   ├── database.py            # Funções de banco de dados
│   └── config.py              # Configurações
├── uploaded_data/             # Arquivos CSV enviados
├── requirements.txt
├── README.md
└── .env
```

## Instalação

1. Clone o repositório
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure as variáveis de ambiente no arquivo `.env`
4. Execute a aplicação:
   ```bash
   python app.py
   ```

## Configuração

Edite o arquivo `.env` com suas chaves de API:

```env
HUGGINGFACE_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

## Uso

1. Acesse a interface web
2. Selecione o modelo LLM desejado
3. Faça upload de um CSV (opcional)
4. Digite suas perguntas em linguagem natural
5. O sistema processará e retornará respostas baseadas nos dados

## Tecnologias

- **LangGraph**: Orquestração de agentes
- **LangChain**: Framework de LLM
- **Gradio**: Interface web
- **SQLAlchemy**: ORM para banco de dados
- **Pandas**: Processamento de dados
- **HuggingFace**: Modelos LLM
