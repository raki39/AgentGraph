# 📊 Funcionalidade de Gráficos - AgentGraph

## 🎯 Visão Geral

A funcionalidade de gráficos foi integrada ao AgentGraph seguindo a arquitetura LangGraph existente, permitindo que o sistema detecte automaticamente quando o usuário solicita visualizações e gere gráficos apropriados baseados nos dados SQL.

## 🔄 Fluxo de Execução

```
Pergunta do Usuário → Detecção (sql_query_graphic) → AgentSQL → 
Seleção de Gráfico → Geração de Gráfico → Refinamento (Opcional) → Resposta Final
```

## 🏗️ Arquitetura Implementada

### **Novos Componentes:**

1. **Sistema de Detecção Expandido** (`agents/tools.py`)
   - Função `detect_query_type()` atualizada
   - Detecção de palavras-chave para gráficos
   - Retorna `sql_query_graphic` quando gráfico é solicitado

2. **Nó de Seleção de Gráfico** (`nodes/graph_selection_node.py`)
   - Extrai query SQL da resposta do AgentSQL
   - Executa query para obter dados
   - Consulta LLM para escolher tipo de gráfico mais adequado
   - Armazena dados no ObjectManager

3. **Nó de Geração de Gráfico** (`nodes/graph_generation_node.py`)
   - 10 tipos de gráficos implementados
   - Preparação automática de dados
   - Geração usando matplotlib
   - Armazenamento de imagem no ObjectManager

4. **Interface Gradio Atualizada** (`app.py`)
   - Componente de imagem para exibir gráficos
   - Controle de visibilidade automático
   - Integração com sistema de reset

### **Fluxo Condicional Atualizado** (`graphs/main_graph.py`)

```python
# Após AgentSQL
workflow.add_conditional_edges(
    "process_query",
    should_generate_graph,  # Nova função condicional
    {
        "graph_selection": "graph_selection",
        "refine_response": "refine_response", 
        "cache_response": "cache_response"
    }
)
```

## 📊 Tipos de Gráficos Suportados

| Tipo | Código | Aplicação |
|------|--------|-----------|
| Linha Simples | `line_simple` | Tendências temporais |
| Múltiplas Linhas | `multiline` | Comparação de séries |
| Área | `area` | Volume ao longo do tempo |
| Barras Verticais | `bar_vertical` | Comparação de categorias |
| Barras Horizontais | `bar_horizontal` | Muitas categorias |
| Barras Agrupadas | `bar_grouped` | Múltiplas métricas |
| Barras Empilhadas | `bar_stacked` | Partes de um todo |
| Pizza | `pie` | Proporções simples |
| Donut | `donut` | Proporções com centro |
| Pizzas Múltiplas | `pie_multiple` | Comparação de grupos |

## 🔍 Sistema de Detecção

### **Palavras-chave Detectadas:**
- `gráfico`, `grafico`, `chart`, `plot`
- `visualizar`, `visualização`, `mostrar gráfico`
- `gerar gráfico`, `criar gráfico`, `plotar`
- `barras`, `linha`, `pizza`, `área`
- `scatter`, `dispersão`, `histograma`

### **Exemplos de Queries:**
```
✅ "Gere um gráfico de vendas por mês"
✅ "Mostrar gráfico de pizza com categorias"
✅ "Criar visualização em barras dos produtos"
✅ "Plotar linha temporal de receitas"
✅ "Exibir gráfico de área das vendas"
```

## 🧠 Seleção Inteligente de Gráfico

A LLM analisa:
- **Pergunta do usuário**: Intenção e contexto
- **Query SQL**: Estrutura e colunas
- **Tipos de dados**: Numérico, categórico, temporal
- **Amostra dos dados**: Primeiras linhas

### **Contexto Enviado à LLM:**
```
Você é um especialista em visualização de dados...

Pergunta do usuário: {user_query}
Query SQL gerada: {sql_query}
Colunas retornadas: {columns}
Amostra dos dados: {sample}

Escolha o tipo de gráfico mais adequado (1-10)...
```

## 🎨 Preparação Automática de Dados

### **Por Tipo de Gráfico:**

- **Linha/Área**: Ordena por data/sequência
- **Barras**: Ordena por valor, limita categorias
- **Pizza**: Agrupa dados, limita a 10 categorias
- **Agrupadas/Empilhadas**: Identifica colunas numéricas

### **Tratamentos Aplicados:**
- Detecção automática de tipos de coluna
- Remoção de valores nulos/negativos (pizza)
- Limitação de categorias para legibilidade
- Formatação de datas e números

## 🔧 Integração com ObjectManager

### **Objetos Gerenciados:**
- **DataFrame dos dados**: `graph_data`
- **Imagem do gráfico**: `graph_image`
- **Referências serializáveis**: IDs UUID

### **Estado do Agente Expandido:**
```python
# Novos campos no AgentState
"query_type": str,              # Tipo detectado
"sql_query_extracted": str,     # SQL extraída
"graph_type": str,              # Tipo escolhido
"graph_data": dict,             # Dados serializáveis
"graph_image_id": str,          # ID da imagem
"graph_generated": bool,        # Status de geração
"graph_error": str              # Erros, se houver
```

## 🖥️ Interface Gradio

### **Componentes Adicionados:**
- **Componente de Imagem**: Exibe gráficos gerados
- **Controle de Visibilidade**: Aparece apenas quando há gráfico
- **Integração com Reset**: Limpa gráfico ao resetar

### **Fluxo na Interface:**
1. Usuário faz pergunta com gráfico
2. Sistema processa e gera visualização
3. Gráfico aparece abaixo do chat
4. Reset limpa chat e gráfico

## 🧪 Testes e Validação

### **Arquivo de Teste:** `test_graph_functionality.py`

**Testes Implementados:**
- ✅ Detecção de tipos de query
- ✅ Extração de SQL da resposta
- ✅ Geração de contexto para LLM
- ✅ Geração de gráficos por tipo
- ✅ Fluxo de integração completo

### **Como Executar Testes:**
```bash
python test_graph_functionality.py
```

## 🚀 Como Usar

### **1. Instalar Dependências:**
```bash
pip install matplotlib pillow numpy
```

### **2. Executar Sistema:**
```bash
python app.py
```

### **3. Fazer Upload de CSV**

### **4. Fazer Perguntas com Gráficos:**
```
"Gere um gráfico de vendas por categoria"
"Mostrar gráfico de pizza com os dados"
"Criar visualização em barras dos produtos"
"Plotar linha temporal das receitas"
```

## 🔍 Troubleshooting

### **Problemas Comuns:**

1. **Gráfico não aparece:**
   - Verificar se query contém palavras-chave
   - Verificar se SQL retorna dados válidos
   - Verificar logs para erros de geração

2. **Tipo de gráfico inadequado:**
   - LLM escolhe baseado nos dados disponíveis
   - Pode ser refinado ajustando o contexto

3. **Erro na geração:**
   - Verificar se dados são compatíveis com tipo
   - Verificar se matplotlib está instalado

### **Logs Importantes:**
```
[GRAPH_SELECTION] Tipo de query detectado: sql_query_graphic
[GRAPH_SELECTION] Query SQL extraída: SELECT...
[GRAPH_SELECTION] Tipo de gráfico selecionado: bar_vertical
[GRAPH_GENERATION] Gráfico gerado com sucesso: bar_vertical
[GRADIO] Gráfico salvo em: /tmp/...
```

## 🎯 Próximos Passos

### **Melhorias Futuras:**
1. **Mais Tipos de Gráfico**: Scatter, heatmap, boxplot
2. **Customização**: Cores, títulos, estilos
3. **Interatividade**: Plotly para gráficos interativos
4. **Export**: Download de gráficos em diferentes formatos
5. **Templates**: Estilos pré-definidos por domínio

### **Otimizações:**
1. **Cache de Gráficos**: Evitar regeneração desnecessária
2. **Processamento Assíncrono**: Geração em background
3. **Compressão**: Otimizar tamanho das imagens
4. **Batch Processing**: Múltiplos gráficos simultâneos

---

**🎉 A funcionalidade de gráficos está totalmente integrada e pronta para uso!**
