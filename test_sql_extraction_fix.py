"""
Teste específico para verificar a correção da extração de SQL
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.tools import extract_sql_query_from_response

def test_real_response():
    """Testa com a resposta real que causou o problema"""
    
    # Resposta real que causou o erro
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

    print("🧪 TESTE DE CORREÇÃO DA EXTRAÇÃO DE SQL")
    print("=" * 50)
    
    print("Resposta do agente:")
    print("-" * 30)
    print(real_response)
    print("-" * 30)
    
    # Testar extração
    sql_query = extract_sql_query_from_response(real_response)
    
    print(f"\nSQL extraída:")
    print(f"✅ SUCESSO: {sql_query}" if sql_query else "❌ FALHOU: None")
    
    if sql_query:
        print(f"\nQuery completa:")
        print(sql_query)
        
        # Verificar se a query está correta
        expected_parts = [
            "SELECT MARCA_PRODUTO",
            "MAX(CAST(PRECO_VISTA AS FLOAT))",
            "FROM tabela",
            "GROUP BY MARCA_PRODUTO",
            "ORDER BY PRECO_MAXIMO DESC",
            "LIMIT 40"
        ]
        
        print(f"\nVerificação de partes da query:")
        all_parts_found = True
        for part in expected_parts:
            found = part in sql_query
            print(f"  {'✅' if found else '❌'} {part}: {'Encontrado' if found else 'NÃO encontrado'}")
            if not found:
                all_parts_found = False
        
        print(f"\nResultado final: {'✅ QUERY COMPLETA E CORRETA' if all_parts_found else '⚠️ QUERY INCOMPLETA'}")
    
    return sql_query is not None

def test_other_formats():
    """Testa outros formatos de resposta"""
    
    print("\n" + "=" * 50)
    print("🧪 TESTE DE OUTROS FORMATOS")
    
    test_cases = [
        {
            "name": "Formato simples com ```sql",
            "response": "```sql\nSELECT * FROM produtos;\n```"
        },
        {
            "name": "Formato sem sql, só ```",
            "response": "```\nSELECT categoria, COUNT(*) FROM itens GROUP BY categoria;\n```"
        },
        {
            "name": "SELECT direto com ;",
            "response": "A query é: SELECT nome, preco FROM produtos WHERE preco > 100;"
        },
        {
            "name": "SELECT multilinhas",
            "response": """Vou executar esta consulta:
SELECT 
    produto,
    SUM(vendas) as total
FROM vendas_mensais 
GROUP BY produto
ORDER BY total DESC;

Executando agora..."""
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Teste {i}: {test_case['name']} ---")
        sql_query = extract_sql_query_from_response(test_case['response'])
        print(f"Resultado: {'✅ SUCESSO' if sql_query else '❌ FALHOU'}")
        if sql_query:
            print(f"SQL: {sql_query}")

if __name__ == "__main__":
    success = test_real_response()
    test_other_formats()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 CORREÇÃO FUNCIONOU! O problema foi resolvido.")
        print("\nAgora você pode testar novamente no sistema principal:")
        print("1. Execute: python app.py")
        print("2. Faça upload do CSV")
        print("3. Teste com: 'Gere um gráfico das marcas com produtos mais caros'")
    else:
        print("❌ CORREÇÃO NÃO FUNCIONOU. Precisa de mais ajustes.")
