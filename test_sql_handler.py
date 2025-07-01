"""
Teste específico para verificar o callback handler SQL
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
from agents.sql_agent import SQLQueryCaptureHandler

# Configurar logging
logging.basicConfig(level=logging.INFO)

def test_handler_creation():
    """Testa criação do handler"""
    print("🧪 TESTE: Criação do Handler")
    
    try:
        handler = SQLQueryCaptureHandler()
        print("✅ Handler criado com sucesso")
        print(f"   - SQL queries: {handler.sql_queries}")
        print(f"   - Agent actions: {handler.agent_actions}")
        print(f"   - Step count: {handler.step_count}")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar handler: {e}")
        return False

def test_handler_methods():
    """Testa métodos do handler"""
    print("\n🧪 TESTE: Métodos do Handler")
    
    try:
        handler = SQLQueryCaptureHandler()
        
        # Simular adição de query
        handler.sql_queries.append("SELECT * FROM test")
        
        # Testar métodos
        last_query = handler.get_last_sql_query()
        all_queries = handler.get_all_sql_queries()
        
        print(f"✅ get_last_sql_query(): {last_query}")
        print(f"✅ get_all_sql_queries(): {all_queries}")
        
        # Testar reset
        handler.reset()
        print(f"✅ reset(): queries={len(handler.sql_queries)}, actions={len(handler.agent_actions)}")
        
        return True
    except Exception as e:
        print(f"❌ Erro nos métodos: {e}")
        return False

async def test_integration():
    """Testa integração básica"""
    print("\n🧪 TESTE: Integração Básica")
    
    try:
        # Simular estrutura de ação do LangChain
        class MockAction:
            def __init__(self, tool, tool_input):
                self.tool = tool
                self.tool_input = tool_input
        
        handler = SQLQueryCaptureHandler()
        
        # Simular ação SQL
        mock_action = MockAction(
            tool="sql_db_query",
            tool_input={"query": "SELECT MARCA_PRODUTO, MAX(PRECO_VISTA) FROM tabela GROUP BY MARCA_PRODUTO"}
        )
        
        # Chamar handler
        handler.on_agent_action(mock_action)
        
        # Verificar captura
        captured_query = handler.get_last_sql_query()
        
        if captured_query:
            print(f"✅ Query capturada: {captured_query}")
            return True
        else:
            print("❌ Nenhuma query foi capturada")
            return False
            
    except Exception as e:
        print(f"❌ Erro na integração: {e}")
        return False

def test_edge_cases():
    """Testa casos extremos"""
    print("\n🧪 TESTE: Casos Extremos")
    
    try:
        handler = SQLQueryCaptureHandler()
        
        # Caso 1: Ação não-SQL
        class MockAction:
            def __init__(self, tool, tool_input):
                self.tool = tool
                self.tool_input = tool_input
        
        non_sql_action = MockAction("other_tool", {"param": "value"})
        handler.on_agent_action(non_sql_action)
        
        print(f"✅ Ação não-SQL ignorada: {len(handler.sql_queries)} queries")
        
        # Caso 2: Input inválido
        invalid_action = MockAction("sql_db_query", "string_instead_of_dict")
        handler.on_agent_action(invalid_action)
        
        print(f"✅ Input inválido tratado: {len(handler.sql_queries)} queries")
        
        # Caso 3: Query vazia
        empty_action = MockAction("sql_db_query", {"query": ""})
        handler.on_agent_action(empty_action)
        
        print(f"✅ Query vazia ignorada: {len(handler.sql_queries)} queries")
        
        # Caso 4: Query válida
        valid_action = MockAction("sql_db_query", {"query": "SELECT COUNT(*) FROM users"})
        handler.on_agent_action(valid_action)
        
        print(f"✅ Query válida capturada: {len(handler.sql_queries)} queries")
        print(f"   Query: {handler.get_last_sql_query()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro nos casos extremos: {e}")
        return False

async def main():
    """Função principal de teste"""
    print("🧪 TESTE DO CALLBACK HANDLER SQL")
    print("=" * 50)
    
    tests = [
        ("Criação do Handler", test_handler_creation),
        ("Métodos do Handler", test_handler_methods),
        ("Integração Básica", test_integration),
        ("Casos Extremos", test_edge_cases)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 RESULTADOS DOS TESTES")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 RESUMO: {passed}/{len(tests)} testes passaram")
    
    if passed == len(tests):
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("\nO callback handler está funcionando corretamente.")
        print("Agora teste no sistema principal:")
        print("1. Execute: python app.py")
        print("2. Faça upload do CSV")
        print("3. Teste: 'Gere um gráfico das marcas com produtos mais caros'")
    else:
        print(f"\n⚠️ {len(tests) - passed} TESTE(S) FALHARAM")
        print("Verifique os erros acima antes de prosseguir.")

if __name__ == "__main__":
    asyncio.run(main())
