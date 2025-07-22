#!/usr/bin/env python3
"""
Teste para verificar se o paralelismo REAL está funcionando
"""
import asyncio
import time
import threading
from datetime import datetime

async def test_real_parallelism():
    """Testa se múltiplas tasks executam realmente em paralelo"""
    print("🧪 TESTE DE PARALELISMO REAL")
    print("=" * 50)
    
    async def mock_test(test_id, duration=3):
        """Simula um teste que demora alguns segundos"""
        start_time = time.time()
        thread_name = threading.current_thread().name
        
        print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando teste {test_id} (Thread: {thread_name})")
        
        # Simula processamento
        await asyncio.sleep(duration)
        
        end_time = time.time()
        print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Teste {test_id} concluído em {end_time - start_time:.2f}s (Thread: {thread_name})")
        
        return f"resultado_{test_id}"
    
    # Teste 1: Execução sequencial (para comparação)
    print("\n📊 TESTE 1: Execução Sequencial")
    start_sequential = time.time()
    
    for i in range(3):
        await mock_test(f"seq_{i}", 2)
    
    sequential_time = time.time() - start_sequential
    print(f"⏱️ Tempo sequencial: {sequential_time:.2f}s")
    
    # Teste 2: Execução paralela com asyncio.gather
    print("\n📊 TESTE 2: Execução Paralela (asyncio.gather)")
    start_parallel = time.time()
    
    tasks = [mock_test(f"par_{i}", 2) for i in range(3)]
    await asyncio.gather(*tasks)
    
    parallel_time = time.time() - start_parallel
    print(f"⏱️ Tempo paralelo: {parallel_time:.2f}s")
    
    # Teste 3: Execução com semáforo (como no sistema)
    print("\n📊 TESTE 3: Execução com Semáforo (max 2 simultâneos)")
    start_semaphore = time.time()
    
    semaphore = asyncio.Semaphore(2)
    
    async def limited_test(test_id):
        async with semaphore:
            return await mock_test(f"sem_{test_id}", 2)
    
    sem_tasks = [limited_test(i) for i in range(4)]
    await asyncio.gather(*sem_tasks)
    
    semaphore_time = time.time() - start_semaphore
    print(f"⏱️ Tempo com semáforo: {semaphore_time:.2f}s")
    
    # Análise
    print("\n📈 ANÁLISE DE PERFORMANCE:")
    print(f"Sequencial: {sequential_time:.2f}s")
    print(f"Paralelo: {parallel_time:.2f}s")
    print(f"Semáforo: {semaphore_time:.2f}s")
    
    speedup_parallel = sequential_time / parallel_time
    speedup_semaphore = sequential_time / semaphore_time
    
    print(f"\n🚀 SPEEDUP:")
    print(f"Paralelo: {speedup_parallel:.2f}x mais rápido")
    print(f"Semáforo: {speedup_semaphore:.2f}x mais rápido")
    
    if speedup_parallel > 2.5:
        print("✅ Paralelismo funcionando corretamente!")
    else:
        print("❌ Paralelismo pode não estar funcionando adequadamente")
    
    return speedup_parallel > 2.5

def test_threading():
    """Testa se múltiplas threads estão sendo usadas"""
    print("\n🧪 TESTE DE THREADING")
    print("=" * 50)
    
    import threading
    import time
    
    threads_used = set()
    
    def worker(worker_id):
        thread_name = threading.current_thread().name
        threads_used.add(thread_name)
        print(f"🔄 Worker {worker_id} executando na thread: {thread_name}")
        time.sleep(1)
        print(f"✅ Worker {worker_id} concluído na thread: {thread_name}")
    
    # Cria múltiplas threads
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    # Aguarda conclusão
    for t in threads:
        t.join()
    
    print(f"\n📊 Threads utilizadas: {len(threads_used)}")
    print(f"Nomes das threads: {list(threads_used)}")
    
    if len(threads_used) > 1:
        print("✅ Múltiplas threads sendo utilizadas!")
        return True
    else:
        print("❌ Apenas uma thread sendo utilizada")
        return False

async def test_agentgraph_parallel():
    """Testa paralelismo específico do AgentGraph"""
    print("\n🧪 TESTE DE PARALELISMO AGENTGRAPH")
    print("=" * 50)
    
    try:
        from testes.test_runner import MassiveTestRunner
        
        runner = MassiveTestRunner(max_workers=3)
        
        # Simula sessão pequena
        test_session = {
            'id': 'test_parallel_real',
            'question': 'SELECT COUNT(*) FROM usuarios',
            'groups': [
                {
                    'id': 1,
                    'sql_model_name': 'GPT-4o-mini',
                    'processing_enabled': False,
                    'processing_model_name': None,
                    'iterations': 3
                }
            ]
        }
        
        print(f"🚀 Testando {test_session['groups'][0]['iterations']} testes em paralelo...")
        start_time = time.time()
        
        results = await runner.run_test_session(
            test_session,
            validation_method='keyword',
            expected_content='COUNT'
        )
        
        total_time = time.time() - start_time
        print(f"⏱️ Tempo total: {total_time:.2f}s")
        
        if results and 'individual_results' in results:
            individual_times = [r.get('execution_time', 0) for r in results['individual_results']]
            avg_time = sum(individual_times) / len(individual_times) if individual_times else 0
            
            print(f"📊 Tempo médio por teste: {avg_time:.2f}s")
            print(f"📊 Tempo total esperado (sequencial): {avg_time * len(individual_times):.2f}s")
            print(f"📊 Tempo real: {total_time:.2f}s")
            
            if total_time < (avg_time * len(individual_times) * 0.7):
                print("✅ Paralelismo AgentGraph funcionando!")
                return True
            else:
                print("❌ Paralelismo AgentGraph pode estar sequencial")
                return False
        else:
            print("❌ Erro nos resultados")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste AgentGraph: {e}")
        return False

async def main():
    """Função principal"""
    print("🔧 TESTE COMPLETO DE PARALELISMO")
    print("=" * 60)
    
    tests = [
        ("Paralelismo Básico", test_real_parallelism),
        ("Threading", test_threading),
        ("AgentGraph Paralelo", test_agentgraph_parallel)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
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
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTADO: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 PARALELISMO FUNCIONANDO PERFEITAMENTE!")
    elif passed >= 2:
        print("⚠️ Paralelismo parcialmente funcionando")
    else:
        print("❌ Problemas sérios de paralelismo")
    
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
