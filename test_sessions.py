"""
Script de teste para validar o sistema de sessões temporárias
Testa isolamento entre usuários, cache por sessão e limpeza automática
"""
import asyncio
import logging
import time
import os
import sys
from typing import Dict, Any

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.session_manager import get_session_manager, reset_session_manager
from utils.session_paths import get_session_paths, reset_session_paths
from utils.session_cleanup import get_cleanup_service
from utils.object_manager import get_object_manager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SessionTester:
    """Classe para testar o sistema de sessões"""
    
    def __init__(self):
        self.session_manager = None
        self.session_paths = None
        self.cleanup_service = None
        self.object_manager = None
        
    def setup(self):
        """Inicializa componentes para teste"""
        try:
            # Reset componentes para teste limpo
            reset_session_manager()
            reset_session_paths()
            
            # Inicializa componentes
            self.session_manager = get_session_manager()
            self.session_paths = get_session_paths()
            self.cleanup_service = get_cleanup_service()
            self.object_manager = get_object_manager()
            
            logging.info("✅ Componentes inicializados para teste")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro ao inicializar componentes: {e}")
            return False
    
    def test_session_creation(self) -> bool:
        """Testa criação de sessões"""
        try:
            logging.info("🧪 Testando criação de sessões...")
            
            # Cria múltiplas sessões
            sessions = []
            for i in range(3):
                session_id = self.session_manager.create_session(f"test_ip_{i}")
                sessions.append(session_id)
                logging.info(f"Sessão {i+1} criada: {session_id}")
            
            # Verifica se sessões foram criadas
            for session_id in sessions:
                session_data = self.session_manager.get_session(session_id)
                if not session_data:
                    logging.error(f"❌ Sessão não encontrada: {session_id}")
                    return False
                
                logging.info(f"✅ Sessão válida: {session_id}")
            
            # Verifica estatísticas
            stats = self.session_manager.get_session_stats()
            logging.info(f"📊 Estatísticas: {stats}")
            
            if stats.get("active_sessions", 0) < 3:
                logging.error("❌ Número de sessões ativas incorreto")
                return False
            
            logging.info("✅ Teste de criação de sessões passou")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no teste de criação: {e}")
            return False
    
    def test_session_isolation(self) -> bool:
        """Testa isolamento entre sessões"""
        try:
            logging.info("🧪 Testando isolamento entre sessões...")
            
            # Cria duas sessões
            session1 = self.session_manager.create_session("user1")
            session2 = self.session_manager.create_session("user2")
            
            # Configura sessões com dados diferentes
            config1 = {
                "selected_model": "gpt-4o-mini",
                "connection_type": "csv",
                "top_k": 10,
                "test_data": "session1_data"
            }
            
            config2 = {
                "selected_model": "claude-3-5-sonnet-20241022",
                "connection_type": "postgresql",
                "top_k": 20,
                "test_data": "session2_data"
            }
            
            # Atualiza configurações
            self.session_manager.update_session(session1, config1)
            self.session_manager.update_session(session2, config2)
            
            # Verifica isolamento
            data1 = self.session_manager.get_session(session1)
            data2 = self.session_manager.get_session(session2)
            
            if data1.get("test_data") != "session1_data":
                logging.error("❌ Dados da sessão 1 incorretos")
                return False
            
            if data2.get("test_data") != "session2_data":
                logging.error("❌ Dados da sessão 2 incorretos")
                return False
            
            if data1.get("selected_model") == data2.get("selected_model"):
                logging.error("❌ Configurações não estão isoladas")
                return False
            
            logging.info("✅ Teste de isolamento passou")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no teste de isolamento: {e}")
            return False
    
    def test_session_directories(self) -> bool:
        """Testa criação de diretórios por sessão"""
        try:
            logging.info("🧪 Testando diretórios por sessão...")
            
            # Cria sessão
            session_id = self.session_manager.create_session("test_dirs")
            
            # Cria estrutura de diretórios
            paths = self.session_paths.create_session_structure(session_id)
            
            # Verifica se diretórios foram criados
            for name, path in paths.items():
                if name.endswith("_dir") and not os.path.exists(path):
                    logging.error(f"❌ Diretório não criado: {path}")
                    return False
            
            # Testa escrita em diretório da sessão
            test_file = os.path.join(paths["session_dir"], "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")
            
            if not os.path.exists(test_file):
                logging.error("❌ Não foi possível escrever no diretório da sessão")
                return False
            
            # Calcula tamanho da sessão
            size_mb = self.session_paths.get_session_size(session_id)
            logging.info(f"📁 Tamanho da sessão: {size_mb:.2f} MB")
            
            logging.info("✅ Teste de diretórios passou")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no teste de diretórios: {e}")
            return False
    
    def test_object_manager_sessions(self) -> bool:
        """Testa ObjectManager com sessões"""
        try:
            logging.info("🧪 Testando ObjectManager com sessões...")
            
            # Cria duas sessões
            session1 = self.session_manager.create_session("obj_test1")
            session2 = self.session_manager.create_session("obj_test2")
            
            # Simula objetos para cada sessão
            test_obj1 = {"type": "test", "data": "session1"}
            test_obj2 = {"type": "test", "data": "session2"}
            
            # Armazena objetos por sessão (simulando engines)
            engine_id1 = self.object_manager.store_engine_session(session1, test_obj1)
            engine_id2 = self.object_manager.store_engine_session(session2, test_obj2)
            
            # Verifica isolamento
            retrieved1 = self.object_manager.get_engine_session(session1)
            retrieved2 = self.object_manager.get_engine_session(session2)
            
            if retrieved1.get("data") != "session1":
                logging.error("❌ Objeto da sessão 1 incorreto")
                return False
            
            if retrieved2.get("data") != "session2":
                logging.error("❌ Objeto da sessão 2 incorreto")
                return False
            
            # Verifica estatísticas por sessão
            stats1 = self.object_manager.get_session_stats(session1)
            stats2 = self.object_manager.get_session_stats(session2)
            
            if stats1.get("engines", 0) != 1:
                logging.error("❌ Estatísticas da sessão 1 incorretas")
                return False
            
            if stats2.get("engines", 0) != 1:
                logging.error("❌ Estatísticas da sessão 2 incorretas")
                return False
            
            logging.info("✅ Teste de ObjectManager passou")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no teste de ObjectManager: {e}")
            return False
    
    def test_cleanup(self) -> bool:
        """Testa limpeza automática"""
        try:
            logging.info("🧪 Testando limpeza automática...")
            
            # Cria sessão temporária
            session_id = self.session_manager.create_session("cleanup_test")
            
            # Cria estrutura de diretórios
            self.session_paths.create_session_structure(session_id)
            
            # Verifica se sessão existe
            if not self.session_manager.get_session(session_id):
                logging.error("❌ Sessão não foi criada")
                return False
            
            # Remove sessão manualmente (simula expiração)
            self.session_manager.delete_session(session_id)
            
            # Executa limpeza
            stats = self.cleanup_service.run_cleanup()
            logging.info(f"🧹 Estatísticas de limpeza: {stats}")
            
            # Verifica se sessão foi removida
            if self.session_manager.get_session(session_id):
                logging.error("❌ Sessão não foi removida")
                return False
            
            logging.info("✅ Teste de limpeza passou")
            return True
            
        except Exception as e:
            logging.error(f"❌ Erro no teste de limpeza: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Executa todos os testes"""
        logging.info("🚀 Iniciando testes do sistema de sessões...")
        
        if not self.setup():
            return False
        
        tests = [
            ("Criação de Sessões", self.test_session_creation),
            ("Isolamento entre Sessões", self.test_session_isolation),
            ("Diretórios por Sessão", self.test_session_directories),
            ("ObjectManager com Sessões", self.test_object_manager_sessions),
            ("Limpeza Automática", self.test_cleanup)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logging.info(f"\n{'='*50}")
            logging.info(f"Executando: {test_name}")
            logging.info(f"{'='*50}")
            
            try:
                if test_func():
                    passed += 1
                    logging.info(f"✅ {test_name} - PASSOU")
                else:
                    logging.error(f"❌ {test_name} - FALHOU")
            except Exception as e:
                logging.error(f"❌ {test_name} - ERRO: {e}")
        
        logging.info(f"\n{'='*50}")
        logging.info(f"RESULTADO FINAL: {passed}/{total} testes passaram")
        logging.info(f"{'='*50}")
        
        return passed == total

def main():
    """Função principal"""
    tester = SessionTester()
    success = tester.run_all_tests()
    
    if success:
        logging.info("🎉 Todos os testes passaram! Sistema de sessões está funcionando.")
        return 0
    else:
        logging.error("💥 Alguns testes falharam. Verifique os logs acima.")
        return 1

if __name__ == "__main__":
    exit(main())
