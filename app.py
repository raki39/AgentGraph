"""
AgentGraph - Aplicação principal com interface Gradio e LangGraph
"""
import asyncio
import logging
import gradio as gr
import tempfile
import os
from typing import List, Tuple, Optional, Dict
from PIL import Image

from graphs.main_graph import initialize_graph, get_graph_manager
from utils.config import (
    AVAILABLE_MODELS,
    REFINEMENT_MODELS,
    DEFAULT_MODEL,
    GRADIO_SHARE,
    GRADIO_PORT,
    validate_config,
    is_langsmith_enabled,
    LANGSMITH_PROJECT
)
from utils.object_manager import get_object_manager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Variáveis globais
graph_manager = None
show_history_flag = False
connection_ready = False  # Controla se a conexão está pronta para uso
chat_blocked = False      # Controla se o chat está bloqueado durante carregamento

async def initialize_app():
    """Inicializa a aplicação"""
    global graph_manager, connection_ready

    try:
        # Valida configurações
        validate_config()

        # Inicializa o grafo
        graph_manager = await initialize_graph()

        # Inicializa como conectado (base padrão já carregada)
        connection_ready = True

        # Informa sobre o status do LangSmith
        if is_langsmith_enabled():
            logging.info(f"✅ LangSmith habilitado - Projeto: '{LANGSMITH_PROJECT}'")
            logging.info("🔍 Traces serão enviados para LangSmith automaticamente")
        else:
            logging.info("ℹ️ LangSmith não configurado - Executando sem observabilidade")

        logging.info("Aplicação inicializada com sucesso")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao inicializar aplicação: {e}")
        return False

def run_async(coro):
    """Executa corrotina de forma síncrona"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

def chatbot_response(user_input: str, selected_model: str, advanced_mode: bool = False, processing_enabled: bool = False, processing_model: str = "GPT-4o-mini", connection_type: str = "csv", postgresql_config: Optional[Dict] = None, selected_table: str = None, single_table_mode: bool = False) -> Tuple[str, Optional[str]]:
    """
    Processa resposta do chatbot usando LangGraph

    Args:
        user_input: Entrada do usuário
        selected_model: Modelo LLM selecionado
        advanced_mode: Se deve usar refinamento avançado
        processing_enabled: Se o Processing Agent está habilitado
        processing_model: Modelo para o Processing Agent
        connection_type: Tipo de conexão ("csv" ou "postgresql")
        postgresql_config: Configuração postgresql (se aplicável)
        selected_table: Tabela selecionada (para postgresql)
        single_table_mode: Se deve usar apenas uma tabela (postgresql)

    Returns:
        Tupla com (resposta_texto, caminho_imagem_grafico)
    """
    global graph_manager

    if not graph_manager:
        return "❌ Sistema não inicializado. Tente recarregar a página.", None

    try:
        # Processa query através do LangGraph
        result = run_async(graph_manager.process_query(
            user_input=user_input,
            selected_model=selected_model,
            advanced_mode=advanced_mode,
            processing_enabled=processing_enabled,
            processing_model=processing_model,
            connection_type=connection_type,
            postgresql_config=postgresql_config,
            selected_table=selected_table,
            single_table_mode=single_table_mode
        ))

        response_text = result.get("response", "Erro ao processar resposta")
        graph_image_path = None

        # Verifica se foi gerado um gráfico
        if result.get("graph_generated", False) and result.get("graph_image_id"):
            graph_image_path = save_graph_image_to_temp(result["graph_image_id"])

            # Adiciona informação sobre o gráfico na resposta
            if graph_image_path:
                graph_type = result.get("graph_type", "gráfico")
                response_text += f"\n\n📊 **Gráfico gerado**: {graph_type.replace('_', ' ').title()}"

        return response_text, graph_image_path

    except Exception as e:
        error_msg = f"Erro no chatbot: {e}"
        logging.error(error_msg)
        logging.error(f"Detalhes do erro: {type(e).__name__}: {str(e)}")
        return error_msg, None

def save_graph_image_to_temp(graph_image_id: str) -> Optional[str]:
    """
    Salva imagem do gráfico em arquivo temporário para exibição no Gradio

    Args:
        graph_image_id: ID da imagem no ObjectManager

    Returns:
        Caminho do arquivo temporário ou None se falhar
    """
    try:
        obj_manager = get_object_manager()
        graph_image = obj_manager.get_object(graph_image_id)

        if graph_image and isinstance(graph_image, Image.Image):
            # Cria arquivo temporário
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            graph_image.save(temp_file.name, format='PNG')
            temp_file.close()

            logging.info(f"[GRADIO] Gráfico salvo em: {temp_file.name}")
            return temp_file.name

    except Exception as e:
        logging.error(f"[GRADIO] Erro ao salvar gráfico: {e}")

    return None

def handle_csv_upload(file) -> str:
    """
    Processa upload de arquivo csv

    Args:
        file: Arquivo enviado pelo Gradio

    Returns:
        Mensagem de feedback
    """
    global graph_manager

    if not graph_manager:
        return "❌ Sistema não inicializado."

    if not file:
        return "❌ Nenhum arquivo selecionado."

    try:
        # Log detalhado do arquivo recebido
        logging.info(f"[UPLOAD] Arquivo recebido: {file}")
        logging.info(f"[UPLOAD] Nome do arquivo: {file.name}")
        logging.info(f"[UPLOAD] Tipo do arquivo: {type(file)}")

        # Verifica se o arquivo existe
        import os
        if not os.path.exists(file.name):
            return f"❌ Arquivo não encontrado: {file.name}"

        # Verifica se é um arquivo csv
        if not file.name.lower().endswith('.csv'):
            return "❌ Por favor, selecione um arquivo csv válido."

        # Verifica o tamanho do arquivo
        file_size = os.path.getsize(file.name)
        file_size_mb = file_size / (1024 * 1024)
        file_size_gb = file_size / (1024 * 1024 * 1024)

        if file_size_gb >= 1:
            size_str = f"{file_size_gb:.2f} GB"
        else:
            size_str = f"{file_size_mb:.2f} MB"

        logging.info(f"[UPLOAD] Tamanho do arquivo: {file_size} bytes ({size_str})")

        if file_size == 0:
            return "❌ O arquivo está vazio."

        if file_size > 5 * 1024 * 1024 * 1024:  # 5GB
            return "❌ Arquivo muito grande. Máximo permitido: 5GB."

        # Aviso para arquivos grandes
        if file_size_mb > 100:
            logging.info(f"[UPLOAD] Arquivo grande detectado ({size_str}). Processamento pode demorar...")
            return f"⏳ Processando arquivo grande ({size_str}). Aguarde..."

        # Processa upload através do LangGraph
        logging.info(f"[UPLOAD] Iniciando processamento do arquivo: {file.name}")
        result = run_async(graph_manager.handle_csv_upload(file.name))

        logging.info(f"[UPLOAD] Resultado do processamento: {result}")
        return result.get("message", "Erro no upload")

    except Exception as e:
        error_msg = f"❌ Erro ao processar upload: {e}"
        logging.error(error_msg)
        logging.error(f"[UPLOAD] Detalhes do erro: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"[UPLOAD] Traceback: {traceback.format_exc()}")
        return error_msg

def reset_system() -> str:
    """
    Reseta o sistema ao estado inicial
    
    Returns:
        Mensagem de feedback
    """
    global graph_manager
    
    if not graph_manager:
        return "❌ Sistema não inicializado."
    
    try:
        # Reseta sistema através do LangGraph
        result = run_async(graph_manager.reset_system())
        
        return result.get("message", "Erro no reset")
        
    except Exception as e:
        error_msg = f"❌ Erro ao resetar sistema: {e}"
        logging.error(error_msg)
        return error_msg

def handle_postgresql_connection(host: str, port: str, database: str, username: str, password: str) -> str:
    """
    Processa conexão postgresql

    Args:
        host: Host do postgresql
        port: Porta do postgresql
        database: Nome do banco
        username: Nome de usuário
        password: Senha

    Returns:
        Mensagem de feedback
    """
    global graph_manager

    if not graph_manager:
        return "❌ Sistema não inicializado."

    try:
        # Valida campos obrigatórios
        if not all([host, port, database, username, password]):
            return "❌ Todos os campos são obrigatórios para conexão postgresql."

        # Valida porta
        try:
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                return "❌ Porta deve estar entre 1 e 65535."
        except ValueError:
            return "❌ Porta deve ser um número válido."

        # Prepara configuração postgresql
        postgresql_config = {
            "host": host.strip(),
            "port": port_int,
            "database": database.strip(),
            "username": username.strip(),
            "password": password
        }

        # Cria estado inicial para a conexão
        initial_state = {
            "user_input": "Conectar postgresql",
            "selected_model": "gpt-4o-mini",
            "advanced_mode": False,
            "processing_enabled": False,
            "processing_model": "gpt-4o-mini",
            "connection_type": "postgresql",
            "postgresql_config": postgresql_config,
            "selected_table": None,
            "single_table_mode": False
        }

        # Processa conexão através do LangGraph
        logging.info(f"[POSTGRESQL] Iniciando conexão: {host}:{port}/{database}")
        result = run_async(graph_manager.handle_postgresql_connection(initial_state))

        logging.info(f"[POSTGRESQL] Resultado da conexão: {result}")
        return result.get("message", "Erro na conexão postgresql")

    except Exception as e:
        error_msg = f"❌ Erro ao conectar postgresql: {e}"
        logging.error(error_msg)
        logging.error(f"[POSTGRESQL] Detalhes do erro: {type(e).__name__}: {str(e)}")
        return error_msg

def toggle_advanced_mode(enabled: bool) -> str:
    """
    Alterna modo avançado
    
    Args:
        enabled: Se deve habilitar modo avançado
        
    Returns:
        Mensagem de status
    """
    global graph_manager
    
    if not graph_manager:
        return "❌ Sistema não inicializado."
    
    return graph_manager.toggle_advanced_mode(enabled)

def toggle_history():
    """Alterna exibição do histórico"""
    global show_history_flag, graph_manager
    
    show_history_flag = not show_history_flag
    
    if show_history_flag and graph_manager:
        return graph_manager.get_history()
    else:
        return {}

def respond(message: str, chat_history: List[Dict[str, str]], selected_model: str, advanced_mode: bool, processing_enabled: bool = False, processing_model: str = "GPT-4o-mini", connection_type: str = "csv", postgresql_config: Optional[Dict] = None, selected_table: str = None, single_table_mode: bool = False):
    """
    Função de resposta para o chatbot Gradio

    Args:
        message: Mensagem do usuário
        chat_history: Histórico do chat (formato messages)
        selected_model: Modelo selecionado
        advanced_mode: Modo avançado habilitado
        processing_enabled: Se o Processing Agent está habilitado
        processing_model: Modelo para o Processing Agent
        connection_type: Tipo de conexão ("csv" ou "postgresql")
        postgresql_config: Configuração postgresql (se aplicável)
        selected_table: Tabela selecionada (para postgresql)
        single_table_mode: Se deve usar apenas uma tabela (postgresql)

    Returns:
        Tupla com (mensagem_vazia, histórico_atualizado, imagem_grafico)
    """
    import logging

    logging.info(f"[GRADIO RESPOND] ===== NOVA REQUISIÇÃO =====")
    logging.info(f"[GRADIO RESPOND] Message: {message}")
    logging.info(f"[GRADIO RESPOND] Selected model: {selected_model}")
    logging.info(f"[GRADIO RESPOND] Advanced mode: {advanced_mode}")
    logging.info(f"[GRADIO RESPOND] Processing enabled: {processing_enabled}")
    logging.info(f"[GRADIO RESPOND] Processing model: {processing_model}")

    if not message.strip():
        return "", chat_history, None

    # Processa resposta
    response, graph_image_path = chatbot_response(message, selected_model, advanced_mode, processing_enabled, processing_model, connection_type, postgresql_config, selected_table, single_table_mode)

    # Atualiza histórico no formato messages
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": response})

    return "", chat_history, graph_image_path

def handle_csv_and_clear_chat(file):
    """
    Processa csv e limpa chat com indicador de carregamento melhorado

    Args:
        file: Arquivo csv

    Returns:
        Tupla com (feedback, chat_limpo, grafico_limpo, status)
    """
    global connection_ready

    if file is None:
        connection_ready = False
        return "", [], gr.update(visible=False), "**Status**: <span class='status-error'>Nenhum arquivo selecionado</span>"

    # Indica carregamento
    connection_ready = False

    # Processa arquivo
    feedback = handle_csv_upload(file)

    # Status final baseado no resultado
    if "✅" in feedback:
        connection_ready = True
        final_status = "**Status**: <span class='status-connected'>csv processado com sucesso</span>"
    else:
        connection_ready = False
        final_status = "**Status**: <span class='status-error'>Erro no processamento do csv</span>"

    return feedback, [], gr.update(visible=False), final_status

def is_connection_ready(conn_type, pg_host=None, pg_port=None, pg_db=None, pg_user=None, pg_pass=None):
    """
    Verifica se há uma conexão de dados ativa e pronta para uso

    Args:
        conn_type: Tipo de conexão ("csv" ou "postgresql")
        pg_host, pg_port, pg_db, pg_user, pg_pass: Credenciais postgresql

    Returns:
        True se conexão está pronta, False caso contrário
    """
    global connection_ready, chat_blocked
    return connection_ready and not chat_blocked

def show_loading_in_chat(message):
    """
    Mostra mensagem de carregamento apenas no chat

    Args:
        message: Mensagem de carregamento

    Returns:
        Histórico atualizado com mensagem de carregamento
    """
    global chat_blocked
    chat_blocked = True

    return [
        {"role": "user", "content": "Alterando tipo de conexão..."},
        {"role": "assistant", "content": f"🔄 {message}"}
    ]

def clear_loading_from_chat():
    """
    Remove carregamento do chat
    """
    global chat_blocked
    chat_blocked = False

def load_default_csv_and_cleanup_postgresql():
    """
    Carrega a base csv padrão e limpa conexões postgresql ativas

    Returns:
        Mensagem de feedback sobre a operação
    """
    global connection_ready

    try:
        from utils.config import DEFAULT_CSV_PATH
        from utils.object_manager import get_object_manager
        import os

        # Verifica se o arquivo padrão existe
        if not os.path.exists(DEFAULT_CSV_PATH):
            connection_ready = False
            return "Arquivo csv padrão (tabela.csv) não encontrado"

        # Limpa conexões postgresql ativas
        obj_manager = get_object_manager()

        # Fecha engines postgresql (SQLAlchemy engines têm método dispose)
        for engine_id, engine in obj_manager._engines.items():
            try:
                if hasattr(engine, 'dispose'):
                    engine.dispose()
                    logging.info(f"[CLEANUP] Engine postgresql {engine_id} fechada")
            except Exception as e:
                logging.warning(f"[CLEANUP] Erro ao fechar engine {engine_id}: {e}")

        # Limpa objetos postgresql do ObjectManager
        obj_manager.clear_all()
        logging.info("[CLEANUP] Objetos postgresql limpos do ObjectManager")

        # Carrega csv padrão através do LangGraph
        logging.info(f"[CSV_DEFAULT] Carregando arquivo padrão: {DEFAULT_CSV_PATH}")
        result = run_async(graph_manager.handle_csv_upload(DEFAULT_CSV_PATH))

        if result.get("success", False):
            connection_ready = True
            return f"✅ Base padrão carregada: {os.path.basename(DEFAULT_CSV_PATH)}"
        else:
            connection_ready = False
            return f"Erro ao carregar base padrão: {result.get('message', 'Erro desconhecido')}"

    except Exception as e:
        connection_ready = False
        error_msg = f"Erro ao carregar base padrão: {e}"
        logging.error(f"[CSV_DEFAULT] {error_msg}")
        return error_msg

def reset_all():
    """
    Reseta tudo e limpa interface

    Returns:
        Tupla com (feedback, chat_limpo, arquivo_limpo, grafico_limpo)
    """
    feedback = reset_system()
    return feedback, [], None, gr.update(visible=False)

# Interface Gradio
def create_interface():
    """Cria interface Gradio"""

    # CSS customizado para interface limpa e moderna
    custom_css = """
    .gradio-container {
        padding: 20px 30px !important;
    }

    /* Seções de configuração */
    .config-section {
        background: #f8f9fa;
        border-radius: 15px;
        padding: 0;
        margin: 16px 0;
        overflow: hidden;
    }

    /* Headers dos containers com espaçamento adequado */
    .gradio-container h3 {
        margin: 0 !important;
        color: #f1f3f4 !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }

    /* Espaçamento para status e informações nos containers */
    .config-section .status-connected,
    .config-section .status-loading,
    .config-section .status-error,
    .config-section .status-waiting {
        padding: 8px 20px !important;
        display: block !important;
    }

    .prose.svelte-lag733 {
        padding: 12px 20px !important;
        margin: 0 !important;
    }

    /* Conteúdo dos containers */
    .config-content {
        padding: 20px;
    }

    /* Status indicators melhorados */
    .status-connected {
        color: #28a745;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    .status-loading {
        color: #ffc107;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    .status-loading::before {
        content: "⏳";
        animation: pulse 1.5s infinite;
    }

    .status-error {
        color: #dc3545;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    .status-waiting {
        color: #6c757d;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    /* Animação de carregamento */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* Espaçamentos internos */
    .gr-form {
        padding: 16px;
    }

    .gr-box {
        padding: 16px;
        margin: 12px 0;
    }

    /* Melhorias para seção postgresql */
    .pg-section {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        margin: 12px 0;
    }

    .pg-feedback {
        padding: 12px;
        margin: 8px 0;
        border-radius: 6px;
        background: #f1f3f4;
    }
    """

    with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Configurações")

                # 1. CONEXÃO DE DADOS
                with gr.Group():
                    gr.Markdown("### Conexão de Dados")

                    with gr.Group():
                        connection_type = gr.Radio(
                            choices=[("CSV", "csv"), ("PostgreSQL", "postgresql")],
                            value="csv",
                            label="Tipo de Conexão"
                        )

                        # Status da conexão
                        connection_status = gr.Markdown("**Status**: <span class='status-connected'>Base padrão carregada</span>")

                # Seção csv
                with gr.Group(visible=True) as csv_section:
                    csv_file = gr.File(
                        file_types=[".csv"],
                        label="Arquivo csv"
                    )
                    upload_feedback = gr.Markdown()

                # Seção postgresql
                with gr.Group(visible=False) as postgresql_section:
                    with gr.Group():
                        with gr.Row():
                            pg_host = gr.Textbox(
                                label="Host",
                                placeholder="localhost",
                                scale=2
                            )
                            pg_port = gr.Textbox(
                                label="Porta",
                                value="5432",
                                placeholder="5432",
                                scale=1
                            )

                        pg_database = gr.Textbox(
                            label="Banco de Dados",
                            placeholder="nome_do_banco"
                        )

                        with gr.Row():
                            pg_username = gr.Textbox(
                                label="Usuário",
                                placeholder="usuario",
                                scale=1
                            )
                            pg_password = gr.Textbox(
                                label="Senha",
                                type="password",
                                placeholder="senha",
                                scale=1
                            )

                        pg_connect_btn = gr.Button(
                            "Conectar postgresql",
                            variant="primary",
                            size="lg"
                        )

                        pg_feedback = gr.Markdown()

                    # Configuração de tabelas (visível após conexão)
                    with gr.Group(visible=False) as pg_table_section:
                        gr.Markdown("#### Configuração de Tabelas")

                        with gr.Group():
                            pg_single_table_mode = gr.Checkbox(
                                label="Modo Tabela Única",
                                value=False
                            )

                            # Seletor de tabela
                            with gr.Group(visible=False) as pg_table_selector_group:
                                pg_table_selector = gr.Dropdown(
                                    choices=[],
                                    label="Selecionar Tabela",
                                    interactive=True
                                )

                            pg_table_info = gr.Markdown()

                # 2. CONFIGURAÇÃO DE MODELOS
                with gr.Group():
                    gr.Markdown("### Configuração de Agentes")

                    with gr.Group():
                        # Processing Agent
                        processing_checkbox = gr.Checkbox(
                            label="Processing Agent",
                            value=False
                        )
                        processing_model_selector = gr.Dropdown(
                            choices=list(AVAILABLE_MODELS.keys()) + list(REFINEMENT_MODELS.keys()),
                            value="GPT-4o-mini",
                            label="Modelo do Processing Agent",
                            visible=False
                        )

                        # Modelo principal SQL
                        model_selector = gr.Dropdown(
                            list(AVAILABLE_MODELS.keys()),
                            value=DEFAULT_MODEL,
                            label="Modelo SQL Principal"
                        )

                # 3. CONFIGURAÇÕES AVANÇADAS
                with gr.Group():
                    gr.Markdown("### Configurações Avançadas")

                    with gr.Group():
                        advanced_checkbox = gr.Checkbox(
                            label="Refinar Resposta"
                        )

                # 4. STATUS E CONTROLES
                with gr.Group():
                    gr.Markdown("### Status do Sistema")

                    with gr.Group():
                        # Status do LangSmith
                        if is_langsmith_enabled():
                            gr.Markdown(f"**LangSmith**: Ativo")
                        else:
                            gr.Markdown("**LangSmith**: Desabilitado")

                        reset_btn = gr.Button(
                            "Resetar Sistema",
                            variant="secondary"
                        )
                
            with gr.Column(scale=4):
                gr.Markdown("## Agent86")
                chatbot = gr.Chatbot(
                    height=600,
                    show_label=False,
                    container=True,
                    type="messages"
                )

                msg = gr.Textbox(placeholder="Digite sua pergunta aqui...", lines=1, label="")
                btn = gr.Button("Enviar", variant="primary")
                history_btn = gr.Button("Histórico", variant="secondary")
                history_output = gr.JSON()

                # Componente para exibir gráficos - posicionado após histórico
                graph_image = gr.Image(
                    label="📊 Visualização de Dados",
                    visible=False,
                    height=500,  # Altura maior para ocupar mais espaço
                    show_label=True,
                    container=True,
                    interactive=False,
                    show_download_button=True
                )

                download_file = gr.File(visible=False)
        
        # Função para mostrar carregamento de transição no chat
        def show_transition_loading(conn_type):
            """Mostra carregamento de transição apenas no chat"""
            if conn_type == "csv":
                loading_chat = show_loading_in_chat("Fechando postgresql e carregando base csv padrão...")
                return "", loading_chat, gr.update(visible=False)
            else:
                return "", [], gr.update(visible=False)

        # Event handlers (usando as funções originais do sistema)
        def handle_response_with_graph(message, chat_history, model, advanced, processing_enabled, processing_model, conn_type, pg_host, pg_port, pg_db, pg_user, pg_pass, pg_table, pg_single_mode):
            """Wrapper para lidar com resposta e gráfico"""

            # Verifica se há conexão ativa antes de processar
            if not is_connection_ready(conn_type, pg_host, pg_port, pg_db, pg_user, pg_pass):
                error_msg = "⚠️ **Aguarde**: Configure e conecte a uma fonte de dados antes de fazer perguntas."
                chat_history.append({"role": "user", "content": message})
                chat_history.append({"role": "assistant", "content": error_msg})
                return "", chat_history, gr.update(visible=False)

            # Prepara configuração postgresql se necessário
            postgresql_config = None
            if conn_type == "postgresql":
                postgresql_config = {
                    "host": pg_host,
                    "port": pg_port,
                    "database": pg_db,
                    "username": pg_user,
                    "password": pg_pass
                }

            empty_msg, updated_history, graph_path = respond(message, chat_history, model, advanced, processing_enabled, processing_model, conn_type, postgresql_config, pg_table, pg_single_mode)

            # Controla visibilidade do componente de gráfico
            if graph_path:
                return empty_msg, updated_history, gr.update(value=graph_path, visible=True)
            else:
                return empty_msg, updated_history, gr.update(visible=False)

        def toggle_processing_agent(enabled):
            """Controla visibilidade do seletor de modelo do Processing Agent"""
            return gr.update(visible=enabled)

        def toggle_connection_type(conn_type):
            """Controla visibilidade das seções de conexão - FECHA POSTGRES IMEDIATAMENTE"""
            global connection_ready

            if conn_type == "csv":
                # PRIMEIRO: Fecha container postgresql imediatamente
                # SEGUNDO: Executa transição em background
                feedback_msg = load_default_csv_and_cleanup_postgresql()
                if "✅" in feedback_msg:
                    connection_ready = True
                    status_msg = "**Status**: <span class='status-connected'>Base padrão carregada</span>"
                else:
                    connection_ready = False
                    status_msg = "**Status**: <span class='status-error'>Erro na conexão</span>"

                return (
                    gr.update(visible=True),   # csv_section - MOSTRA IMEDIATAMENTE
                    gr.update(visible=False),  # postgresql_section - FECHA IMEDIATAMENTE
                    feedback_msg,              # upload_feedback
                    status_msg,                # connection_status
                    # Limpa campos postgresql IMEDIATAMENTE
                    gr.update(value=""),       # pg_host
                    gr.update(value="5432"),   # pg_port
                    gr.update(value=""),       # pg_database
                    gr.update(value=""),       # pg_username
                    gr.update(value=""),       # pg_password
                    gr.update(value=""),       # pg_feedback
                    gr.update(visible=False),  # pg_table_section
                    gr.update(value=False),    # pg_single_table_mode
                    gr.update(visible=False),  # pg_table_selector_group
                    gr.update(choices=[], value=None),  # pg_table_selector
                    gr.update(value="")        # pg_table_info
                )

            else:  # postgresql
                connection_ready = False
                status_msg = "**Status**: <span class='status-waiting'>Aguardando configuração postgresql</span>"
                return (
                    gr.update(visible=False),  # csv_section
                    gr.update(visible=True),   # postgresql_section
                    "",                        # upload_feedback
                    status_msg,                # connection_status
                    # Mantém campos postgresql como estão
                    gr.update(),  # pg_host
                    gr.update(),  # pg_port
                    gr.update(),  # pg_database
                    gr.update(),  # pg_username
                    gr.update(),  # pg_password
                    gr.update(),  # pg_feedback
                    gr.update(),  # pg_table_section
                    gr.update(),  # pg_single_table_mode
                    gr.update(),  # pg_table_selector_group
                    gr.update(),  # pg_table_selector
                    gr.update()   # pg_table_info
                )

        def handle_postgresql_connect(host, port, database, username, password):
            """Wrapper para conexão postgresql"""
            global connection_ready

            # Executa conexão
            connection_ready = False
            result = handle_postgresql_connection(host, port, database, username, password)

            # Se conexão foi bem-sucedida, retorna tabelas disponíveis
            if "✅" in result:
                connection_ready = True
                try:
                    # Obtém tabelas do ObjectManager
                    from utils.object_manager import get_object_manager
                    obj_manager = get_object_manager()

                    # Busca metadados de conexão mais recente
                    all_metadata = obj_manager.get_all_connection_metadata()
                    if all_metadata:
                        latest_metadata = list(all_metadata.values())[-1]
                        tables = latest_metadata.get("tables", [])

                        # Status de sucesso
                        success_status = "**Status**: <span class='status-connected'>postgresql conectado com sucesso</span>"
                        table_info = f"**Modo Multi-Tabela ativo** - {len(tables)} tabelas disponíveis"

                        # Retorna resultado + atualização do seletor
                        return (
                            f"✅ **Conectado com sucesso!** {len(tables)} tabelas encontradas",  # feedback
                            gr.update(visible=True),  # pg_table_section
                            False,  # pg_single_table_mode (padrão desativado)
                            gr.update(visible=False),  # pg_table_selector_group (oculto por padrão)
                            gr.update(choices=tables, value=tables[0] if tables else None),  # pg_table_selector
                            table_info,  # pg_table_info
                            success_status  # connection_status
                        )
                except Exception as e:
                    logging.error(f"Erro ao obter tabelas: {e}")

            # Se falhou, mantém seção de tabela oculta
            connection_ready = False
            error_status = "**Status**: <span class='status-error'>Falha na conexão postgresql</span>"
            return (
                result,  # feedback
                gr.update(visible=False),  # pg_table_section
                False,  # pg_single_table_mode
                gr.update(visible=False),  # pg_table_selector_group
                gr.update(choices=[], value=None),  # pg_table_selector
                "",  # pg_table_info
                error_status  # connection_status
            )

        def toggle_table_mode(single_mode_enabled, current_table):
            """Alterna entre modo multi-tabela e tabela única"""
            if single_mode_enabled:
                # Modo tabela única ativado
                return (
                    gr.update(visible=True),  # pg_table_selector_group
                    f"**Modo Tabela Única ativo** - Usando: {current_table or 'Selecione uma tabela'}"
                )
            else:
                # Modo multi-tabela ativado
                return (
                    gr.update(visible=False),  # pg_table_selector_group
                    "**Modo Multi-Tabela ativo** - Pode usar todas as tabelas e fazer JOINs"
                )

        msg.submit(
            handle_response_with_graph,
            inputs=[msg, chatbot, model_selector, advanced_checkbox, processing_checkbox, processing_model_selector, connection_type, pg_host, pg_port, pg_database, pg_username, pg_password, pg_table_selector, pg_single_table_mode],
            outputs=[msg, chatbot, graph_image],
            show_progress=True  # Mostra carregamento no input do chat
        )

        btn.click(
            handle_response_with_graph,
            inputs=[msg, chatbot, model_selector, advanced_checkbox, processing_checkbox, processing_model_selector, connection_type, pg_host, pg_port, pg_database, pg_username, pg_password, pg_table_selector, pg_single_table_mode],
            outputs=[msg, chatbot, graph_image]
        )

        csv_file.change(
            handle_csv_and_clear_chat,
            inputs=csv_file,
            outputs=[upload_feedback, chatbot, graph_image, connection_status],
            show_progress="minimal"  # Mostra carregamento mínimo
        )

        reset_btn.click(
            reset_all,
            outputs=[upload_feedback, chatbot, csv_file, graph_image]
        )

        advanced_checkbox.change(
            toggle_advanced_mode,
            inputs=advanced_checkbox,
            outputs=[]
        )

        history_btn.click(
            toggle_history,
            outputs=history_output
        )

        processing_checkbox.change(
            toggle_processing_agent,
            inputs=processing_checkbox,
            outputs=processing_model_selector
        )

        # Executa toggle imediatamente (sem carregamento nos campos)
        connection_type.change(
            toggle_connection_type,
            inputs=connection_type,
            outputs=[
                csv_section, postgresql_section, upload_feedback, connection_status,
                pg_host, pg_port, pg_database, pg_username, pg_password, pg_feedback,
                pg_table_section, pg_single_table_mode, pg_table_selector_group,
                pg_table_selector, pg_table_info
            ],
            show_progress=False  # Não mostra carregamento nos campos
        )

        pg_connect_btn.click(
            handle_postgresql_connect,
            inputs=[pg_host, pg_port, pg_database, pg_username, pg_password],
            outputs=[pg_feedback, pg_table_section, pg_single_table_mode, pg_table_selector_group, pg_table_selector, pg_table_info, connection_status],
            show_progress="minimal"  # Mostra carregamento mínimo
        )

        # Event handler para toggle de modo de tabela
        pg_single_table_mode.change(
            toggle_table_mode,
            inputs=[pg_single_table_mode, pg_table_selector],
            outputs=[pg_table_selector_group, pg_table_info]
        )
    
    return demo

async def main():
    """Função principal"""
    # Inicializa aplicação
    success = await initialize_app()

    if not success:
        logging.error("Falha na inicialização. Encerrando aplicação.")
        return

    # Cria e lança interface
    demo = create_interface()

    # Tenta diferentes portas se a padrão estiver ocupada
    ports_to_try = [GRADIO_PORT, 7861, 7862, 7863, 7864, 0]  # 0 = porta automática

    for port in ports_to_try:
        try:
            logging.info(f"Tentando iniciar interface Gradio na porta {port}")

            # Configurações para Docker
            server_name = "0.0.0.0" if GRADIO_SHARE else "127.0.0.1"

            if GRADIO_SHARE:
                logging.info("🌐 Configurando link público do Gradio...")

            demo.launch(
                server_name=server_name,
                server_port=port if port != 0 else None,
                share=GRADIO_SHARE,
                show_error=True,
                quiet=False
            )
            break  # Se chegou aqui, deu certo
        except OSError as e:
            if "Cannot find empty port" in str(e) and port != ports_to_try[-1]:
                logging.warning(f"Porta {port} ocupada, tentando próxima...")
                continue
            else:
                logging.error(f"Erro ao iniciar servidor: {e}")
                raise
        except Exception as e:
            logging.error(f"Erro inesperado ao iniciar interface: {e}")
            raise

if __name__ == "__main__":
    run_async(main())
