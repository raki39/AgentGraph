"""
Sistema de Sessões Temporárias para AgentGraph
Gerencia sessões de usuários com Redis, TTL e isolamento completo
"""
import uuid
import json
import time
import os
import shutil
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import redis

from utils.config import (
    REDIS_HOST, 
    REDIS_PORT, 
    is_docker_environment,
    get_environment_info
)

class SessionManager:
    """
    Gerenciador de sessões temporárias com Redis
    Suporta TTL, renovação automática e limpeza de recursos
    """
    
    def __init__(self):
        self.redis_client = None
        self.session_ttl = 24 * 60 * 60  # 24 horas em segundos
        self.max_sessions_per_ip = 5  # Limite por IP
        self.max_session_size_mb = 200  # Limite de espaço por sessão
        self.sessions_db = 2  # Database Redis específico para sessões
        self._initialize_redis()
        self._setup_session_directories()
    
    def _initialize_redis(self):
        """Inicializa conexão Redis para sessões"""
        max_retries = 10
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self.redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=self.sessions_db,  # DB separado para sessões
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )

                # Testa conexão
                self.redis_client.ping()

                env_info = get_environment_info()
                logging.info(f"[SESSION_MANAGER] Redis conectado para sessões em {env_info['environment']}: {REDIS_HOST}:{REDIS_PORT}/db{self.sessions_db}")
                return

            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"[SESSION_MANAGER] Tentativa {attempt + 1}/{max_retries} falhou, aguardando Redis... ({e})")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 5)  # Backoff exponencial
                else:
                    logging.error(f"[SESSION_MANAGER] Erro ao conectar Redis para sessões após {max_retries} tentativas: {e}")
                    raise
    
    def _setup_session_directories(self):
        """Configura diretórios base para sessões"""
        try:
            if is_docker_environment():
                # Docker: usar volume montado
                self.sessions_base_dir = "/data/sessions"
            else:
                # Windows: usar diretório local
                self.sessions_base_dir = os.path.join(os.getcwd(), "data", "sessions")
            
            # Criar diretório base se não existir
            os.makedirs(self.sessions_base_dir, exist_ok=True)
            
            logging.info(f"[SESSION_MANAGER] Diretório base de sessões: {self.sessions_base_dir}")
            
        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao configurar diretórios: {e}")
            raise
    
    def create_session(self, client_ip: str = "unknown") -> str:
        """
        Cria nova sessão com ID único
        
        Args:
            client_ip: IP do cliente (para limites)
            
        Returns:
            session_id: ID único da sessão
        """
        try:
            # Verifica limite de sessões por IP
            if not self._check_ip_limit(client_ip):
                raise Exception(f"Limite de {self.max_sessions_per_ip} sessões por IP excedido")
            
            # Gera ID único
            session_id = str(uuid.uuid4())
            
            # Configuração padrão da sessão
            session_data = {
                "session_id": session_id,
                "client_ip": client_ip,
                "created_at": time.time(),
                "last_seen": time.time(),
                "version": 1,
                
                # Configurações padrão do agente
                "selected_model": "gpt-4o-mini",
                "top_k": 10,
                "connection_type": "csv",
                "db_uri": None,  # Será definido no upload
                "include_tables_key": "*",
                "advanced_mode": False,
                "processing_enabled": False,
                "processing_model": "gpt-4o-mini",
                "question_refinement_enabled": False,
                "single_table_mode": False,
                "selected_table": None,
                
                # Metadados
                "total_queries": 0,
                "last_query": None,
                "session_size_mb": 0.0
            }
            
            # Salva no Redis com TTL
            session_key = f"session:{session_id}"
            self.redis_client.setex(
                session_key, 
                self.session_ttl, 
                json.dumps(session_data, default=str)
            )
            
            # Cria diretório da sessão
            session_dir = self._get_session_directory(session_id)
            os.makedirs(session_dir, exist_ok=True)
            
            # Registra IP para controle de limite
            ip_key = f"ip_sessions:{client_ip}"
            self.redis_client.sadd(ip_key, session_id)
            self.redis_client.expire(ip_key, self.session_ttl)
            
            logging.info(f"[SESSION_MANAGER] Nova sessão criada: {session_id} (IP: {client_ip})")
            return session_id
            
        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao criar sessão: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera dados da sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Dados da sessão ou None se não encontrada/expirada
        """
        try:
            if not session_id:
                return None
                
            session_key = f"session:{session_id}"
            session_data = self.redis_client.get(session_key)
            
            if not session_data:
                logging.warning(f"[SESSION_MANAGER] Sessão não encontrada ou expirada: {session_id}")
                return None
            
            return json.loads(session_data)
            
        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao recuperar sessão {session_id}: {e}")
            return None
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Atualiza dados da sessão e renova TTL
        
        Args:
            session_id: ID da sessão
            updates: Dados para atualizar
            
        Returns:
            True se atualizou com sucesso
        """
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                return False
            
            # Atualiza dados
            session_data.update(updates)
            session_data["last_seen"] = time.time()
            
            # Incrementa versão se houve mudança significativa
            config_keys = ["selected_model", "top_k", "connection_type", "db_uri", "include_tables_key"]
            if any(key in updates for key in config_keys):
                session_data["version"] = session_data.get("version", 1) + 1
                logging.info(f"[SESSION_MANAGER] Configuração alterada, versão incrementada para {session_data['version']}")
            
            # Salva com TTL renovado
            session_key = f"session:{session_id}"
            self.redis_client.setex(
                session_key, 
                self.session_ttl, 
                json.dumps(session_data, default=str)
            )
            
            return True
            
        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao atualizar sessão {session_id}: {e}")
            return False
    
    def renew_session(self, session_id: str) -> bool:
        """
        Renova TTL da sessão (chamado a cada request)
        
        Args:
            session_id: ID da sessão
            
        Returns:
            True se renovada com sucesso
        """
        try:
            session_key = f"session:{session_id}"
            
            # Verifica se sessão existe
            if not self.redis_client.exists(session_key):
                return False
            
            # Renova TTL
            self.redis_client.expire(session_key, self.session_ttl)
            
            # Atualiza last_seen
            self.update_session(session_id, {"last_seen": time.time()})
            
            return True
            
        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao renovar sessão {session_id}: {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """
        Remove sessão e limpa recursos

        Args:
            session_id: ID da sessão

        Returns:
            True se removida com sucesso
        """
        try:
            # Remove do Redis
            session_key = f"session:{session_id}"
            self.redis_client.delete(session_key)

            # Remove diretório da sessão
            session_dir = self._get_session_directory(session_id)
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                logging.info(f"[SESSION_MANAGER] Diretório removido: {session_dir}")

            logging.info(f"[SESSION_MANAGER] Sessão removida: {session_id}")
            return True

        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao remover sessão {session_id}: {e}")
            return False

    def _check_ip_limit(self, client_ip: str) -> bool:
        """Verifica se IP não excedeu limite de sessões"""
        try:
            ip_key = f"ip_sessions:{client_ip}"
            session_count = self.redis_client.scard(ip_key)
            return session_count < self.max_sessions_per_ip
        except:
            return True  # Em caso de erro, permite criação

    def _get_session_directory(self, session_id: str) -> str:
        """Retorna caminho do diretório da sessão"""
        return os.path.join(self.sessions_base_dir, session_id)

    def get_session_db_path(self, session_id: str) -> str:
        """
        Retorna caminho do banco SQLite da sessão

        Args:
            session_id: ID da sessão

        Returns:
            Caminho absoluto para o arquivo db.db da sessão
        """
        session_dir = self._get_session_directory(session_id)
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
        return f"sqlite:///{db_path}"

    def get_session_upload_dir(self, session_id: str) -> str:
        """
        Retorna diretório de uploads da sessão

        Args:
            session_id: ID da sessão

        Returns:
            Caminho do diretório de uploads
        """
        session_dir = self._get_session_directory(session_id)
        upload_dir = os.path.join(session_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    def calculate_session_size(self, session_id: str) -> float:
        """
        Calcula tamanho da sessão em MB

        Args:
            session_id: ID da sessão

        Returns:
            Tamanho em MB
        """
        try:
            session_dir = self._get_session_directory(session_id)
            if not os.path.exists(session_dir):
                return 0.0

            total_size = 0
            for dirpath, dirnames, filenames in os.walk(session_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            size_mb = total_size / (1024 * 1024)

            # Atualiza no Redis
            self.update_session(session_id, {"session_size_mb": size_mb})

            return size_mb

        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao calcular tamanho da sessão {session_id}: {e}")
            return 0.0

    def cleanup_expired_sessions(self) -> int:
        """
        Remove sessões expiradas e seus recursos

        Returns:
            Número de sessões removidas
        """
        try:
            removed_count = 0

            # Busca todas as chaves de sessão
            session_keys = self.redis_client.keys("session:*")

            for session_key in session_keys:
                # Verifica se ainda existe (não expirou)
                if not self.redis_client.exists(session_key):
                    # Extrai session_id da chave
                    session_id = session_key.replace("session:", "")

                    # Remove diretório órfão
                    session_dir = self._get_session_directory(session_id)
                    if os.path.exists(session_dir):
                        shutil.rmtree(session_dir)
                        logging.info(f"[SESSION_CLEANUP] Diretório órfão removido: {session_id}")
                        removed_count += 1

            # Remove diretórios órfãos (sem sessão no Redis)
            if os.path.exists(self.sessions_base_dir):
                for item in os.listdir(self.sessions_base_dir):
                    item_path = os.path.join(self.sessions_base_dir, item)
                    if os.path.isdir(item_path):
                        session_key = f"session:{item}"
                        if not self.redis_client.exists(session_key):
                            shutil.rmtree(item_path)
                            logging.info(f"[SESSION_CLEANUP] Diretório órfão removido: {item}")
                            removed_count += 1

            if removed_count > 0:
                logging.info(f"[SESSION_CLEANUP] {removed_count} sessões expiradas removidas")

            return removed_count

        except Exception as e:
            logging.error(f"[SESSION_CLEANUP] Erro na limpeza: {e}")
            return 0

    def get_active_sessions_count(self) -> int:
        """Retorna número de sessões ativas"""
        try:
            return len(self.redis_client.keys("session:*"))
        except:
            return 0

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas das sessões

        Returns:
            Dicionário com estatísticas
        """
        try:
            active_sessions = self.get_active_sessions_count()

            # Calcula tamanho total
            total_size_mb = 0.0
            if os.path.exists(self.sessions_base_dir):
                for item in os.listdir(self.sessions_base_dir):
                    item_path = os.path.join(self.sessions_base_dir, item)
                    if os.path.isdir(item_path):
                        for dirpath, dirnames, filenames in os.walk(item_path):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                if os.path.exists(filepath):
                                    total_size_mb += os.path.getsize(filepath)
                total_size_mb = total_size_mb / (1024 * 1024)

            return {
                "active_sessions": active_sessions,
                "total_size_mb": round(total_size_mb, 2),
                "sessions_base_dir": self.sessions_base_dir,
                "session_ttl_minutes": self.session_ttl // 60,
                "max_sessions_per_ip": self.max_sessions_per_ip,
                "max_session_size_mb": self.max_session_size_mb
            }

        except Exception as e:
            logging.error(f"[SESSION_MANAGER] Erro ao obter estatísticas: {e}")
            return {}

# Instância global do gerenciador de sessões
_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """Retorna instância singleton do gerenciador de sessões"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

def reset_session_manager():
    """Reseta o gerenciador de sessões"""
    global _session_manager
    _session_manager = None
