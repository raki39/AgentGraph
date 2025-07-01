"""
Teste básico para validar a funcionalidade de gráficos
"""
import asyncio
import logging
import pandas as pd
from typing import Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Importar funções necessárias
from agents.tools import detect_query_type, generate_graph_type_context, extract_sql_query_from_response
from nodes.graph_selection_node import graph_selection_node
from nodes.graph_generation_node import graph_generation_node, generate_graph

async def test_query_detection():
    """Testa detecção de tipos de query"""
    print("\n=== TESTE: Detecção de Tipos de Query ===")
    
    test_queries = [
        "Mostre os dados de vendas",
        "Gere um gráfico de vendas por mês",
        "Criar gráfico de barras com os produtos",
        "Visualizar dados em pizza",
        "Plotar gráfico de linha temporal",
        "Prever vendas futuras",
        "Mostrar tabela de clientes"
    ]
    
    for query in test_queries:
        query_type = detect_query_type(query)
        print(f"Query: '{query}' -> Tipo: {query_type}")

def test_sql_extraction():
    """Testa extração de query SQL"""
    print("\n=== TESTE: Extração de Query SQL ===")

    # Incluir a resposta real que causou o problema
    real_response = """Para identificar as marcas com os produtos mais caros, primeiro, vou extrair os produtos com seus preços e marcas. Em seguida, ordenarei os resultados pelo preço em ordem decrescente para encontrar os mais caros.

Passo 1: Extrair marcas e preços dos produtos.
```sql
SELECT MARCA_PRODUTO, MAX(CAST(PRECO_VISTA AS FLOAT)) AS PRECO_MAXIMO
FROM tabela
GROUP BY MARCA_PRODUTO
ORDER BY PRECO_MAXIMO DESC
LIMIT 40;
```
Agora, vou executar a consulta."""

    test_responses = [
        real_response,  # Resposta real que causou o problema
        "```sql\nSELECT produto, SUM(vendas) FROM tabela GROUP BY produto;\n```",
        "A query SQL é: SELECT * FROM clientes WHERE idade > 25;",
        "Query: SELECT data, valor FROM vendas ORDER BY data;",
        "Aqui está o resultado:\n```\nSELECT categoria, COUNT(*) FROM produtos GROUP BY categoria\n```",
        "Resposta sem SQL válida"
    ]

    for i, response in enumerate(test_responses):
        sql_query = extract_sql_query_from_response(response)
        print(f"Teste {i+1}: SQL extraída: {sql_query}")
        if i == 0:  # Resposta real
            print(f"  -> Resposta real: {'✅ SUCESSO' if sql_query else '❌ FALHOU'}")

def test_graph_context_generation():
    """Testa geração de contexto para gráficos"""
    print("\n=== TESTE: Geração de Contexto de Gráfico ===")
    
    # Criar DataFrame de exemplo
    df_sample = pd.DataFrame({
        'produto': ['A', 'B', 'C'],
        'vendas': [100, 200, 150],
        'data': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03'])
    })
    
    user_query = "Gere um gráfico de vendas por produto"
    sql_query = "SELECT produto, SUM(vendas) as vendas FROM tabela GROUP BY produto"
    columns = ['produto', 'vendas']
    
    context = generate_graph_type_context(user_query, sql_query, columns, df_sample)
    print(f"Contexto gerado (primeiros 200 chars): {context[:200]}...")

async def test_graph_generation():
    """Testa geração de gráficos"""
    print("\n=== TESTE: Geração de Gráficos ===")
    
    # Criar DataFrame de teste
    df_test = pd.DataFrame({
        'categoria': ['Eletrônicos', 'Roupas', 'Casa', 'Livros'],
        'vendas': [1500, 800, 1200, 400],
        'lucro': [300, 160, 240, 80]
    })
    
    graph_types = ['bar_vertical', 'pie', 'line_simple', 'bar_grouped']
    
    for graph_type in graph_types:
        try:
            print(f"Testando gráfico: {graph_type}")
            image = await generate_graph(df_test, graph_type, f"Teste {graph_type}")
            
            if image:
                print(f"✅ Gráfico {graph_type} gerado com sucesso")
            else:
                print(f"❌ Falha ao gerar gráfico {graph_type}")
                
        except Exception as e:
            print(f"❌ Erro ao gerar gráfico {graph_type}: {e}")

async def test_graph_nodes():
    """Testa nós de gráfico"""
    print("\n=== TESTE: Nós de Gráfico ===")
    
    # Estado de teste
    test_state = {
        "user_input": "Gere um gráfico de vendas por categoria",
        "query_type": "sql_query_graphic",
        "response": "```sql\nSELECT categoria, SUM(vendas) as total_vendas FROM produtos GROUP BY categoria;\n```",
        "agent_id": "test_agent",
        "engine_id": "test_engine",
        "cache_id": "test_cache",
        "error": None
    }
    
    try:
        # Teste do nó de seleção (sem ObjectManager real)
        print("Testando nó de seleção de gráfico...")
        # result_state = await graph_selection_node(test_state)
        # print(f"Estado após seleção: {result_state.get('graph_type', 'Não definido')}")
        print("⚠️  Teste de nó de seleção requer ObjectManager configurado")
        
        # Teste do nó de geração (sem ObjectManager real)
        print("Testando nó de geração de gráfico...")
        # result_state = await graph_generation_node(test_state)
        # print(f"Gráfico gerado: {result_state.get('graph_generated', False)}")
        print("⚠️  Teste de nó de geração requer ObjectManager configurado")
        
    except Exception as e:
        print(f"❌ Erro nos testes de nós: {e}")

def test_integration_flow():
    """Testa fluxo de integração"""
    print("\n=== TESTE: Fluxo de Integração ===")
    
    # Simular fluxo completo
    user_queries = [
        "Mostre um gráfico de vendas por mês",
        "Criar gráfico de pizza com categorias",
        "Plotar linha temporal de receitas",
        "Visualizar dados em barras horizontais"
    ]
    
    for query in user_queries:
        print(f"\n--- Processando: '{query}' ---")
        
        # 1. Detecção
        query_type = detect_query_type(query)
        print(f"1. Tipo detectado: {query_type}")
        
        # 2. Simulação de resposta do AgentSQL
        if query_type == "sql_query_graphic":
            mock_sql_response = "```sql\nSELECT categoria, SUM(valor) FROM dados GROUP BY categoria;\n```"
            
            # 3. Extração de SQL
            sql_query = extract_sql_query_from_response(mock_sql_response)
            print(f"2. SQL extraída: {sql_query}")
            
            # 4. Contexto para LLM
            if sql_query:
                df_mock = pd.DataFrame({'categoria': ['A', 'B'], 'valor': [100, 200]})
                context = generate_graph_type_context(query, sql_query, ['categoria', 'valor'], df_mock)
                print(f"3. Contexto gerado: ✅")
                print(f"4. Próximo passo: Seleção de gráfico pela LLM")
                print(f"5. Próximo passo: Geração do gráfico")
            else:
                print("❌ Falha na extração de SQL")
        else:
            print("ℹ️  Query não requer gráfico")

async def main():
    """Função principal de teste"""
    print("🧪 INICIANDO TESTES DE FUNCIONALIDADE DE GRÁFICOS")
    print("=" * 60)
    
    # Executar testes
    test_query_detection()
    test_sql_extraction()
    test_graph_context_generation()
    await test_graph_generation()
    await test_graph_nodes()
    test_integration_flow()
    
    print("\n" + "=" * 60)
    print("✅ TESTES CONCLUÍDOS")
    print("\nPara testes completos, execute o sistema com:")
    print("python app.py")
    print("\nE teste com queries como:")
    print("- 'Gere um gráfico de vendas por categoria'")
    print("- 'Mostrar gráfico de pizza com dados'")
    print("- 'Criar visualização em barras'")

if __name__ == "__main__":
    asyncio.run(main())
