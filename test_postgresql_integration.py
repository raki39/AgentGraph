"""
Teste de integração para conexão PostgreSQL
"""
import asyncio
import logging
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nodes.postgresql_connection_node import postgresql_connection_node, test_postgresql_connection_node
from nodes.connection_selection_node import connection_selection_node, validate_connection_input_node
from utils.validation import validate_postgresql_config, sanitize_postgresql_config
from utils.object_manager import get_object_manager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_postgresql_validation():
    """Testa validação de configuração PostgreSQL"""
    print("\n=== Teste de Validação PostgreSQL ===")
    
    # Teste 1: Configuração válida
    valid_config = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "username": "test_user",
        "password": "test_pass"
    }
    
    is_valid, error = validate_postgresql_config(valid_config)
    print(f"Configuração válida: {is_valid} (erro: {error})")
    assert is_valid, f"Configuração válida falhou: {error}"
    
    # Teste 2: Configuração inválida - porta
    invalid_config = valid_config.copy()
    invalid_config["port"] = "invalid"
    
    is_valid, error = validate_postgresql_config(invalid_config)
    print(f"Configuração inválida (porta): {is_valid} (erro: {error})")
    assert not is_valid, "Deveria falhar com porta inválida"
    
    # Teste 3: Campo ausente
    incomplete_config = valid_config.copy()
    del incomplete_config["host"]
    
    is_valid, error = validate_postgresql_config(incomplete_config)
    print(f"Configuração incompleta: {is_valid} (erro: {error})")
    assert not is_valid, "Deveria falhar com campo ausente"
    
    print("✅ Todos os testes de validação passaram!")

async def test_connection_selection_node():
    """Testa nó de seleção de conexão"""
    print("\n=== Teste de Nó de Seleção de Conexão ===")
    
    # Teste 1: Tipo CSV
    csv_state = {
        "connection_type": "csv",
        "file_path": "tabela.csv"  # Arquivo padrão
    }
    
    result = await connection_selection_node(csv_state)
    print(f"Seleção CSV: {result.get('connection_type')} - Sucesso: {result.get('connection_success')}")
    assert result.get("connection_type") == "csv"
    assert result.get("connection_success") == True
    
    # Teste 2: Tipo PostgreSQL
    pg_state = {
        "connection_type": "postgresql",
        "postgresql_config": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_pass"
        }
    }
    
    result = await connection_selection_node(pg_state)
    print(f"Seleção PostgreSQL: {result.get('connection_type')} - Sucesso: {result.get('connection_success')}")
    assert result.get("connection_type") == "postgresql"
    assert result.get("connection_success") == True
    
    print("✅ Testes de seleção de conexão passaram!")

async def test_validation_node():
    """Testa nó de validação de entrada"""
    print("\n=== Teste de Nó de Validação ===")
    
    # Teste 1: Validação PostgreSQL válida
    valid_state = {
        "connection_type": "postgresql",
        "postgresql_config": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_pass"
        }
    }
    
    result = await validate_connection_input_node(valid_state)
    print(f"Validação PostgreSQL válida: Sucesso: {result.get('connection_success')}")
    assert result.get("connection_success") == True
    
    # Teste 2: Validação PostgreSQL inválida
    invalid_state = {
        "connection_type": "postgresql",
        "postgresql_config": {
            "host": "",  # Host vazio
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_pass"
        }
    }
    
    result = await validate_connection_input_node(invalid_state)
    print(f"Validação PostgreSQL inválida: Sucesso: {result.get('connection_success')} - Erro: {result.get('connection_error')}")
    assert result.get("connection_success") == False
    
    print("✅ Testes de validação passaram!")

async def test_postgresql_connection_mock():
    """Testa conexão PostgreSQL (mock - sem servidor real)"""
    print("\n=== Teste de Conexão PostgreSQL (Mock) ===")
    
    # Teste com configuração que falhará (servidor inexistente)
    mock_state = {
        "postgresql_config": {
            "host": "nonexistent-server.local",
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_pass"
        }
    }
    
    result = await postgresql_connection_node(mock_state)
    print(f"Conexão mock: Sucesso: {result.get('success')} - Mensagem: {result.get('message')}")
    
    # Deve falhar mas com mensagem amigável
    assert result.get("success") == False
    assert "❌" in result.get("message", "")
    
    print("✅ Teste de conexão mock passou!")

def test_sanitization():
    """Testa sanitização de configuração"""
    print("\n=== Teste de Sanitização ===")
    
    dirty_config = {
        "host": "  localhost  ",
        "port": "5432",
        "database": "  test_db  ",
        "username": "  test_user  ",
        "password": "test_pass"
    }
    
    clean_config = sanitize_postgresql_config(dirty_config)
    
    print(f"Host sanitizado: '{clean_config['host']}'")
    print(f"Porta sanitizada: {clean_config['port']} (tipo: {type(clean_config['port'])})")
    print(f"Database sanitizado: '{clean_config['database']}'")
    
    assert clean_config["host"] == "localhost"
    assert clean_config["port"] == 5432
    assert clean_config["database"] == "test_db"
    assert clean_config["username"] == "test_user"
    
    print("✅ Teste de sanitização passou!")

async def test_object_manager_integration():
    """Testa integração com ObjectManager"""
    print("\n=== Teste de Integração ObjectManager ===")
    
    obj_manager = get_object_manager()
    
    # Testa armazenamento de metadados
    test_metadata = {
        "type": "postgresql",
        "host": "localhost",
        "database": "test_db",
        "connection_time": 1.5
    }
    
    connection_id = "test_connection_123"
    stored_id = obj_manager.store_connection_metadata(connection_id, test_metadata)
    
    print(f"Metadados armazenados com ID: {stored_id}")
    assert stored_id == connection_id
    
    # Recupera metadados
    retrieved_metadata = obj_manager.get_connection_metadata(connection_id)
    print(f"Metadados recuperados: {retrieved_metadata}")
    assert retrieved_metadata == test_metadata
    
    # Testa estatísticas
    stats = obj_manager.get_stats()
    print(f"Estatísticas: {stats}")
    assert stats["connection_metadata"] >= 1
    
    print("✅ Teste de integração ObjectManager passou!")

async def run_all_tests():
    """Executa todos os testes"""
    print("🚀 Iniciando testes de integração PostgreSQL...")
    
    try:
        # Testes síncronos
        test_sanitization()
        
        # Testes assíncronos
        await test_postgresql_validation()
        await test_connection_selection_node()
        await test_validation_node()
        await test_postgresql_connection_mock()
        await test_object_manager_integration()
        
        print("\n🎉 Todos os testes passaram com sucesso!")
        print("✅ A implementação PostgreSQL está funcionando corretamente!")
        
    except Exception as e:
        print(f"\n❌ Erro nos testes: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
