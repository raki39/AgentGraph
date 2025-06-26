"""
Teste de performance e correção de tipos para processamento CSV
"""
import asyncio
import time
import pandas as pd
import numpy as np
import logging
from nodes.csv_processing_node import (
    detect_column_types, 
    process_dataframe_generic,
    analyze_numeric_column,
    convert_to_int_optimized,
    convert_to_float_optimized
)

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_test_dataframe(rows: int = 100000) -> pd.DataFrame:
    """Cria DataFrame de teste com vários tipos de dados"""
    np.random.seed(42)
    
    data = {
        # Inteiros puros
        'int_puro': np.random.randint(1, 1000, rows),
        
        # Floats puros  
        'float_puro': np.random.uniform(1.0, 1000.0, rows),
        
        # Inteiros como texto
        'int_como_texto': [str(x) for x in np.random.randint(1, 1000, rows)],
        
        # Floats como texto com vírgula (formato brasileiro)
        'float_virgula': [f"{x:.2f}".replace('.', ',') for x in np.random.uniform(1.0, 1000.0, rows)],
        
        # Floats como texto com ponto
        'float_ponto': [f"{x:.2f}" for x in np.random.uniform(1.0, 1000.0, rows)],
        
        # Dados mistos (problemáticos)
        'dados_mistos': ['123', '45.67', 'texto', '89,12', '-', '', 'NULL'] * (rows // 7 + 1),
        
        # Datas (usando ciclo para evitar overflow)
        'datas': [f"{(i % 28) + 1:02d}/{((i // 28) % 12) + 1:02d}/202{(i // 336) % 5}" for i in range(rows)],
        
        # Texto puro
        'texto': [f'produto_{i}' for i in range(rows)],
        
        # Valores com problemas (que causavam os warnings)
        'problematico_int': ['123.45', '67.89', '90', 'texto', ''] * (rows // 5 + 1),
        'problematico_float': ['123,45', '67.89', 'abc', '90.12', 'NULL'] * (rows // 5 + 1)
    }
    
    # Ajusta tamanhos para ter exatamente 'rows' linhas
    for key in data:
        data[key] = data[key][:rows]
    
    return pd.DataFrame(data)

async def test_numeric_analysis():
    """Testa análise numérica otimizada"""
    print("\n=== Teste de Análise Numérica ===")
    
    # Casos de teste
    test_cases = {
        'inteiros_puros': pd.Series(['1', '2', '3', '4', '5']),
        'floats_puros': pd.Series(['1.5', '2.7', '3.14', '4.0']),
        'floats_virgula': pd.Series(['1,5', '2,7', '3,14', '4,0']),
        'mistos': pd.Series(['1', '2.5', 'texto', '3,7', '']),
        'texto_puro': pd.Series(['abc', 'def', 'ghi']),
        'problematicos': pd.Series(['123.45', 'texto', '', 'NULL', '67,89'])
    }
    
    for name, series in test_cases.items():
        start_time = time.time()
        analysis = analyze_numeric_column(series)
        end_time = time.time()
        
        print(f"\n{name}:")
        print(f"  Dados: {series.tolist()}")
        print(f"  É numérico: {analysis['is_numeric']}")
        print(f"  É inteiro: {analysis['is_integer']}")
        print(f"  Ratio numérico: {analysis['numeric_ratio']:.2f}")
        print(f"  Tempo: {(end_time - start_time)*1000:.2f}ms")

async def test_conversion_functions():
    """Testa funções de conversão otimizadas"""
    print("\n=== Teste de Conversões Otimizadas ===")
    
    # Teste conversão para int
    int_series = pd.Series(['123', '456', '789.0', '90.00', 'texto', ''])
    print(f"\nConversão para int:")
    print(f"Original: {int_series.tolist()}")
    
    start_time = time.time()
    converted_int = convert_to_int_optimized(int_series)
    end_time = time.time()
    
    print(f"Convertido: {converted_int.tolist()}")
    print(f"Tipo: {converted_int.dtype}")
    print(f"Tempo: {(end_time - start_time)*1000:.2f}ms")
    
    # Teste conversão para float
    float_series = pd.Series(['123,45', '67.89', '90', 'texto', 'NULL'])
    print(f"\nConversão para float:")
    print(f"Original: {float_series.tolist()}")
    
    start_time = time.time()
    converted_float = convert_to_float_optimized(float_series)
    end_time = time.time()
    
    print(f"Convertido: {converted_float.tolist()}")
    print(f"Tipo: {converted_float.dtype}")
    print(f"Tempo: {(end_time - start_time)*1000:.2f}ms")

async def test_performance_small():
    """Testa performance com dataset pequeno"""
    print("\n=== Teste de Performance (10K linhas) ===")
    
    df = create_test_dataframe(10000)
    print(f"DataFrame criado: {df.shape}")
    
    # Detecção de tipos
    start_time = time.time()
    column_info = await detect_column_types(df)
    detection_time = time.time() - start_time
    
    print(f"Detecção de tipos: {detection_time:.2f}s")
    print(f"Colunas detectadas:")
    print(f"  Datas: {len(column_info['date_columns'])}")
    print(f"  Numéricas: {len(column_info['numeric_columns'])}")
    print(f"  Texto: {len(column_info['text_columns'])}")
    
    # Processamento
    start_time = time.time()
    processed_df = await process_dataframe_generic(df, column_info)
    processing_time = time.time() - start_time
    
    print(f"Processamento: {processing_time:.2f}s")
    print(f"Tempo total: {detection_time + processing_time:.2f}s")
    
    # Verifica tipos finais
    print(f"\nTipos finais:")
    for col in processed_df.columns:
        print(f"  {col}: {processed_df[col].dtype}")
    
    return detection_time + processing_time

async def test_performance_large():
    """Testa performance com dataset grande"""
    print("\n=== Teste de Performance (100K linhas) ===")
    
    df = create_test_dataframe(100000)
    print(f"DataFrame criado: {df.shape}")
    
    # Detecção de tipos
    start_time = time.time()
    column_info = await detect_column_types(df)
    detection_time = time.time() - start_time
    
    print(f"Detecção de tipos: {detection_time:.2f}s")
    
    # Processamento
    start_time = time.time()
    processed_df = await process_dataframe_generic(df, column_info)
    processing_time = time.time() - start_time
    
    print(f"Processamento: {processing_time:.2f}s")
    print(f"Tempo total: {detection_time + processing_time:.2f}s")
    
    # Performance por linha
    total_time = detection_time + processing_time
    lines_per_second = len(df) / total_time
    print(f"Performance: {lines_per_second:.0f} linhas/segundo")
    
    return total_time

async def test_problematic_columns():
    """Testa colunas que causavam warnings"""
    print("\n=== Teste de Colunas Problemáticas ===")
    
    # Simula colunas que causavam problemas
    problematic_data = {
        'VALOR_ENTRADA_PLANO1': ['123.45', '67.89', '90.12', 'texto', ''],
        'VALOR_PARCELA_PLANO1': ['45,67', '89.12', '123', 'NULL', '-'],
        'TAXA_JUROS_PLANO1': ['5.5', '7,2', '8.0', 'abc', ''],
        'VALOR_MEDIDA': [123.45, 67.89, 90.0, np.nan, 45.67]  # Já float64
    }
    
    df = pd.DataFrame(problematic_data)
    print(f"DataFrame problemático: {df.shape}")
    print(f"Tipos originais:")
    for col in df.columns:
        print(f"  {col}: {df[col].dtype}")
    
    # Processa
    start_time = time.time()
    column_info = await detect_column_types(df)
    processed_df = await process_dataframe_generic(df, column_info)
    end_time = time.time()
    
    print(f"\nProcessamento concluído em {end_time - start_time:.2f}s")
    print(f"Tipos finais:")
    for col in processed_df.columns:
        print(f"  {col}: {processed_df[col].dtype}")
    
    print(f"\nRegras aplicadas:")
    for col, rule in column_info['processing_rules'].items():
        print(f"  {col}: {rule}")

async def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes de performance e correção de tipos...")
    
    try:
        # Teste 1: Análise numérica
        await test_numeric_analysis()
        
        # Teste 2: Funções de conversão
        await test_conversion_functions()
        
        # Teste 3: Colunas problemáticas
        await test_problematic_columns()
        
        # Teste 4: Performance pequena
        small_time = await test_performance_small()
        
        # Teste 5: Performance grande
        large_time = await test_performance_large()
        
        print(f"\n✅ Todos os testes concluídos!")
        print(f"\n📊 Resumo de Performance:")
        print(f"  10K linhas: {small_time:.2f}s")
        print(f"  100K linhas: {large_time:.2f}s")
        print(f"  Estimativa para 1M linhas: {large_time * 10:.2f}s")
        
        # Comparação com performance anterior
        old_time_1m = 600  # 600s que você reportou
        new_time_1m = large_time * 10
        improvement = old_time_1m / new_time_1m
        
        print(f"\n🚀 Melhoria de Performance:")
        print(f"  Antes: {old_time_1m}s para 1M linhas")
        print(f"  Agora: {new_time_1m:.2f}s para 1M linhas")
        print(f"  Melhoria: {improvement:.1f}x mais rápido!")
        
    except Exception as e:
        print(f"❌ Erro nos testes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
