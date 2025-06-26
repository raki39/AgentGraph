"""
Teste específico para processamento avançado de datas
"""
import asyncio
import pandas as pd
import logging
from nodes.csv_processing_node import detect_column_types, process_dataframe_generic, process_dates_advanced

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_date_detection():
    """Testa detecção automática de colunas de data"""
    print("\n=== Teste de Detecção de Datas ===")
    
    # Cria DataFrame de teste com vários formatos de data
    test_data = {
        'data_br': ['01/12/2024', '15/06/2023', '30/11/2022', '05/03/2021'],
        'data_iso': ['2024-12-01', '2023-06-15', '2022-11-30', '2021-03-05'],
        'data_us': ['12/01/2024', '06/15/2023', '11/30/2022', '03/05/2021'],
        'data_ponto': ['01.12.2024', '15.06.2023', '30.11.2022', '05.03.2021'],
        'data_hifen': ['01-12-2024', '15-06-2023', '30-11-2022', '05-03-2021'],
        'data_com_hora': ['01/12/2024 14:30:00', '15/06/2023 09:15:30', '30/11/2022 18:45:00', '05/03/2021 12:00:00'],
        'texto_normal': ['produto A', 'produto B', 'produto C', 'produto D'],
        'numeros': [100, 200, 300, 400],
        'data_mista': ['01/12/2024', 'texto', '15/06/2023', 'outro texto']
    }
    
    df = pd.DataFrame(test_data)
    print(f"DataFrame criado com {len(df)} linhas e {len(df.columns)} colunas")
    print(f"Colunas: {list(df.columns)}")
    
    # Detecta tipos
    column_info = await detect_column_types(df)
    
    print(f"\n📊 Resultados da Detecção:")
    print(f"Colunas de data detectadas: {column_info['date_columns']}")
    print(f"Colunas numéricas detectadas: {column_info['numeric_columns']}")
    print(f"Colunas de texto detectadas: {column_info['text_columns']}")
    
    print(f"\n🔧 Regras de Processamento:")
    for col, rule in column_info['processing_rules'].items():
        print(f"  {col}: {rule}")
    
    return column_info, df

async def test_date_processing(column_info, df):
    """Testa processamento das datas detectadas"""
    print("\n=== Teste de Processamento de Datas ===")
    
    # Processa DataFrame
    processed_df = await process_dataframe_generic(df, column_info)
    
    print(f"DataFrame processado:")
    print(f"Tipos originais:")
    for col in df.columns:
        print(f"  {col}: {df[col].dtype}")
    
    print(f"\nTipos após processamento:")
    for col in processed_df.columns:
        print(f"  {col}: {processed_df[col].dtype}")
    
    print(f"\nAmostras de dados processados:")
    for col in column_info['date_columns']:
        if col in processed_df.columns:
            print(f"\n{col}:")
            print(f"  Original: {df[col].head(3).tolist()}")
            print(f"  Processado: {processed_df[col].head(3).tolist()}")
    
    return processed_df

async def test_advanced_date_processing():
    """Testa função específica de processamento avançado"""
    print("\n=== Teste de Processamento Avançado ===")
    
    # Testa vários formatos de data
    test_dates = [
        '01/12/2024',      # BR
        '2024-12-01',      # ISO
        '01-12-2024',      # Hífen
        '01.12.2024',      # Ponto
        '01/12/24',        # Ano curto
        '2024/12/01',      # US ISO
        '01/12/2024 14:30:00',  # Com hora
        'texto inválido',   # Inválido
        '',                # Vazio
        None,              # Nulo
        '32/13/2024'       # Data inválida
    ]
    
    series = pd.Series(test_dates)
    print(f"Série de teste: {test_dates}")
    
    # Processa
    result = await process_dates_advanced(series)
    
    print(f"\nResultados:")
    for i, (original, converted) in enumerate(zip(test_dates, result)):
        status = "✅" if pd.notna(converted) else "❌"
        print(f"  {status} '{original}' → {converted}")
    
    return result

async def test_csv_with_dates():
    """Testa com CSV real contendo datas"""
    print("\n=== Teste com CSV Real ===")
    
    # Cria CSV de teste
    csv_data = """DATA_INICIAL;DATA_FINAL;PRODUTO;PRECO
01/01/2024;31/01/2024;Arroz;15.99
05/02/2024;28/02/2024;Feijão;8.50
10-03-2024;30-03-2024;Óleo;6.99
2024-04-01;2024-04-30;Açúcar;4.50
15.05.2024;31.05.2024;Sal;2.99"""
    
    # Salva CSV temporário
    with open('test_dates.csv', 'w', encoding='utf-8') as f:
        f.write(csv_data)
    
    # Lê CSV
    df = pd.read_csv('test_dates.csv', sep=';')
    print(f"CSV carregado: {df.shape}")
    print(df.head())
    
    # Detecta e processa
    column_info = await detect_column_types(df)
    processed_df = await process_dataframe_generic(df, column_info)
    
    print(f"\nColunas de data detectadas: {column_info['date_columns']}")
    print(f"Dados processados:")
    print(processed_df.head())
    print(f"\nTipos finais:")
    print(processed_df.dtypes)
    
    # Remove arquivo temporário
    import os
    os.remove('test_dates.csv')
    
    return processed_df

async def main():
    """Função principal de teste"""
    print("🧪 Iniciando testes de processamento de datas...")
    
    try:
        # Teste 1: Detecção
        column_info, df = await test_date_detection()
        
        # Teste 2: Processamento
        processed_df = await test_date_processing(column_info, df)
        
        # Teste 3: Função avançada
        result = await test_advanced_date_processing()
        
        # Teste 4: CSV real
        csv_result = await test_csv_with_dates()
        
        print("\n✅ Todos os testes de data concluídos com sucesso!")
        
        # Estatísticas finais
        date_columns_detected = len(column_info['date_columns'])
        total_columns = len(df.columns)
        
        print(f"\n📊 Estatísticas:")
        print(f"  Colunas totais: {total_columns}")
        print(f"  Colunas de data detectadas: {date_columns_detected}")
        print(f"  Taxa de detecção: {date_columns_detected/total_columns*100:.1f}%")
        
    except Exception as e:
        print(f"❌ Erro nos testes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
