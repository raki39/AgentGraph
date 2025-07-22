#!/usr/bin/env python3
"""
Teste rápido para verificar se as correções de paralelismo funcionam
"""
import asyncio
import time
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_parallel_execution():
    """Testa execução paralela básica"""
    print("🧪 Testando execução paralela...")
    
    from testes.test_runner import MassiveTestRunner
    
    # Cria runner com 3 workers
    runner = MassiveTestRunner(max_workers=3)
    
    # Simula sessão de teste pequena
    test_session = {
        'id': 'test_parallel',
        'question': 'SELECT COUNT(*) FROM usuarios',
        'groups': [
            {
                'id': 1,
                'sql_model_name': 'GPT-4o-mini',
                'processing_enabled': False,
                'processing_model_name': None,
                'iterations': 3
            },
            {
                'id': 2,
                'sql_model_name': 'GPT-4o-mini',
                'processing_enabled': True,
                'processing_model_name': 'GPT-4o-mini',
                'iterations': 2
            }
        ]
    }
    
    print(f"📊 Testando {sum(g['iterations'] for g in test_session['groups'])} testes em paralelo")
    
    start_time = time.time()
    
    try:
        # Executa testes
        results = await runner.run_test_session(
            test_session,
            validation_method='keyword',
            expected_content='COUNT'
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"✅ Testes concluídos em {total_time:.2f}s")
        
        # Verifica resultados
        if results and 'group_results' in results:
            print(f"📊 Grupos processados: {len(results['group_results'])}")
            print(f"📊 Testes individuais: {len(results.get('individual_results', []))}")
            
            for group in results['group_results']:
                print(f"   Grupo {group['group_id']}: {group['total_tests']} testes, {group['success_rate']}% sucesso")
            
            return True
        else:
            print("❌ Resultados inválidos")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_validator():
    """Testa o validador"""
    print("\n🧪 Testando validador...")
    
    from testes.test_validator import TestValidator
    
    validator = TestValidator()
    
    # Teste keyword
    result = await validator.validate_result(
        question="Quantos usuários temos?",
        sql_query="SELECT COUNT(*) FROM usuarios",
        response="Temos 150 usuários no total",
        method='keyword',
        expected_content='150'
    )
    
    if result['valid']:
        print("✅ Validação keyword funcionando")
        return True
    else:
        print(f"❌ Validação keyword falhou: {result}")
        return False

def test_imports():
    """Testa imports básicos"""
    print("\n🧪 Testando imports...")
    
    try:
        from testes.test_runner import MassiveTestRunner
        from testes.test_validator import TestValidator
        from testes.report_generator import ReportGenerator
        from graphs.main_graph import AgentGraphManager
        
        print("✅ Todos os imports funcionando")
        return True
    except Exception as e:
        print(f"❌ Erro no import: {e}")
        return False

async def main():
    """Função principal"""
    print("🔧 TESTE DAS CORREÇÕES DE PARALELISMO")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Validator", test_validator),
        ("Execução Paralela", test_parallel_execution)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"✅ {test_name} PASSOU")
            else:
                print(f"❌ {test_name} FALHOU")
        except Exception as e:
            print(f"❌ {test_name} ERRO: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTADO: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 CORREÇÕES FUNCIONANDO!")
        print("🚀 Paralelismo implementado")
        print("✅ Sistema pronto para uso")
    else:
        print("⚠️ Alguns problemas ainda existem")
    
    print("=" * 50)

if __name__ == '__main__':
    asyncio.run(main())
