"""
Teste da nova arquitetura de nós
"""
import asyncio
import logging
import pandas as pd
from utils.object_manager import get_object_manager, reset_object_manager
from nodes.csv_processing_node import csv_processing_node
from nodes.database_node import create_database_from_dataframe_node, get_database_sample_node
from agents.sql_agent import SQLAgentManager
from agents.tools import CacheManager
from utils.database import create_sql_database

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_csv_processing():
    """Testa processamento de CSV genérico"""
    print("\n=== Teste de Processamento CSV ===")
    
    # Reset do gerenciador de objetos
    reset_object_manager()
    
    # Estado inicial
    state = {
        "file_path": "tabela.csv",
        "success": False,
        "message": "",
        "csv_data_sample": {},
        "column_info": {},
        "processing_stats": {}
    }
    
    # Executa processamento
    result = await csv_processing_node(state)
    
    print(f"Sucesso: {result['success']}")
    print(f"Mensagem: {result['message']}")
    print(f"Estatísticas: {result.get('processing_stats', {})}")
    
    if result['success']:
        print(f"Colunas detectadas: {result['csv_data_sample']['columns']}")
        print(f"Tipos detectados: {result['column_info']['detected_types']}")
    
    return result

async def test_database_creation(csv_result):
    """Testa criação de banco de dados"""
    print("\n=== Teste de Criação de Banco ===")
    
    if not csv_result['success']:
        print("Pulando teste de banco - CSV falhou")
        return None
    
    # Executa criação do banco
    db_result = await create_database_from_dataframe_node(csv_result)
    
    print(f"Sucesso: {db_result['success']}")
    print(f"Mensagem: {db_result['message']}")
    
    if db_result['success']:
        print(f"Info do banco: {db_result['database_info']}")
    
    return db_result

async def test_agent_creation(db_result):
    """Testa criação do agente SQL"""
    print("\n=== Teste de Criação do Agente ===")
    
    if not db_result or not db_result['success']:
        print("Pulando teste de agente - banco falhou")
        return None
    
    try:
        obj_manager = get_object_manager()
        
        # Recupera objetos
        db = obj_manager.get_object(db_result['db_id'])
        if not db:
            print("Erro: Objeto DB não encontrado")
            return None
        
        # Cria agente SQL
        sql_agent = SQLAgentManager(db)
        
        # Armazena agente
        agent_id = obj_manager.store_sql_agent(sql_agent)
        
        print(f"Agente criado com ID: {agent_id}")
        print(f"Info do agente: {sql_agent.get_agent_info()}")
        
        return {"agent_id": agent_id, "success": True}
        
    except Exception as e:
        print(f"Erro ao criar agente: {e}")
        return None

async def test_database_sample(db_result):
    """Testa obtenção de amostra do banco"""
    print("\n=== Teste de Amostra do Banco ===")
    
    if not db_result or not db_result['success']:
        print("Pulando teste de amostra - banco falhou")
        return None
    
    # Estado para amostra
    state = {
        "engine_id": db_result['engine_id']
    }
    
    # Executa obtenção de amostra
    sample_result = await get_database_sample_node(state)
    
    if sample_result.get('db_sample_dict'):
        sample_dict = sample_result['db_sample_dict']
        print(f"Amostra obtida: {sample_dict['shape']} registros")
        print(f"Colunas: {sample_dict['columns']}")
        print(f"Primeiros dados: {sample_dict['data'][:2]}")
    else:
        print("Erro ao obter amostra")
    
    return sample_result

async def test_object_manager():
    """Testa gerenciador de objetos"""
    print("\n=== Teste do Gerenciador de Objetos ===")
    
    obj_manager = get_object_manager()
    stats = obj_manager.get_stats()
    
    print(f"Estatísticas do gerenciador: {stats}")
    
    # Testa armazenamento de cache
    cache_manager = CacheManager()
    cache_id = obj_manager.store_cache_manager(cache_manager)
    
    print(f"Cache manager armazenado com ID: {cache_id}")
    
    # Testa recuperação
    recovered_cache = obj_manager.get_cache_manager(cache_id)
    print(f"Cache recuperado: {recovered_cache is not None}")
    
    return True

async def main():
    """Função principal de teste"""
    print("🧪 Iniciando testes da nova arquitetura...")
    
    try:
        # Teste 1: Gerenciador de objetos
        await test_object_manager()
        
        # Teste 2: Processamento CSV
        csv_result = await test_csv_processing()
        
        # Teste 3: Criação de banco
        db_result = await test_database_creation(csv_result)
        
        # Teste 4: Criação de agente
        agent_result = await test_agent_creation(db_result)
        
        # Teste 5: Amostra do banco
        sample_result = await test_database_sample(db_result)
        
        print("\n✅ Todos os testes concluídos!")
        
        # Estatísticas finais
        obj_manager = get_object_manager()
        final_stats = obj_manager.get_stats()
        print(f"Estatísticas finais: {final_stats}")
        
    except Exception as e:
        print(f"❌ Erro nos testes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
