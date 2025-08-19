"""
Utilitários para gerenciamento de paths e diretórios por sessão
Garante consistência entre Windows e Docker
"""
import os
import logging
from typing import Dict, Any, Optional
from utils.config import is_docker_environment

class SessionPaths:
    """
    Gerenciador de paths consistentes para sessões
    Funciona tanto no Windows quanto no Docker
    """
    
    def __init__(self):
        self.base_dir = self._get_base_directory()
        self._ensure_base_structure()
    
    def _get_base_directory(self) -> str:
        """
        Determina diretório base baseado no ambiente
        
        Returns:
            Caminho do diretório base
        """
        if is_docker_environment():
            # Docker: usar volume montado
            return "/data"
        else:
            # Windows: usar diretório local
            return os.path.join(os.getcwd(), "data")
    
    def _ensure_base_structure(self):
        """Garante que estrutura base existe"""
        try:
            # Cria diretórios base
            directories = [
                self.base_dir,
                os.path.join(self.base_dir, "sessions"),
                os.path.join(self.base_dir, "temp"),
                os.path.join(self.base_dir, "backups")
            ]
            
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
            
            logging.info(f"[SESSION_PATHS] Estrutura base criada em: {self.base_dir}")
            
        except Exception as e:
            logging.error(f"[SESSION_PATHS] Erro ao criar estrutura base: {e}")
            raise
    
    def get_session_directory(self, session_id: str) -> str:
        """
        Retorna diretório da sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Caminho do diretório da sessão
        """
        return os.path.join(self.base_dir, "sessions", session_id)
    
    def get_session_db_path(self, session_id: str) -> str:
        """
        Retorna caminho do banco SQLite da sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Caminho absoluto do arquivo db.db
        """
        session_dir = self.get_session_directory(session_id)
        return os.path.join(session_dir, "db.db")
    
    def get_session_db_uri(self, session_id: str) -> str:
        """
        Retorna URI do banco SQLite da sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            URI SQLite para conexão
        """
        db_path = self.get_session_db_path(session_id)
        # Normaliza path para URI (sempre usar forward slashes)
        normalized_path = db_path.replace("\\", "/")
        return f"sqlite:///{normalized_path}"
    
    def get_session_upload_dir(self, session_id: str) -> str:
        """
        Retorna diretório de uploads da sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Caminho do diretório de uploads
        """
        session_dir = self.get_session_directory(session_id)
        upload_dir = os.path.join(session_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir
    
    def get_session_temp_dir(self, session_id: str) -> str:
        """
        Retorna diretório temporário da sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Caminho do diretório temporário
        """
        session_dir = self.get_session_directory(session_id)
        temp_dir = os.path.join(session_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir
    
    def create_session_structure(self, session_id: str) -> Dict[str, str]:
        """
        Cria estrutura completa de diretórios para sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Dicionário com paths criados
        """
        try:
            session_dir = self.get_session_directory(session_id)
            
            # Cria diretórios da sessão
            directories = {
                "session_dir": session_dir,
                "uploads_dir": os.path.join(session_dir, "uploads"),
                "temp_dir": os.path.join(session_dir, "temp"),
                "cache_dir": os.path.join(session_dir, "cache")
            }
            
            for name, path in directories.items():
                os.makedirs(path, exist_ok=True)
            
            # Adiciona paths de arquivos
            directories.update({
                "db_path": self.get_session_db_path(session_id),
                "db_uri": self.get_session_db_uri(session_id)
            })
            
            logging.info(f"[SESSION_PATHS] Estrutura criada para sessão: {session_id}")
            return directories
            
        except Exception as e:
            logging.error(f"[SESSION_PATHS] Erro ao criar estrutura para {session_id}: {e}")
            raise
    
    def validate_session_paths(self, session_id: str) -> bool:
        """
        Valida se paths da sessão são válidos e acessíveis
        
        Args:
            session_id: ID da sessão
            
        Returns:
            True se paths são válidos
        """
        try:
            session_dir = self.get_session_directory(session_id)
            
            # Verifica se diretório existe
            if not os.path.exists(session_dir):
                return False
            
            # Verifica se é possível escrever
            test_file = os.path.join(session_dir, ".test_write")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except:
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"[SESSION_PATHS] Erro ao validar paths para {session_id}: {e}")
            return False
    
    def get_session_size(self, session_id: str) -> float:
        """
        Calcula tamanho da sessão em MB
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Tamanho em MB
        """
        try:
            session_dir = self.get_session_directory(session_id)
            if not os.path.exists(session_dir):
                return 0.0
            
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(session_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            
            return total_size / (1024 * 1024)  # Converte para MB
            
        except Exception as e:
            logging.error(f"[SESSION_PATHS] Erro ao calcular tamanho para {session_id}: {e}")
            return 0.0
    
    def cleanup_session_directory(self, session_id: str) -> bool:
        """
        Remove diretório da sessão e todos os arquivos
        
        Args:
            session_id: ID da sessão
            
        Returns:
            True se removido com sucesso
        """
        try:
            import shutil
            
            session_dir = self.get_session_directory(session_id)
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                logging.info(f"[SESSION_PATHS] Diretório removido: {session_dir}")
                return True
            
            return True  # Já não existe
            
        except Exception as e:
            logging.error(f"[SESSION_PATHS] Erro ao remover diretório para {session_id}: {e}")
            return False
    
    def get_environment_info(self) -> Dict[str, Any]:
        """
        Retorna informações do ambiente atual
        
        Returns:
            Dicionário com informações do ambiente
        """
        return {
            "environment": "docker" if is_docker_environment() else "windows",
            "base_dir": self.base_dir,
            "sessions_dir": os.path.join(self.base_dir, "sessions"),
            "is_docker": is_docker_environment(),
            "os_name": os.name,
            "cwd": os.getcwd()
        }

# Instância global
_session_paths: Optional[SessionPaths] = None

def get_session_paths() -> SessionPaths:
    """Retorna instância singleton do gerenciador de paths"""
    global _session_paths
    if _session_paths is None:
        _session_paths = SessionPaths()
    return _session_paths

def reset_session_paths():
    """Reseta o gerenciador de paths"""
    global _session_paths
    _session_paths = None
