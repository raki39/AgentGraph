# 🔍 LangSmith Integration - AgentGraph

## 🎯 Visão Geral

O AgentGraph agora inclui integração completa com **LangSmith**, a plataforma de observabilidade da LangChain, proporcionando rastreamento avançado, monitoramento de performance e debug detalhado de todos os fluxos LangGraph.

## ✨ Benefícios da Integração

### **🔍 Observabilidade Completa**
- **Rastreamento de Execuções**: Cada query é rastreada do início ao fim
- **Visualização de Fluxos**: Veja como os nós LangGraph se conectam
- **Timing Detalhado**: Performance de cada componente
- **Hierarquia de Traces**: Estrutura aninhada de chamadas

### **📊 Monitoramento de Performance**
- **Latência por Nó**: Identifique gargalos no fluxo
- **Uso de Tokens**: Custos detalhados por modelo
- **Taxa de Sucesso**: Monitoramento de erros
- **Dashboards Customizáveis**: Métricas em tempo real

### **🐛 Debug Avançado**
- **Inputs/Outputs**: Veja dados em cada etapa
- **Estados Intermediários**: Debug do LangGraph
- **Logs Estruturados**: Correlação com traces
- **Comparação de Execuções**: Análise de diferenças

## 🚀 Configuração Rápida

### **1. Obtenha API Key**
1. Acesse [LangSmith](https://smith.langchain.com/)
2. Crie uma conta gratuita
3. Vá para **Settings** → **API Keys**
4. Gere uma nova API key

### **2. Configure Variáveis de Ambiente**
Adicione ao seu arquivo `.env`:

```env
# LangSmith - Observabilidade
LANGSMITH_API_KEY=lsv2_pt_your_key_here
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=agentgraph-project
```

### **3. Reinicie a Aplicação**
```bash
python app.py
```

✅ **Pronto!** Você verá no log:
```
✅ LangSmith habilitado - Projeto: 'agentgraph-project'
🔍 Traces serão enviados para LangSmith automaticamente
```

## 🎛️ Configurações Avançadas

### **Projetos Personalizados**
```env
# Diferentes ambientes
LANGSMITH_PROJECT=agentgraph-dev        # Desenvolvimento
LANGSMITH_PROJECT=agentgraph-staging    # Homologação
LANGSMITH_PROJECT=agentgraph-prod       # Produção
```

### **Configuração Condicional**
```env
# Habilitar apenas em produção
LANGSMITH_TRACING=true   # true/false
```

## 📊 O Que é Rastreado

### **Fluxo Principal LangGraph**
- ✅ `validate_input` - Validação de entrada
- ✅ `check_cache` - Verificação de cache
- ✅ `prepare_context` - Preparação de contexto
- ✅ `get_db_sample` - Amostra do banco
- ✅ `process_query` - Processamento SQL
- ✅ `graph_selection` - Seleção de gráfico
- ✅ `graph_generation` - Geração de gráfico
- ✅ `refine_response` - Refinamento
- ✅ `cache_response` - Cache da resposta

### **Agentes e Modelos**
- ✅ **SQL Agent**: Todas as chamadas LLM
- ✅ **OpenAI**: GPT-4o, GPT-4o-mini, o3-mini
- ✅ **Anthropic**: Claude-3.5-Sonnet
- ✅ **HuggingFace**: LLaMA, DeepSeek (refinamento)

### **Operações de Dados**
- ✅ **CSV Processing**: Upload e processamento
- ✅ **Database Operations**: Criação e consultas
- ✅ **Graph Generation**: Criação de visualizações

## 🔧 Implementação Técnica

### **Integração Automática**
A integração é **completamente automática** - não requer alterações no código existente:

```python
# LangChain/LangGraph detecta automaticamente as variáveis:
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=...
# LANGSMITH_PROJECT=...

# Todas as chamadas são rastreadas automaticamente
llm = ChatOpenAI(model="gpt-4o-mini")
response = llm.invoke("Hello")  # ← Automaticamente rastreado
```

### **Metadados Customizados**
O sistema adiciona metadados específicos do AgentGraph:

```python
{
    "project": "agentgraph-project",
    "application": "AgentGraph", 
    "version": "1.0.0",
    "environment": "production"
}
```

## 📈 Dashboards e Análises

### **Métricas Principais**
- **Queries por Hora**: Volume de uso
- **Latência Média**: Performance geral
- **Taxa de Erro**: Confiabilidade
- **Custo por Query**: Eficiência econômica

### **Análises Avançadas**
- **Modelos Mais Usados**: Preferências
- **Tipos de Query**: Padrões de uso
- **Performance por Nó**: Otimizações
- **Comparação Temporal**: Tendências

## 🚨 Troubleshooting

### **LangSmith Não Aparece**
```bash
# Verifique as variáveis
echo $LANGSMITH_API_KEY
echo $LANGSMITH_TRACING

# Logs da aplicação
python app.py | grep -i langsmith
```

### **Traces Não Aparecem**
1. **API Key Válida**: Verifique no dashboard LangSmith
2. **Projeto Existe**: Será criado automaticamente
3. **Conectividade**: Teste acesso a `https://api.smith.langchain.com`

### **Performance Impact**
- **Overhead Mínimo**: ~5-10ms por trace
- **Async Processing**: Não bloqueia execução
- **Configurável**: Pode ser desabilitado facilmente

## 🎯 Próximos Passos

### **Análise de Dados**
1. **Execute algumas queries** no AgentGraph
2. **Acesse LangSmith** dashboard
3. **Explore traces** e métricas
4. **Configure alertas** para erros

### **Otimização**
1. **Identifique gargalos** nos traces
2. **Compare modelos** diferentes
3. **Analise custos** por tipo de query
4. **Otimize prompts** baseado em dados

---

**🏆 Conclusão**: A integração com LangSmith transforma o AgentGraph em uma plataforma **observável** e **otimizável**, proporcionando insights valiosos sobre performance, custos e comportamento dos agentes.

**🔗 Links Úteis**:
- [LangSmith Dashboard](https://smith.langchain.com/)
- [Documentação LangSmith](https://docs.smith.langchain.com/)
- [LangGraph Tracing Guide](https://docs.smith.langchain.com/observability/how_to_guides/trace_with_langgraph)
