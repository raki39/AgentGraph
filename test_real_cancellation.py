#!/usr/bin/env python3
"""
Teste para verificar se o cancelamento REAL está funcionando
"""
import asyncio
import time
import threading
from datetime import datetime

async def test_real_cancellation():
    """Testa se o cancelamento realmente para a execução"""
    print("🧪 TESTE DE CANCELAMENTO REAL")
    print("=" * 50)
    
    async def long_running_task(task_id, duration=10):
        """Simula uma task que demora muito tempo"""
        start_time = time.time()
        print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Iniciando task {task_id} (duração: {duration}s)")
        
        try:
            # Simula processamento longo com verificações de cancelamento
            for i in range(duration):
                await asyncio.sleep(1)
                elapsed = time.time() - start_time
                print(f"⏳ Task {task_id}: {i+1}/{duration}s ({elapsed:.1f}s total)")
                
                # Verifica se foi cancelada
                if asyncio.current_task().cancelled():
                    print(f"🚫 Task {task_id} detectou cancelamento!")
                    raise asyncio.CancelledError()
            
            end_time = time.time()
            print(f"✅ Task {task_id} concluída em {end_time - start_time:.2f}s")
            return f"resultado_{task_id}"
            
        except asyncio.CancelledError:
            elapsed = time.time() - start_time
            print(f"🚫 Task {task_id} CANCELADA após {elapsed:.2f}s")
            raise
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Task {task_id} erro após {elapsed:.2f}s: {e}")
            raise
    
    # Teste 1: Cancelamento manual
    print("\n📊 TESTE 1: Cancelamento Manual")
    
    # Cria task de longa duração
    task1 = asyncio.create_task(long_running_task("manual_1", 15))
    
    # Aguarda 3 segundos e cancela
    await asyncio.sleep(3)
    print(f"🚫 Cancelando task manual_1 após 3s...")
    task1.cancel()
    
    try:
        result = await task1
        print(f"❌ Task não foi cancelada! Resultado: {result}")
        return False
    except asyncio.CancelledError:
        print(f"✅ Task cancelada com sucesso!")
    
    # Teste 2: Timeout automático
    print("\n📊 TESTE 2: Timeout Automático")
    
    try:
        result = await asyncio.wait_for(long_running_task("timeout_1", 10), timeout=5)
        print(f"❌ Task não teve timeout! Resultado: {result}")
        return False
    except asyncio.TimeoutError:
        print(f"✅ Timeout funcionou corretamente!")
    
    # Teste 3: Múltiplas tasks com cancelamento seletivo
    print("\n📊 TESTE 3: Cancelamento Seletivo")
    
    tasks = []
    for i in range(3):
        task = asyncio.create_task(long_running_task(f"multi_{i}", 8))
        tasks.append(task)
    
    # Aguarda 2 segundos e cancela apenas a task do meio
    await asyncio.sleep(2)
    print(f"🚫 Cancelando apenas task multi_1...")
    tasks[1].cancel()
    
    # Aguarda todas terminarem
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    cancelled_count = sum(1 for r in results if isinstance(r, asyncio.CancelledError))
    completed_count = sum(1 for r in results if isinstance(r, str))
    error_count = len(results) - cancelled_count - completed_count
    
    print(f"📊 Resultados: {completed_count} concluídas, {cancelled_count} canceladas, {error_count} erros")
    
    if cancelled_count == 1 and completed_count == 2:
        print("✅ Cancelamento seletivo funcionou!")
        return True
    else:
        print("❌ Cancelamento seletivo falhou!")
        return False

async def test_agentgraph_cancellation():
    """Testa cancelamento específico do AgentGraph"""
    print("\n🧪 TESTE DE CANCELAMENTO AGENTGRAPH")
    print("=" * 50)
    
    try:
        from testes.test_runner import MassiveTestRunner
        
        runner = MassiveTestRunner(max_workers=2)
        
        # Simula sessão com testes longos
        test_session = {
            'id': 'test_cancellation',
            'question': 'SELECT COUNT(*) FROM usuarios WHERE data_criacao > "2023-01-01"',
            'groups': [
                {
                    'id': 1,
                    'sql_model_name': 'GPT-4o-mini',
                    'processing_enabled': False,
                    'processing_model_name': None,
                    'iterations': 4  # 4 testes para testar cancelamento
                }
            ]
        }
        
        print(f"🚀 Iniciando {test_session['groups'][0]['iterations']} testes...")
        
        # Inicia testes em background
        test_task = asyncio.create_task(
            runner.run_test_session(
                test_session,
                validation_method='keyword',
                expected_content='COUNT'
            )
        )
        
        # Aguarda 10 segundos e tenta cancelar um teste
        await asyncio.sleep(10)
        
        status = runner.get_status()
        running_tests = status.get('running_tests_details', [])
        
        if running_tests:
            # Cancela o primeiro teste em execução
            first_test = running_tests[0]
            thread_id = first_test.get('thread_id')
            
            if thread_id:
                print(f"🚫 Tentando cancelar teste {thread_id}...")
                cancelled = runner.cancel_current_test(thread_id)
                
                if cancelled:
                    print(f"✅ Teste {thread_id} marcado para cancelamento")
                    
                    # Aguarda mais 5 segundos para ver se realmente parou
                    await asyncio.sleep(5)
                    
                    new_status = runner.get_status()
                    new_running = new_status.get('running_tests_details', [])
                    
                    # Verifica se o teste foi realmente removido
                    still_running = any(t.get('thread_id') == thread_id for t in new_running)
                    
                    if not still_running:
                        print(f"✅ Teste {thread_id} realmente parou!")
                        return True
                    else:
                        print(f"❌ Teste {thread_id} ainda está executando...")
                        return False
                else:
                    print(f"❌ Falha ao cancelar teste {thread_id}")
                    return False
            else:
                print("❌ Não foi possível obter thread_id")
                return False
        else:
            print("❌ Nenhum teste em execução para cancelar")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste AgentGraph: {e}")
        return False

async def test_timeout_behavior():
    """Testa comportamento de timeout"""
    print("\n🧪 TESTE DE TIMEOUT")
    print("=" * 50)
    
    async def slow_task(duration):
        """Task que demora mais que o timeout"""
        print(f"🐌 Iniciando task lenta ({duration}s)...")
        start = time.time()
        
        try:
            await asyncio.sleep(duration)
            elapsed = time.time() - start
            print(f"✅ Task lenta concluída em {elapsed:.2f}s")
            return "concluida"
        except asyncio.CancelledError:
            elapsed = time.time() - start
            print(f"🚫 Task lenta cancelada após {elapsed:.2f}s")
            raise
    
    # Testa timeout de 3 segundos em task de 8 segundos
    try:
        start_time = time.time()
        result = await asyncio.wait_for(slow_task(8), timeout=3)
        print(f"❌ Timeout não funcionou! Resultado: {result}")
        return False
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        print(f"✅ Timeout funcionou em {elapsed:.2f}s (esperado: ~3s)")
        
        if 2.8 <= elapsed <= 3.2:  # Margem de erro
            print("✅ Tempo de timeout correto!")
            return True
        else:
            print(f"⚠️ Tempo de timeout impreciso (esperado: 3s, real: {elapsed:.2f}s)")
            return False

async def main():
    """Função principal"""
    print("🔧 TESTE COMPLETO DE CANCELAMENTO REAL")
    print("=" * 60)
    
    tests = [
        ("Cancelamento Básico", test_real_cancellation),
        ("Timeout Automático", test_timeout_behavior),
        ("AgentGraph Cancelamento", test_agentgraph_cancellation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            result = await test_func()
            
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
        print("🎉 CANCELAMENTO FUNCIONANDO PERFEITAMENTE!")
    elif passed >= 2:
        print("⚠️ Cancelamento parcialmente funcionando")
    else:
        print("❌ Problemas sérios de cancelamento")
    
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
