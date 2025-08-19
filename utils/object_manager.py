"""
Gerenciador de objetos não-serializáveis para LangGraph
Integrado com Redis para armazenamento de configurações de agentes
Suporte completo a sessões temporárias
"""
import uuid
import json
from typing import Dict, Any, Optional, List
import logging


class ObjectManager:
    """
    Gerencia objetos não-serializáveis que não podem ser incluídos no estado do LangGraph
    Suporte completo a sessões temporárias com isolamento por usuário
    """

    def __init__(self):
        # Estruturas organizadas por sessão
        self._session_objects: Dict[str, Dict[str, Any]] = {}  # session_id -> {type -> {id -> object}}

        # Estruturas globais (compatibilidade com código existente)
        self._objects: Dict[str, Any] = {}
        self._sql_agents: Dict[str, Any] = {}
        self._processing_agents: Dict[str, Any] = {}
        self._engines: Dict[str, Any] = {}
        self._databases: Dict[str, Any] = {}
        self._cache_managers: Dict[str, Any] = {}

        # Mapeamentos
        self._agent_db_mapping: Dict[str, str] = {}
        self._connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Mapeamento de sessões para objetos
        self._session_mappings: Dict[str, Dict[str, str]] = {}  # session_id -> {type -> object_id}

    def _ensure_session_structure(self, session_id: str):
        """Garante que estrutura da sessão existe"""
        if session_id not in self._session_objects:
            self._session_objects[session_id] = {
                "sql_agents": {},
                "processing_agents": {},
                "engines": {},
                "databases": {},
                "cache_managers": {},
                "objects": {}
            }

        if session_id not in self._session_mappings:
            self._session_mappings[session_id] = {}

    def _get_session_key(self, session_id: str, object_type: str, object_id: str) -> str:
        """Gera chave única para objeto da sessão"""
        return f"session:{session_id}:{object_type}:{object_id}"

    # ===== MÉTODOS PARA SESSÕES =====

    def store_sql_agent_session(self, session_id: str, agent: Any, db_id: str = None) -> str:
        """
        Armazena agente SQL para sessão específica

        Args:
            session_id: ID da sessão
            agent: Instância do agente SQL
            db_id: ID do banco associado (opcional)

        Returns:
            ID único do agente
        """
        self._ensure_session_structure(session_id)

        agent_id = str(uuid.uuid4())
        self._session_objects[session_id]["sql_agents"][agent_id] = agent

        # Mapeia agente com seu banco se fornecido
        if db_id:
            session_key = self._get_session_key(session_id, "agent_db_mapping", agent_id)
            self._agent_db_mapping[session_key] = db_id

        # Atualiza mapeamento da sessão
        self._session_mappings[session_id]["sql_agent"] = agent_id

        logging.info(f"[OBJECT_MANAGER] Agente SQL armazenado para sessão {session_id}: {agent_id}")
        return agent_id

    def get_sql_agent_session(self, session_id: str, agent_id: str = None) -> Optional[Any]:
        """
        Recupera agente SQL da sessão

        Args:
            session_id: ID da sessão
            agent_id: ID específico do agente (opcional, usa mapeamento se não fornecido)

        Returns:
            Instância do agente ou None
        """
        if session_id not in self._session_objects:
            return None

        # Se agent_id não fornecido, usa mapeamento da sessão
        if not agent_id:
            agent_id = self._session_mappings.get(session_id, {}).get("sql_agent")
            if not agent_id:
                return None

        return self._session_objects[session_id]["sql_agents"].get(agent_id)

    def store_engine_session(self, session_id: str, engine: Any) -> str:
        """
        Armazena engine para sessão específica

        Args:
            session_id: ID da sessão
            engine: Instância da engine

        Returns:
            ID único da engine
        """
        self._ensure_session_structure(session_id)

        engine_id = str(uuid.uuid4())
        self._session_objects[session_id]["engines"][engine_id] = engine

        # Atualiza mapeamento da sessão
        self._session_mappings[session_id]["engine"] = engine_id

        logging.info(f"[OBJECT_MANAGER] Engine armazenada para sessão {session_id}: {engine_id}")
        return engine_id

    def get_engine_session(self, session_id: str, engine_id: str = None) -> Optional[Any]:
        """
        Recupera engine da sessão

        Args:
            session_id: ID da sessão
            engine_id: ID específico da engine (opcional)

        Returns:
            Instância da engine ou None
        """
        if session_id not in self._session_objects:
            return None

        if not engine_id:
            engine_id = self._session_mappings.get(session_id, {}).get("engine")
            if not engine_id:
                return None

        return self._session_objects[session_id]["engines"].get(engine_id)

    def store_database_session(self, session_id: str, database: Any) -> str:
        """
        Armazena banco de dados para sessão específica

        Args:
            session_id: ID da sessão
            database: Instância do banco

        Returns:
            ID único do banco
        """
        self._ensure_session_structure(session_id)

        db_id = str(uuid.uuid4())
        self._session_objects[session_id]["databases"][db_id] = database

        # Atualiza mapeamento da sessão
        self._session_mappings[session_id]["database"] = db_id

        logging.info(f"[OBJECT_MANAGER] Banco armazenado para sessão {session_id}: {db_id}")
        return db_id

    def get_database_session(self, session_id: str, db_id: str = None) -> Optional[Any]:
        """
        Recupera banco de dados da sessão

        Args:
            session_id: ID da sessão
            db_id: ID específico do banco (opcional)

        Returns:
            Instância do banco ou None
        """
        if session_id not in self._session_objects:
            return None

        if not db_id:
            db_id = self._session_mappings.get(session_id, {}).get("database")
            if not db_id:
                return None

        return self._session_objects[session_id]["databases"].get(db_id)

    def store_cache_manager_session(self, session_id: str, cache_manager: Any) -> str:
        """
        Armazena cache manager para sessão específica

        Args:
            session_id: ID da sessão
            cache_manager: Instância do cache manager

        Returns:
            ID único do cache manager
        """
        self._ensure_session_structure(session_id)

        cache_id = str(uuid.uuid4())
        self._session_objects[session_id]["cache_managers"][cache_id] = cache_manager

        # Atualiza mapeamento da sessão
        self._session_mappings[session_id]["cache_manager"] = cache_id

        logging.info(f"[OBJECT_MANAGER] Cache manager armazenado para sessão {session_id}: {cache_id}")
        return cache_id

    def get_cache_manager_session(self, session_id: str, cache_id: str = None) -> Optional[Any]:
        """
        Recupera cache manager da sessão

        Args:
            session_id: ID da sessão
            cache_id: ID específico do cache (opcional)

        Returns:
            Instância do cache manager ou None
        """
        if session_id not in self._session_objects:
            return None

        if not cache_id:
            cache_id = self._session_mappings.get(session_id, {}).get("cache_manager")
            if not cache_id:
                return None

        return self._session_objects[session_id]["cache_managers"].get(cache_id)

    def get_session_mappings(self, session_id: str) -> Dict[str, str]:
        """
        Retorna mapeamentos de objetos da sessão

        Args:
            session_id: ID da sessão

        Returns:
            Dicionário com mapeamentos {type -> object_id}
        """
        return self._session_mappings.get(session_id, {}).copy()

    def clear_session(self, session_id: str) -> bool:
        """
        Remove todos os objetos de uma sessão

        Args:
            session_id: ID da sessão

        Returns:
            True se removida com sucesso
        """
        try:
            # Remove objetos da sessão
            if session_id in self._session_objects:
                del self._session_objects[session_id]

            # Remove mapeamentos da sessão
            if session_id in self._session_mappings:
                del self._session_mappings[session_id]

            # Remove mapeamentos relacionados
            keys_to_remove = []
            for key in self._agent_db_mapping.keys():
                if key.startswith(f"session:{session_id}:"):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._agent_db_mapping[key]

            logging.info(f"[OBJECT_MANAGER] Sessão limpa: {session_id}")
            return True

        except Exception as e:
            logging.error(f"[OBJECT_MANAGER] Erro ao limpar sessão {session_id}: {e}")
            return False

    def get_session_stats(self, session_id: str) -> Dict[str, int]:
        """
        Retorna estatísticas de objetos da sessão

        Args:
            session_id: ID da sessão

        Returns:
            Dicionário com contadores por tipo
        """
        if session_id not in self._session_objects:
            return {}

        session_data = self._session_objects[session_id]
        return {
            "sql_agents": len(session_data["sql_agents"]),
            "engines": len(session_data["engines"]),
            "databases": len(session_data["databases"]),
            "cache_managers": len(session_data["cache_managers"]),
            "objects": len(session_data["objects"])
        }

    def get_all_sessions(self) -> List[str]:
        """
        Retorna lista de todas as sessões ativas

        Returns:
            Lista de session_ids
        """
        return list(self._session_objects.keys())

    def session_exists(self, session_id: str) -> bool:
        """
        Verifica se sessão existe

        Args:
            session_id: ID da sessão

        Returns:
            True se sessão existe
        """
        return session_id in self._session_objects

    # ===== MÉTODOS DE COMPATIBILIDADE (GLOBAIS) =====
    # Mantém compatibilidade com código existente

    def store_sql_agent(self, agent: Any, db_id: str = None) -> str:
        """Armazena agente SQL (método global para compatibilidade)"""
        agent_id = str(uuid.uuid4())
        self._sql_agents[agent_id] = agent

        if db_id:
            self._agent_db_mapping[agent_id] = db_id

        logging.info(f"Agente SQL armazenado com ID: {agent_id}")
        return agent_id

    def get_sql_agent(self, agent_id: str) -> Optional[Any]:
        """Recupera agente SQL (método global para compatibilidade)"""
        return self._sql_agents.get(agent_id)

    def store_engine(self, engine: Any) -> str:
        """Armazena engine (método global para compatibilidade)"""
        engine_id = str(uuid.uuid4())
        self._engines[engine_id] = engine
        logging.info(f"Engine armazenada com ID: {engine_id}")
        return engine_id

    def get_engine(self, engine_id: str) -> Optional[Any]:
        """Recupera engine (método global para compatibilidade)"""
        return self._engines.get(engine_id)

    def store_database(self, database: Any) -> str:
        """Armazena banco de dados (método global para compatibilidade)"""
        db_id = str(uuid.uuid4())
        self._databases[db_id] = database
        logging.info(f"Banco de dados armazenado com ID: {db_id}")
        return db_id

    def get_database(self, db_id: str) -> Optional[Any]:
        """Recupera banco de dados (método global para compatibilidade)"""
        return self._databases.get(db_id)

    def store_cache_manager(self, cache_manager: Any) -> str:
        """Armazena cache manager (método global para compatibilidade)"""
        cache_id = str(uuid.uuid4())
        self._cache_managers[cache_id] = cache_manager
        logging.info(f"Cache manager armazenado com ID: {cache_id}")
        return cache_id

    def get_cache_manager(self, cache_id: str) -> Optional[Any]:
        """Recupera cache manager (método global para compatibilidade)"""
        return self._cache_managers.get(cache_id)

    def get_db_id_for_agent(self, agent_id: str) -> Optional[str]:
        """Recupera ID do banco associado ao agente (compatibilidade)"""
        return self._agent_db_mapping.get(agent_id)

    # ===== INTEGRAÇÃO COM REDIS PARA SESSÕES =====

    def store_session_config_redis(self, session_id: str, config: Dict[str, Any]) -> bool:
        """
        Armazena configuração da sessão no Redis para uso pelo Celery

        Args:
            session_id: ID da sessão
            config: Configurações da sessão

        Returns:
            True se salvou com sucesso
        """
        try:
            # Importa aqui para evitar dependência circular
            from utils.session_manager import get_session_manager

            session_manager = get_session_manager()
            return session_manager.update_session(session_id, config)

        except Exception as e:
            logging.error(f"[OBJECT_MANAGER] Erro ao salvar configuração da sessão no Redis: {e}")
            return False

    def load_session_config_redis(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Carrega configuração da sessão do Redis

        Args:
            session_id: ID da sessão

        Returns:
            Configurações da sessão ou None se não encontrado
        """
        try:
            from utils.session_manager import get_session_manager

            session_manager = get_session_manager()
            return session_manager.get_session(session_id)

        except Exception as e:
            logging.error(f"[OBJECT_MANAGER] Erro ao carregar configuração da sessão do Redis: {e}")
            return None

    def store_agent_config_redis(self, agent_id: str, config: Dict[str, Any]) -> bool:
        """
        Armazena configuração do agente no Redis para uso pelo Celery

        Args:
            agent_id: ID do agente
            config: Configurações do agente

        Returns:
            True se salvou com sucesso
        """
        try:
            from tasks import save_agent_config_to_redis
            return save_agent_config_to_redis(agent_id, config)
        except Exception as e:
            logging.error(f"Erro ao salvar configuração no Redis: {e}")
            return False

    def load_agent_config_redis(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Carrega configuração do agente do Redis (compatibilidade)

        Args:
            agent_id: ID do agente

        Returns:
            Configurações do agente ou None se não encontrado
        """
        try:
            from tasks import load_agent_config_from_redis
            return load_agent_config_from_redis(agent_id)
        except Exception as e:
            logging.error(f"Erro ao carregar configuração do Redis: {e}")
            return None

    def store_processing_agent(self, agent: Any) -> str:
        """Armazena Processing Agent e retorna ID"""
        agent_id = str(uuid.uuid4())
        self._processing_agents[agent_id] = agent
        logging.info(f"Processing Agent armazenado com ID: {agent_id}")
        return agent_id

    def get_processing_agent(self, agent_id: str) -> Optional[Any]:
        """Recupera Processing Agent pelo ID"""
        return self._processing_agents.get(agent_id)
    
    def store_cache_manager(self, cache_manager: Any) -> str:
        """Armazena cache manager e retorna ID"""
        cache_id = str(uuid.uuid4())
        self._cache_managers[cache_id] = cache_manager
        logging.info(f"Cache manager armazenado com ID: {cache_id}")
        return cache_id
    
    def get_cache_manager(self, cache_id: str) -> Optional[Any]:
        """Recupera cache manager pelo ID"""
        return self._cache_managers.get(cache_id)
    
    def store_object(self, obj: Any, category: str = "general") -> str:
        """Armazena objeto genérico e retorna ID"""
        obj_id = str(uuid.uuid4())
        self._objects[obj_id] = {"object": obj, "category": category}
        logging.info(f"Objeto {category} armazenado com ID: {obj_id}")
        return obj_id
    
    def get_object(self, obj_id: str) -> Optional[Any]:
        """Recupera objeto pelo ID"""
        obj_data = self._objects.get(obj_id)
        return obj_data["object"] if obj_data else None
    
    def update_sql_agent(self, agent_id: str, new_agent: Any) -> bool:
        """Atualiza agente SQL existente"""
        if agent_id in self._sql_agents:
            self._sql_agents[agent_id] = new_agent
            logging.info(f"Agente SQL atualizado: {agent_id}")
            return True
        return False
    
    def update_engine(self, engine_id: str, new_engine: Any) -> bool:
        """Atualiza engine existente"""
        if engine_id in self._engines:
            self._engines[engine_id] = new_engine
            logging.info(f"Engine atualizada: {engine_id}")
            return True
        return False
    
    def update_cache_manager(self, cache_id: str, new_cache_manager: Any) -> bool:
        """Atualiza cache manager existente"""
        if cache_id in self._cache_managers:
            self._cache_managers[cache_id] = new_cache_manager
            logging.info(f"Cache manager atualizado: {cache_id}")
            return True
        return False
    
    def clear_all(self):
        """Limpa todos os objetos armazenados (globais e sessões)"""
        # Limpa objetos globais
        self._objects.clear()
        self._sql_agents.clear()
        self._engines.clear()
        self._databases.clear()
        self._cache_managers.clear()
        self._agent_db_mapping.clear()
        self._connection_metadata.clear()

        # Limpa objetos de sessões
        self._session_objects.clear()
        self._session_mappings.clear()

        logging.info("Todos os objetos foram limpos do gerenciador (globais e sessões)")

    def store_connection_metadata(self, connection_id: str, metadata: Dict[str, Any]) -> str:
        """
        Armazena metadados de conexão

        Args:
            connection_id: ID da conexão
            metadata: Metadados da conexão

        Returns:
            ID dos metadados armazenados
        """
        self._connection_metadata[connection_id] = metadata
        logging.info(f"Metadados de conexão armazenados com ID: {connection_id}")
        return connection_id

    def get_connection_metadata(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera metadados de conexão pelo ID

        Args:
            connection_id: ID da conexão

        Returns:
            Metadados da conexão ou None se não encontrado
        """
        return self._connection_metadata.get(connection_id)

    def get_all_connection_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna todos os metadados de conexão

        Returns:
            Dicionário com todos os metadados
        """
        return self._connection_metadata.copy()

    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas dos objetos armazenados"""
        return {
            "sql_agents": len(self._sql_agents),
            "engines": len(self._engines),
            "databases": len(self._databases),
            "cache_managers": len(self._cache_managers),
            "general_objects": len(self._objects),
            "agent_db_mappings": len(self._agent_db_mapping),
            "connection_metadata": len(self._connection_metadata)
        }

    # REMOVIDO: Métodos de configuração global
    # TOP_K agora é por sessão, não global

# Instância global do gerenciador
_object_manager: Optional[ObjectManager] = None

def get_object_manager() -> ObjectManager:
    """Retorna instância singleton do gerenciador de objetos"""
    global _object_manager
    if _object_manager is None:
        _object_manager = ObjectManager()
    return _object_manager

def reset_object_manager():
    """Reseta o gerenciador de objetos"""
    global _object_manager
    if _object_manager:
        _object_manager.clear_all()
    _object_manager = ObjectManager()
