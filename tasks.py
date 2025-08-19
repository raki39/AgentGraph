"""
Tasks do Celery para processamento de queries SQL
"""
import logging
import time
import json
import pandas as pd
from typing import Dict, Any, Optional
from celery import Celery
from sqlalchemy import create_engine, text

# Importa configurações
from utils.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, is_docker_environment, get_environment_info

# Log informações do ambiente no worker
env_info = get_environment_info()
logging.info(f"[CELERY_WORKER] Ambiente detectado: {env_info['environment']}")
logging.info(f"[CELERY_WORKER] Redis URL: {env_info['redis_url']}")
logging.info(f"[CELERY_WORKER] Concorrência esperada: {env_info['worker_concurrency']}")

# Configuração do Celery com logs
logging.info(f"[CELERY_CONFIG] Broker: {CELERY_BROKER_URL}")
logging.info(f"[CELERY_CONFIG] Backend: {CELERY_RESULT_BACKEND}")

celery_app = Celery(
    'agentgraph',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Configurações do Celery (sem worker_pool - definido no comando)
if is_docker_environment():
    # Docker: Configurações permissivas para tabelas grandes
    celery_app.conf.update(
        # Serialização
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',

        # Timezone
        timezone='UTC',
        enable_utc=True,

        # Task tracking
        task_track_started=True,

        # Timeouts estendidos para tabelas grandes
        task_time_limit=120 * 60,  # 120 minutos (2 horas)
        task_soft_time_limit=110 * 60,  # 110 minutos

        # Worker configuration
        worker_prefetch_multiplier=1,  # Uma task por vez para evitar sobrecarga
        worker_max_tasks_per_child=50,  # Reinicia worker após 50 tasks
        worker_disable_rate_limits=True,

        # Task acknowledgment - configurações para reliability
        task_acks_late=True,  # Confirma apenas após conclusão
        task_acks_on_failure_or_timeout=True,  # Confirma mesmo em falha
        task_reject_on_worker_lost=True,  # Rejeita se worker morrer

        # Events (desabilitados para performance)
        worker_send_task_events=False,
        task_send_sent_event=False,

        # Result backend
        result_expires=24 * 60 * 60,  # Resultados expiram em 24h
        result_backend_always_retry=True,  # Retry em erros recuperáveis
        result_backend_max_retries=10,  # Máximo 10 retries
    )
    logging.info("[CELERY_CONFIG] Configuração Docker permissiva aplicada (120min timeout)")
else:
    # Windows: Configurações padrão
    celery_app.conf.update(
        # Serialização
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',

        # Timezone
        timezone='UTC',
        enable_utc=True,

        # Task tracking
        task_track_started=True,

        # Timeouts estendidos para produção
        task_time_limit=60 * 60,  # 60 minutos (1 hora)
        task_soft_time_limit=55 * 60,  # 55 minutos

        # Worker configuration
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=True,

        # Events (desabilitados para performance)
        worker_send_task_events=False,
        task_send_sent_event=False,

        # Result backend
        result_expires=24 * 60 * 60,  # Resultados expiram em 24h
    )
    logging.info("[CELERY_CONFIG] Configuração Windows estendida aplicada (60min timeout)")

# Log configuração aplicada
env_info = get_environment_info()
logging.info(f"[CELERY_CONFIG] Configuração aplicada para {env_info['environment']}")
logging.info(f"[CELERY_CONFIG] Pool será definido pelo comando do worker")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Registries de cache por processo do worker (organizados por sessão)
_AGENT_REGISTRY = {}  # session_id -> {cache_key -> agent}
_DB_REGISTRY = {}     # session_id -> {cache_key -> database}

def _key_fingerprint(key_tuple: tuple) -> str:
    """Retorna um fingerprint seguro da chave de cache (SHA1) sem expor segredos."""
    try:
        import hashlib
        # Converte para string estável sem senhas explícitas: mascara db_uri
        parts = list(key_tuple)
        # parts[0] is literal "DB" or "AGENT"; the actual fields start at 1
        # Estrutura esperada: (LABEL, tenant_id, model, connection_type, db_uri_or_path, include_tables_key, top_k)
        if len(parts) >= 6:
            db_uri = str(parts[4])
            if db_uri.startswith("postgresql://") and '@' in db_uri:
                # mascara senha
                try:
                    prefix, rest = db_uri.split('://', 1)
                    creds, hostdb = rest.split('@', 1)
                    user, pwd = creds.split(':', 1)
                    masked = f"{prefix}://{user}:***@{hostdb}"
                    parts[4] = masked
                except Exception:
                    parts[4] = "***"
        key_str = '|'.join(map(str, parts))
        return hashlib.sha1(key_str.encode('utf-8')).hexdigest()[:12]
    except Exception:
        return "unknown"
def _sqlite_fingerprint(db_uri: str) -> str:
    """Gera fingerprint leve (tamanho-mtime) para arquivo SQLite do db_uri."""
    try:
        import re, os
        m = re.match(r"sqlite:///+(.+)", db_uri)
        if not m:
            return "unknown"
        db_path = m.group(1)
        if not os.path.exists(db_path):
            return "missing"
        st = os.stat(db_path)
        return f"{st.st_size}-{int(st.st_mtime)}"
    except Exception:
        return "unknown"

        return "unknown"


def _build_db_uri_or_path(agent_config: Dict[str, Any]) -> str:
    """Monta db_uri_or_path a partir da configuração. Para CSV/SQLite espera 'db_uri' no config."""
    connection_type = agent_config.get('connection_type', 'csv')
    if connection_type == 'csv':
        db_uri = agent_config.get('db_uri')
        if not db_uri:
            # Falha explícita orientando ingestão primeiro
            raise Exception("db_uri ausente para conexão CSV. Realize a ingestão (CSV->SQLite) antes de executar no worker.")
        return db_uri
    elif connection_type == 'postgresql':
        # Usa config explícita ou string db_uri, se existir
        if agent_config.get('db_uri'):
            return agent_config['db_uri']
        pg = agent_config.get('postgresql_config', {})
        required = ['username', 'password', 'host', 'port', 'database']
        if not all(k in pg and pg[k] for k in required):
            raise Exception("Configuração PostgreSQL incompleta. Forneça username, password, host, port, database.")
        return f"postgresql://{pg['username']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['database']}"
    else:
        raise Exception(f"Tipo de conexão não suportado: {connection_type}")


def _generate_cache_key(agent_config: Dict[str, Any]) -> tuple:
    # NOVO: session_id é o primeiro elemento da chave para isolamento
    session_id = agent_config.get('session_id', 'global')
    tenant_id = agent_config.get('tenant_id', 'default')
    selected_model = agent_config.get('selected_model', 'gpt-4o-mini')
    connection_type = agent_config.get('connection_type', 'csv')
    db_uri_or_path = _build_db_uri_or_path(agent_config)

    # include_tables_key: '*' por padrão; se modo tabela única, usa nome da tabela
    if agent_config.get('single_table_mode') and agent_config.get('selected_table'):
        include_tables_key = agent_config['selected_table']
    else:
        include_tables_key = '*'

    # fingerprint de arquivo para SQLite para refletir mudanças após novo upload
    if connection_type == 'csv' and str(db_uri_or_path).startswith('sqlite'):
        sqlite_fp = _sqlite_fingerprint(str(db_uri_or_path))
    else:
        sqlite_fp = None

    top_k = agent_config.get('top_k', 10)
    version = agent_config.get('version', 1)  # NOVO: versão da configuração

    return (session_id, tenant_id, selected_model, connection_type, db_uri_or_path, include_tables_key, sqlite_fp, top_k, version)


def _get_or_create_database(agent_config: Dict[str, Any]):
    """Obtém ou cria SQLDatabase usando db_uri, com cache por sessão."""
    from utils.database import create_sql_database

    session_id = agent_config.get('session_id', 'global')
    cache_key = _generate_cache_key(agent_config)

    # Inicializa cache da sessão se não existir
    if session_id not in _DB_REGISTRY:
        _DB_REGISTRY[session_id] = {}

    session_cache = _DB_REGISTRY[session_id]

    if cache_key in session_cache:
        logging.info(f"[CACHE] cache_hit DB para sessão {session_id}, chave {_key_fingerprint(cache_key)}")
        return session_cache[cache_key]

    # cache miss
    db_uri = _build_db_uri_or_path(agent_config)
    logging.info(f"[DB_URI] Abrindo banco via db_uri para sessão {session_id}: {db_uri}")

    # Se for SQLite local, garantir que o arquivo exista ou usar fallback
    if db_uri.startswith("sqlite"):
        try:
            import re, os
            from utils.config import SQL_DB_PATH

            m = re.match(r"sqlite:///+(.+)", db_uri)
            if m:
                db_path = m.group(1)
                if not os.path.exists(db_path):
                    # FALLBACK: Se banco da sessão não existe, usa banco padrão
                    logging.warning(f"[DB_URI] Banco da sessão não encontrado: {db_path}")
                    logging.info(f"[DB_URI] Usando banco padrão como fallback: {SQL_DB_PATH}")

                    if os.path.exists(SQL_DB_PATH):
                        db_uri = f"sqlite:///{SQL_DB_PATH}"
                        logging.info(f"[DB_URI] Fallback aplicado: {db_uri}")
                    else:
                        raise Exception(f"Nem banco da sessão nem banco padrão encontrados. Upload um CSV primeiro.")
        except Exception as e:
            logging.error(f"[DB_URI] Validação SQLite falhou: {e}")
            raise

    engine = create_engine(db_uri)

    # Testar conexão rápida
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logging.error(f"[DB_URI] Falha ao conectar em {db_uri}: {e}")
        raise

    db = create_sql_database(engine)
    session_cache[cache_key] = db
    logging.info(f"[CACHE] cache_miss DB para sessão {session_id}; armazenado para chave {_key_fingerprint(cache_key)}")
    return db


def _get_or_create_sql_agent(agent_config: Dict[str, Any]):
    """Obtém ou cria SQLAgentManager com cache por sessão, preservando ciclo nativo."""
    from agents.sql_agent import SQLAgentManager

    session_id = agent_config.get('session_id', 'global')
    cache_key = _generate_cache_key(agent_config)

    # Inicializa cache da sessão se não existir
    if session_id not in _AGENT_REGISTRY:
        _AGENT_REGISTRY[session_id] = {}

    session_cache = _AGENT_REGISTRY[session_id]

    if cache_key in session_cache:
        # Verifica se a versão mudou - se sim, força cache miss
        cached_agent = session_cache[cache_key]
        current_version = agent_config.get('version', 1)
        cached_version = getattr(cached_agent, '_config_version', 1)

        if current_version != cached_version:
            logging.info(f"[CACHE] Versão mudou ({cached_version} → {current_version}), forçando cache miss para sessão {session_id}")
            del session_cache[cache_key]
        else:
            logging.info(f"[CACHE] cache_hit AGENT para sessão {session_id}, chave {_key_fingerprint(cache_key)}")
            return session_cache[cache_key]

    # cache miss: cria DB (via cache) e agente
    db = _get_or_create_database(agent_config)
    single_table_mode = agent_config.get('single_table_mode', False)
    selected_table = agent_config.get('selected_table')
    selected_model = agent_config.get('selected_model', 'gpt-4o-mini')
    top_k = agent_config.get('top_k', 10)

    agent = SQLAgentManager(
        db=db,
        model_name=selected_model,
        single_table_mode=single_table_mode,
        selected_table=selected_table,
        top_k=top_k
    )

    # Armazena versão da configuração no agente para controle de cache
    agent._config_version = agent_config.get('version', 1)

    session_cache[cache_key] = agent
    logging.info(f"[CACHE] cache_miss AGENT para sessão {session_id}; agente criado e armazenado para chave {_key_fingerprint(cache_key)}")
    return agent

@celery_app.task(bind=True, name='process_sql_query')
def process_sql_query_task(self, session_id: str, user_input: str) -> Dict[str, Any]:
    """
    Task principal para processar queries SQL com suporte a sessões

    Args:
        session_id: ID da sessão para carregar configurações do Redis
        user_input: Pergunta do usuário

    Returns:
        Dicionário com resultado da execução
    """
    start_time = time.time()

    try:
        logging.info(f"[CELERY_TASK] ===== INICIANDO TASK =====")
        logging.info(f"[CELERY_TASK] Task ID: {self.request.id}")
        logging.info(f"[CELERY_TASK] Session ID: {session_id}")
        logging.info(f"[CELERY_TASK] User input: {user_input[:100]}...")
        logging.info(f"[CELERY_TASK] Timestamp: {time.time()}")

        # Atualiza status inicial
        logging.info(f"[CELERY_TASK] Atualizando estado inicial...")
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Carregando configurações da sessão...',
                'progress': 10,
                'session_id': session_id
            }
        )
        logging.info(f"[CELERY_TASK] Estado inicial atualizado")

        # 1. Carregar configurações da sessão do Redis
        logging.info(f"[CELERY_TASK] Carregando configurações da sessão {session_id}...")
        session_config = load_session_config_from_redis(session_id)
        if not session_config:
            logging.error(f"[CELERY_TASK] ❌ Configuração da sessão não encontrada no Redis!")
            raise Exception(f"Configuração da sessão {session_id} não encontrada no Redis")

        logging.info(f"[CELERY_TASK] ✅ Configurações da sessão carregadas com sucesso")

        # Adiciona session_id à configuração para uso no cache
        session_config['session_id'] = session_id

        logging.info(f"[CELERY_TASK] Configuração carregada: {session_config['connection_type']}")

        # Atualiza status
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Preparando agente SQL (cache por sessão)...',
                'progress': 30,
                'connection_type': session_config['connection_type']
            }
        )

        # 2. Obter/criar SQL Agent via cache por sessão
        sql_agent = _get_or_create_sql_agent(session_config)

        # Atualiza status
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Executando query SQL...',
                'progress': 60,
                'model': session_config.get('selected_model', 'gpt-4o-mini')
            }
        )

        # 3. Executar pipeline do AgentSQL
        result = execute_sql_pipeline(sql_agent, user_input, session_config)

        # Atualiza status
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Finalizando processamento...',
                'progress': 90
            }
        )

        execution_time = time.time() - start_time

        # 4. Preparar resultado final
        final_result = {
            'status': 'success',
            'sql_query': result.get('sql_query'),
            'response': result.get('output', ''),
            'execution_time': execution_time,
            'session_id': session_id,
            'connection_type': session_config['connection_type'],
            'model_used': session_config.get('selected_model', 'gpt-4o-mini'),
            'intermediate_steps': result.get('intermediate_steps', [])
        }

        logging.info(f"[CELERY_TASK] Concluido em {execution_time:.2f}s | {session_config.get('selected_model', 'gpt-4o-mini')}")
        if result.get('sql_query'):
            sql_query_str = str(result.get('sql_query'))
            logging.info(f"[CELERY_TASK] SQL: {sql_query_str[:80]}...")
        return final_result

    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Erro no processamento SQL: {str(e)}"

        logging.error(f"[CELERY_TASK] {error_msg}")
        logging.error(f"[CELERY_TASK] Exception type: {type(e).__name__}")
        logging.error(f"[CELERY_TASK] Exception args: {e.args}")

        # Atualiza estado de erro
        self.update_state(
            state='FAILURE',
            meta={
                'error': error_msg,
                'execution_time': execution_time,
                'session_id': session_id,
                'exception_type': type(e).__name__
            }
        )

        # Levanta a exceção corretamente para o Celery
        raise Exception(error_msg) from e

def load_session_config_from_redis(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Carrega configuração da sessão do Redis

    Args:
        session_id: ID da sessão

    Returns:
        Dicionário com configurações ou None se não encontrado
    """
    import redis
    from utils.config import REDIS_HOST, REDIS_PORT

    try:
        # Log informações de ambiente para debug
        env_info = get_environment_info()
        logging.info(f"[REDIS] Worker ambiente: {env_info['environment']}")
        logging.info(f"[REDIS] Conectando ao Redis para carregar sessão {session_id}...")
        logging.info(f"[REDIS] Host: {REDIS_HOST}, Port: {REDIS_PORT}")

        # Usa DB 2 para sessões (mesmo do SessionManager)
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=2, decode_responses=True)

        # Testa conexão
        redis_client.ping()
        logging.info(f"[REDIS] Conexão com Redis estabelecida")

        # Busca configuração da sessão no Redis
        session_key = f"session:{session_id}"
        logging.info(f"[REDIS] Buscando chave: {session_key}")
        session_data = redis_client.get(session_key)

        if not session_data:
            logging.error(f"[REDIS] ❌ Configuração da sessão não encontrada: {session_id}")
            logging.error(f"[REDIS] Chave buscada: {session_key}")
            return None

        # Deserializa configuração
        logging.info(f"[REDIS] Dados encontrados, deserializando...")
        session_config = json.loads(session_data)
        logging.info(f"[REDIS] ✅ Configuração da sessão carregada para {session_id}: {list(session_config.keys())}")

        return session_config

    except Exception as e:
        logging.error(f"[REDIS] Erro ao carregar configuração da sessão: {e}")
        return None

def save_session_config_to_redis(session_id: str, config: Dict[str, Any]) -> bool:
    """
    Salva configuração da sessão no Redis

    Args:
        session_id: ID da sessão
        config: Configurações a serem salvas

    Returns:
        True se salvou com sucesso, False caso contrário
    """
    import redis
    from utils.config import REDIS_HOST, REDIS_PORT

    try:
        # Log informações de ambiente para debug
        env_info = get_environment_info()
        logging.info(f"[REDIS] Worker ambiente: {env_info['environment']}")
        logging.info(f"[REDIS] Salvando configuração para sessão {session_id}...")
        logging.info(f"[REDIS] Host: {REDIS_HOST}, Port: {REDIS_PORT}")

        # Usa DB 2 para sessões
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=2, decode_responses=True)

        # Serializa e salva configuração
        session_key = f"session:{session_id}"
        config_data = json.dumps(config, default=str)

        redis_client.set(session_key, config_data)
        logging.info(f"[REDIS] Configuração da sessão salva para {session_id}")

        return True

    except Exception as e:
        logging.error(f"[REDIS] Erro ao salvar configuração da sessão: {e}")
        return False

def cleanup_session_cache(session_id: str) -> bool:
    """
    Remove cache de uma sessão específica

    Args:
        session_id: ID da sessão

    Returns:
        True se removido com sucesso
    """
    try:
        removed_count = 0

        # Remove cache de agentes da sessão
        if session_id in _AGENT_REGISTRY:
            removed_count += len(_AGENT_REGISTRY[session_id])
            del _AGENT_REGISTRY[session_id]

        # Remove cache de databases da sessão
        if session_id in _DB_REGISTRY:
            removed_count += len(_DB_REGISTRY[session_id])
            del _DB_REGISTRY[session_id]

        if removed_count > 0:
            logging.info(f"[CACHE_CLEANUP] {removed_count} objetos removidos do cache da sessão {session_id}")

        return True

    except Exception as e:
        logging.error(f"[CACHE_CLEANUP] Erro ao limpar cache da sessão {session_id}: {e}")
        return False

def get_cache_stats() -> Dict[str, Any]:
    """
    Retorna estatísticas do cache por sessão

    Returns:
        Dicionário com estatísticas
    """
    try:
        stats = {
            "total_sessions": len(_AGENT_REGISTRY),
            "sessions": {}
        }

        for session_id in _AGENT_REGISTRY.keys():
            agent_count = len(_AGENT_REGISTRY.get(session_id, {}))
            db_count = len(_DB_REGISTRY.get(session_id, {}))

            stats["sessions"][session_id] = {
                "agents": agent_count,
                "databases": db_count,
                "total_objects": agent_count + db_count
            }

        return stats

    except Exception as e:
        logging.error(f"[CACHE_STATS] Erro ao obter estatísticas: {e}")
        return {}

def load_agent_config_from_redis(agent_id: str) -> Optional[Dict[str, Any]]:
    """
    Carrega configuração do agente do Redis

    Args:
        agent_id: ID do agente

    Returns:
        Dicionário com configurações ou None se não encontrado
    """
    import redis
    from utils.config import REDIS_HOST, REDIS_PORT

    try:
        # Log informações de ambiente para debug
        env_info = get_environment_info()
        logging.info(f"[REDIS] Worker ambiente: {env_info['environment']}")
        logging.info(f"[REDIS] Conectando ao Redis para carregar {agent_id}...")
        logging.info(f"[REDIS] Host: {REDIS_HOST}, Port: {REDIS_PORT}")

        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True)

        # Testa conexão
        redis_client.ping()
        logging.info(f"[REDIS] Conexão com Redis estabelecida")

        # Busca configuração no Redis
        config_key = f"agent_config:{agent_id}"
        logging.info(f"[REDIS] Buscando chave: {config_key}")
        config_data = redis_client.get(config_key)

        if not config_data:
            logging.error(f"[REDIS] ❌ Configuração não encontrada para agent_id: {agent_id}")
            logging.error(f"[REDIS] Chave buscada: {config_key}")
            return None

        # Deserializa configuração
        logging.info(f"[REDIS] Dados encontrados, deserializando...")
        agent_config = json.loads(config_data)
        logging.info(f"[REDIS] ✅ Configuração carregada para {agent_id}: {list(agent_config.keys())}")

        return agent_config

    except Exception as e:
        logging.error(f"[REDIS] Erro ao carregar configuração: {e}")
        return None

def save_agent_config_to_redis(agent_id: str, config: Dict[str, Any]) -> bool:
    """
    Salva configuração do agente no Redis

    Args:
        agent_id: ID do agente
        config: Configurações a serem salvas

    Returns:
        True se salvou com sucesso, False caso contrário
    """
    import redis
    from utils.config import REDIS_HOST, REDIS_PORT

    try:
        # Log informações de ambiente para debug
        env_info = get_environment_info()
        logging.info(f"[REDIS] Worker ambiente: {env_info['environment']}")
        logging.info(f"[REDIS] Salvando configuração para {agent_id}...")
        logging.info(f"[REDIS] Host: {REDIS_HOST}, Port: {REDIS_PORT}")

        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True)

        # Serializa e salva configuração
        config_key = f"agent_config:{agent_id}"
        config_data = json.dumps(config, default=str)

        redis_client.set(config_key, config_data)
        logging.info(f"[REDIS] Configuração salva para {agent_id}")

        return True

    except Exception as e:
        logging.error(f"[REDIS] Erro ao salvar configuração: {e}")
        return False

# OBSOLETO: reconstrução por task foi substituída por cache por processo (_get_or_create_sql_agent)
# Mantido por compatibilidade mas não utilizado no fluxo principal.
def reconstruct_sql_agent(agent_config: Dict[str, Any]):
    logging.warning("[RECONSTRUCT] Função obsoleta chamada. Utilize o cache por processo.")
    return _get_or_create_sql_agent(agent_config)

# OBSOLETO: leitura de CSV no worker não é mais suportada. Utilize db_uri persistido.
def create_engine_from_csv(csv_path: str):
    """
    [OBSOLETO] Cria engine SQLite a partir de arquivo CSV. Não utilizar no worker.
    """
    raise RuntimeError("Leitura de CSV no worker desabilitada. Realize a ingestão (CSV->SQLite) no app e passe db_uri.")

def create_engine_from_postgresql(pg_config: Dict[str, Any]):
    """
    Cria engine PostgreSQL

    Args:
        pg_config: Configurações do PostgreSQL

    Returns:
        Engine SQLAlchemy
    """
    try:
        # Monta URL de conexão
        connection_url = (
            f"postgresql://{pg_config['username']}:{pg_config['password']}"
            f"@{pg_config['host']}:{pg_config['port']}/{pg_config['database']}"
        )

        # Cria engine
        engine = create_engine(connection_url)

        # Testa conexão com text() para SQLAlchemy 2.0+
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        logging.info(f"[PG_ENGINE] Engine PostgreSQL criada com sucesso")
        return engine

    except Exception as e:
        logging.error(f"[PG_ENGINE] Erro ao criar engine: {e}")
        raise

def execute_sql_pipeline(sql_agent, user_input: str, agent_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o pipeline do AgentSQL

    Args:
        sql_agent: Instância do SQLAgentManager
        user_input: Pergunta do usuário
        agent_config: Configurações do agente

    Returns:
        Resultado da execução
    """
    import asyncio

    try:
        logging.info(f"[SQL_PIPELINE] Executando: {user_input[:80]}...")

        # Log apenas se houver contexto
        sql_context = agent_config.get('sql_context', '')
        if sql_context:
            logging.info(f"[SQL_PIPELINE] Usando contexto SQL: {len(str(sql_context))} chars")

        # Executa query de forma assíncrona
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Preparar instrução com contexto
            instruction = user_input

            # Adicionar contexto SQL se disponível
            sql_context = agent_config.get('sql_context', '')
            if sql_context:
                instruction = f"{sql_context}\n\nPergunta do usuário: {user_input}"

            # Adicionar query sugerida se disponível
            suggested_query = agent_config.get('suggested_query', '')
            if suggested_query:
                instruction += f"\n\nQuery sugerida: {suggested_query}"

            # Adicionar observações se disponíveis
            query_observations = agent_config.get('query_observations', '')
            if query_observations:
                instruction += f"\n\nObservações: {query_observations}"

            # Executar query
            result = loop.run_until_complete(sql_agent.execute_query(instruction))
        finally:
            loop.close()

        if result['success']:
            logging.info(f"[SQL_PIPELINE] Execução bem-sucedida")
            return {
                'output': result['output'],
                'sql_query': result.get('sql_query'),
                'intermediate_steps': result.get('intermediate_steps', []),
                'success': True
            }
        else:
            logging.error(f"[SQL_PIPELINE] Execução falhou: {result.get('output', 'Erro desconhecido')}")
            return {
                'output': result.get('output', 'Erro na execução SQL'),
                'sql_query': None,
                'intermediate_steps': [],
                'success': False
            }

    except Exception as e:
        error_msg = f"Erro no pipeline SQL: {str(e)}"
        logging.error(f"[SQL_PIPELINE] {error_msg}")
        return {
            'output': error_msg,
            'sql_query': None,
            'intermediate_steps': [],
            'success': False
        }

# Função auxiliar para obter status de task
def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Obtém status de uma task do Celery

    Args:
        task_id: ID da task

    Returns:
        Dicionário com status da task
    """
    from celery.result import AsyncResult

    try:
        task_result = AsyncResult(task_id, app=celery_app)

        if task_result.state == 'PENDING':
            return {
                'state': 'PENDING',
                'status': 'Aguardando processamento...',
                'progress': 0,
                'task_id': task_id
            }
        elif task_result.state == 'PROCESSING':
            meta = task_result.info or {}
            return {
                'state': 'PROCESSING',
                'status': meta.get('status', 'Processando...'),
                'progress': meta.get('progress', 50),
                'task_id': task_id,
                **meta
            }
        elif task_result.state == 'SUCCESS':
            return {
                'state': 'SUCCESS',
                'result': task_result.result,
                'status': 'Concluído com sucesso',
                'progress': 100,
                'task_id': task_id
            }
        elif task_result.state == 'FAILURE':
            return {
                'state': 'FAILURE',
                'error': str(task_result.info),
                'status': 'Erro no processamento',
                'progress': 0,
                'task_id': task_id
            }
        else:
            return {
                'state': task_result.state,
                'status': f'Estado desconhecido: {task_result.state}',
                'progress': 0,
                'task_id': task_id
            }

    except Exception as e:
        return {
            'state': 'ERROR',
            'error': str(e),
            'status': 'Erro ao consultar status',
            'progress': 0,
            'task_id': task_id
        }
