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

        # Timeouts padrão
        task_time_limit=30 * 60,  # 30 minutos
        task_soft_time_limit=25 * 60,  # 25 minutos

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
    logging.info("[CELERY_CONFIG] Configuração Windows padrão aplicada (30min timeout)")

# Log configuração aplicada
env_info = get_environment_info()
logging.info(f"[CELERY_CONFIG] Configuração aplicada para {env_info['environment']}")
logging.info(f"[CELERY_CONFIG] Pool será definido pelo comando do worker")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@celery_app.task(bind=True, name='process_sql_query')
def process_sql_query_task(self, agent_id: str, user_input: str) -> Dict[str, Any]:
    """
    Task principal para processar queries SQL
    
    Args:
        agent_id: ID do agente para carregar configurações do Redis
        user_input: Pergunta do usuário
        
    Returns:
        Dicionário com resultado da execução
    """
    start_time = time.time()
    
    try:
        logging.info(f"[CELERY_TASK] ===== INICIANDO TASK =====")
        logging.info(f"[CELERY_TASK] Task ID: {self.request.id}")
        logging.info(f"[CELERY_TASK] Agent ID: {agent_id}")
        logging.info(f"[CELERY_TASK] User input: {user_input[:100]}...")
        logging.info(f"[CELERY_TASK] Timestamp: {time.time()}")

        # Atualiza status inicial
        logging.info(f"[CELERY_TASK] Atualizando estado inicial...")
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Carregando configurações do agente...',
                'progress': 10,
                'agent_id': agent_id
            }
        )
        logging.info(f"[CELERY_TASK] Estado inicial atualizado")
        
        # 1. Carregar configurações do Redis
        logging.info(f"[CELERY_TASK] Carregando configurações do Redis para {agent_id}...")
        agent_config = load_agent_config_from_redis(agent_id)
        if not agent_config:
            logging.error(f"[CELERY_TASK] ❌ Configuração não encontrada no Redis!")
            raise Exception(f"Configuração do agente {agent_id} não encontrada no Redis")

        logging.info(f"[CELERY_TASK] ✅ Configurações carregadas com sucesso")
        
        logging.info(f"[CELERY_TASK] Configuração carregada: {agent_config['connection_type']}")
        
        # Atualiza status
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Reconstruindo agente SQL...',
                'progress': 30,
                'connection_type': agent_config['connection_type']
            }
        )
        
        # 2. Reconstruir SQL Agent baseado no tipo de conexão
        sql_agent = reconstruct_sql_agent(agent_config)

        # Atualiza status
        self.update_state(
            state='PROCESSING',
            meta={
                'status': 'Executando query SQL...',
                'progress': 60,
                'model': agent_config.get('selected_model', 'gpt-4o-mini')
            }
        )

        # 3. Executar pipeline do AgentSQL
        result = execute_sql_pipeline(sql_agent, user_input, agent_config)
        
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
            'agent_id': agent_id,
            'connection_type': agent_config['connection_type'],
            'model_used': agent_config.get('selected_model', 'gpt-4o-mini'),
            'intermediate_steps': result.get('intermediate_steps', [])
        }

        logging.info(f"[CELERY_TASK] Concluido em {execution_time:.2f}s | {agent_config.get('selected_model', 'gpt-4o-mini')}")
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
                'agent_id': agent_id,
                'exception_type': type(e).__name__
            }
        )

        # Levanta a exceção corretamente para o Celery
        raise Exception(error_msg) from e

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

def reconstruct_sql_agent(agent_config: Dict[str, Any]):
    """
    Reconstrói o SQL Agent baseado na configuração

    Args:
        agent_config: Configurações do agente carregadas do Redis

    Returns:
        Instância do SQLAgentManager
    """
    from agents.sql_agent import SQLAgentManager
    from utils.database import create_sql_database

    try:
        logging.info(f"[RECONSTRUCT] Reconstruindo agente SQL...")

        connection_type = agent_config['connection_type']
        selected_model = agent_config.get('selected_model', 'gpt-4o-mini')
        top_k = agent_config.get('top_k', 10)

        # Configurações do Processing Agent
        processing_enabled = agent_config.get('processing_enabled', False)
        processing_model = agent_config.get('processing_model', 'GPT-4o-mini')

        # Configurações de refinamento
        advanced_mode = agent_config.get('advanced_mode', False)

        # Log simplificado das configurações
        processing_status = "ATIVO" if processing_enabled else "DESATIVO"
        refinement_status = "ATIVO" if advanced_mode else "DESATIVO"

        logging.info(f"[RECONSTRUCT] Config: {selected_model} | {connection_type} | TOP_K={top_k} | Processing={processing_status} | Refinamento={refinement_status}")

        # Log do contexto apenas se houver
        sql_context = agent_config.get('sql_context', '')
        if sql_context:
            logging.info(f"[RECONSTRUCT] Contexto SQL recebido: {len(str(sql_context))} chars")

        if connection_type == 'csv':
            # Reconstruir para CSV
            csv_path = agent_config['csv_path']

            logging.info(f"[RECONSTRUCT] Criando agente CSV: {csv_path}")

            # Verificar se arquivo existe
            import os
            if not os.path.exists(csv_path):
                logging.error(f"[RECONSTRUCT] Arquivo CSV nao encontrado: {csv_path}")

            # Criar engine e agente
            engine = create_engine_from_csv(csv_path)
            db = create_sql_database(engine)
            sql_agent = SQLAgentManager(
                db=db,
                model_name=selected_model,
                single_table_mode=False,
                selected_table=None,
                top_k=top_k
            )
            logging.info(f"[RECONSTRUCT] Agente CSV criado com sucesso")

        elif connection_type == 'postgresql':
            # Reconstruir para PostgreSQL
            pg_config = agent_config['postgresql_config']
            single_table_mode = agent_config.get('single_table_mode', False)
            selected_table = agent_config.get('selected_table')

            logging.info(f"[RECONSTRUCT] Criando agente PostgreSQL: {pg_config.get('host')}:{pg_config.get('port')}/{pg_config.get('database')}")

            # Criar engine e agente
            engine = create_engine_from_postgresql(pg_config)
            db = create_sql_database(engine)
            sql_agent = SQLAgentManager(
                db=db,
                model_name=selected_model,
                single_table_mode=single_table_mode,
                selected_table=selected_table,
                top_k=top_k
            )
            logging.info(f"[RECONSTRUCT] Agente PostgreSQL criado com sucesso")

        else:
            raise Exception(f"Tipo de conexão não suportado: {connection_type}")

        logging.info(f"[RECONSTRUCT] Agente reconstruido: {sql_agent.model_name} | TOP_K={sql_agent.top_k}")
        return sql_agent

    except Exception as e:
        logging.error(f"[RECONSTRUCT] ❌ Erro ao reconstruir agente: {e}")
        logging.error(f"[RECONSTRUCT] Configuração que causou erro: {agent_config}")
        raise

def create_engine_from_csv(csv_path: str):
    """
    Cria engine SQLite a partir de arquivo CSV

    Args:
        csv_path: Caminho para o arquivo CSV

    Returns:
        Engine SQLAlchemy
    """
    try:
        # Lê CSV
        df = pd.read_csv(csv_path, sep=';')

        # Cria engine SQLite em memória
        engine = create_engine('sqlite:///:memory:')

        # Carrega dados na tabela
        df.to_sql('tabela', engine, index=False, if_exists='replace')

        logging.info(f"[CSV_ENGINE] Engine criada com {len(df)} registros")
        return engine

    except Exception as e:
        logging.error(f"[CSV_ENGINE] Erro ao criar engine: {e}")
        raise

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
