"""
Teste das ULTRA-OTIMIZAÇÕES para processamento CSV
Meta: <60 segundos para 1M linhas
"""
import asyncio
import time
import pandas as pd
import numpy as np
import logging
from nodes.csv_processing_node import (
    detect_column_types, 
    process_dataframe_generic,
    convert_to_int_ultra_optimized,
    convert_to_float_ultra_optimized,
    process_dates_vectorized
)

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_large_test_dataframe(rows: int = 1000000) -> pd.DataFrame:
    """Cria DataFrame de teste grande para simular CSV real"""
    np.random.seed(42)
    
    print(f"Criando DataFrame de teste com {rows:,} linhas...")
    start_time = time.time()
    
    # Simula dados reais com tipos mistos
    data = {}
    
    # 10 colunas de inteiros como string
    for i in range(10):
        data[f'int_col_{i}'] = [str(x) for x in np.random.randint(1, 10000, rows)]
    
    # 10 colunas de floats como string com vírgula
    for i in range(10):
        data[f'float_col_{i}'] = [f"{x:.2f}".replace('.', ',') for x in np.random.uniform(1.0, 1000.0, rows)]
    
    # 5 colunas de datas (usando geração manual para evitar overflow)
    for i in range(5):
        data[f'date_col_{i}'] = [f"{(j % 28) + 1:02d}/{((j // 28) % 12) + 1:02d}/202{(j // 336) % 5}" for j in range(rows)]
    
    # 10 colunas de texto
    for i in range(10):
        data[f'text_col_{i}'] = [f'produto_{j % 1000}' for j in range(rows)]
    
    # 10 colunas problemáticas (mistos)
    for i in range(10):
        mixed = []
        for j in range(rows):
            if j % 100 == 0:
                mixed.append('NULL')
            elif j % 50 == 0:
                mixed.append('')
            elif j % 25 == 0:
                mixed.append('texto')
            else:
                mixed.append(str(np.random.randint(1, 1000)))
        data[f'mixed_col_{i}'] = mixed
    
    df = pd.DataFrame(data)
    
    creation_time = time.time() - start_time
    print(f"DataFrame criado em {creation_time:.2f}s - Shape: {df.shape}")
    
    return df

async def test_ultra_conversion_functions():
    """Testa funções de conversão ultra-otimizadas"""
    print("\n=== Teste de Conversões ULTRA-OTIMIZADAS ===")
    
    # Cria dados de teste
    size = 100000
    int_data = pd.Series([str(x) for x in np.random.randint(1, 1000, size)])
    float_data = pd.Series([f"{x:.2f}".replace('.', ',') for x in np.random.uniform(1.0, 1000.0, size)])
    # Gera datas manualmente para evitar overflow
    date_data = pd.Series([f"{(i % 28) + 1:02d}/{((i // 28) % 12) + 1:02d}/202{(i // 336) % 5}" for i in range(size)])
    
    # Teste conversão int
    print(f"Testando conversão int com {size:,} valores...")
    start_time = time.time()
    result_int = convert_to_int_ultra_optimized(int_data)
    int_time = time.time() - start_time
    print(f"  Conversão int: {int_time:.2f}s ({size/int_time:.0f} valores/s)")
    
    # Teste conversão float
    print(f"Testando conversão float com {size:,} valores...")
    start_time = time.time()
    result_float = convert_to_float_ultra_optimized(float_data)
    float_time = time.time() - start_time
    print(f"  Conversão float: {float_time:.2f}s ({size/float_time:.0f} valores/s)")
    
    # Teste conversão date (com dados menores para evitar overflow)
    date_data_small = pd.Series([f"{(i % 28) + 1:02d}/{((i // 28) % 12) + 1:02d}/202{(i // 336) % 5}" for i in range(size)])
    print(f"Testando conversão date com {size:,} valores...")
    start_time = time.time()
    result_date = process_dates_vectorized(date_data_small)
    date_time = time.time() - start_time
    print(f"  Conversão date: {date_time:.2f}s ({size/date_time:.0f} valores/s)")
    
    return int_time + float_time + date_time

async def test_ultra_performance_100k():
    """Teste com 100K linhas"""
    print("\n=== Teste ULTRA-PERFORMANCE (100K linhas) ===")
    
    df = create_large_test_dataframe(100000)
    
    # Detecção de tipos
    print("Iniciando detecção de tipos...")
    start_time = time.time()
    column_info = await detect_column_types(df, sample_size=500)  # Amostra menor
    detection_time = time.time() - start_time
    print(f"Detecção: {detection_time:.2f}s")
    
    # Processamento
    print("Iniciando processamento ultra-otimizado...")
    start_time = time.time()
    processed_df = await process_dataframe_generic(df, column_info)
    processing_time = time.time() - start_time
    print(f"Processamento: {processing_time:.2f}s")
    
    total_time = detection_time + processing_time
    lines_per_second = len(df) / total_time
    
    print(f"Total: {total_time:.2f}s")
    print(f"Performance: {lines_per_second:.0f} linhas/segundo")
    
    return total_time

async def test_ultra_performance_1m():
    """Teste com 1M linhas - META: <60 segundos"""
    print("\n=== Teste ULTRA-PERFORMANCE (1M linhas) - META: <60s ===")
    
    df = create_large_test_dataframe(1000000)
    
    # Detecção de tipos com amostra muito pequena
    print("Iniciando detecção de tipos (amostra ultra-reduzida)...")
    start_time = time.time()
    column_info = await detect_column_types(df, sample_size=200)  # Amostra mínima
    detection_time = time.time() - start_time
    print(f"Detecção: {detection_time:.2f}s")
    
    # Processamento ultra-otimizado
    print("Iniciando processamento ULTRA-OTIMIZADO...")
    start_time = time.time()
    processed_df = await process_dataframe_generic(df, column_info)
    processing_time = time.time() - start_time
    print(f"Processamento: {processing_time:.2f}s")
    
    total_time = detection_time + processing_time
    lines_per_second = len(df) / total_time
    
    print(f"\n🎯 RESULTADOS FINAIS:")
    print(f"  Total: {total_time:.2f}s")
    print(f"  Performance: {lines_per_second:.0f} linhas/segundo")
    print(f"  Meta (<60s): {'✅ ATINGIDA' if total_time < 60 else '❌ NÃO ATINGIDA'}")
    
    # Comparação com performance anterior
    old_time = 693
    improvement = old_time / total_time
    print(f"  Melhoria vs anterior: {improvement:.1f}x mais rápido")
    
    return total_time

async def benchmark_memory_usage():
    """Testa uso de memória"""
    print("\n=== Benchmark de Memória ===")
    
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    # Memória inicial
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"Memória inicial: {initial_memory:.1f} MB")
    
    # Cria DataFrame
    df = create_large_test_dataframe(500000)
    after_creation = process.memory_info().rss / 1024 / 1024
    print(f"Após criação DF: {after_creation:.1f} MB (+{after_creation - initial_memory:.1f} MB)")
    
    # Processa
    column_info = await detect_column_types(df, sample_size=200)
    processed_df = await process_dataframe_generic(df, column_info)
    after_processing = process.memory_info().rss / 1024 / 1024
    print(f"Após processamento: {after_processing:.1f} MB (+{after_processing - after_creation:.1f} MB)")
    
    return after_processing - initial_memory

async def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes de ULTRA-OTIMIZAÇÃO...")
    print("Meta: Processar 1M linhas em menos de 60 segundos")
    
    try:
        # Teste 1: Funções de conversão
        conversion_time = await test_ultra_conversion_functions()
        
        # Teste 2: Performance 100K
        time_100k = await test_ultra_performance_100k()
        
        # Teste 3: Benchmark de memória
        memory_usage = await benchmark_memory_usage()
        
        # Teste 4: Performance 1M (TESTE PRINCIPAL)
        time_1m = await test_ultra_performance_1m()
        
        print(f"\n🏆 RESUMO FINAL:")
        print(f"  Conversões: {conversion_time:.2f}s")
        print(f"  100K linhas: {time_100k:.2f}s")
        print(f"  1M linhas: {time_1m:.2f}s")
        print(f"  Uso de memória: {memory_usage:.1f} MB")
        
        # Avaliação final
        if time_1m < 60:
            print(f"\n🎉 SUCESSO! Meta de <60s atingida!")
            print(f"   Performance: {1000000/time_1m:.0f} linhas/segundo")
        else:
            print(f"\n⚠️  Meta não atingida. Necessárias mais otimizações.")
            print(f"   Faltam: {time_1m - 60:.1f}s para atingir a meta")
        
    except Exception as e:
        print(f"❌ Erro nos testes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
