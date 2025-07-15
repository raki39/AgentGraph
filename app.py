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

async def initialize_app():
    """Inicializa a aplicação"""
    global graph_manager
    
    try:
        # Valida configurações
        validate_config()
        
        # Inicializa o grafo
        graph_manager = await initialize_graph()

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
        postgresql_config: Configuração PostgreSQL (se aplicável)
        selected_table: Tabela selecionada (para PostgreSQL)
        single_table_mode: Se deve usar apenas uma tabela (PostgreSQL)

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
    Processa upload de arquivo CSV

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

        # Verifica se é um arquivo CSV
        if not file.name.lower().endswith('.csv'):
            return "❌ Por favor, selecione um arquivo CSV válido."

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
    Processa conexão PostgreSQL

    Args:
        host: Host do PostgreSQL
        port: Porta do PostgreSQL
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
            return "❌ Todos os campos são obrigatórios para conexão PostgreSQL."

        # Valida porta
        try:
            port_int = int(port)
            if port_int < 1 or port_int > 65535:
                return "❌ Porta deve estar entre 1 e 65535."
        except ValueError:
            return "❌ Porta deve ser um número válido."

        # Prepara configuração PostgreSQL
        postgresql_config = {
            "host": host.strip(),
            "port": port_int,
            "database": database.strip(),
            "username": username.strip(),
            "password": password
        }

        # Cria estado inicial para a conexão
        initial_state = {
            "user_input": "Conectar PostgreSQL",
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
        return result.get("message", "Erro na conexão PostgreSQL")

    except Exception as e:
        error_msg = f"❌ Erro ao conectar PostgreSQL: {e}"
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
        postgresql_config: Configuração PostgreSQL (se aplicável)
        selected_table: Tabela selecionada (para PostgreSQL)
        single_table_mode: Se deve usar apenas uma tabela (PostgreSQL)

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
    Processa CSV e limpa chat

    Args:
        file: Arquivo CSV

    Returns:
        Tupla com (feedback, chat_limpo, grafico_limpo)
    """
    feedback = handle_csv_upload(file)
    return feedback, [], gr.update(visible=False)

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

    # CSS customizado para pequeno espaçamento lateral
    custom_css = """
    .gradio-container {
        padding: 20px 30px !important;
    }
    """

    with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Configurações")
                model_selector = gr.Dropdown(list(AVAILABLE_MODELS.keys()), value=DEFAULT_MODEL, label="Modelo LLM")

                # Seleção de tipo de conexão
                gr.Markdown("### Tipo de Conexão")
                connection_type = gr.Radio(
                    choices=["csv", "postgresql"],
                    value="csv",
                    label="",
                    info="Escolha o tipo de conexão de dados"
                )

                # Seção CSV
                with gr.Group(visible=True) as csv_section:
                    gr.Markdown("**Upload CSV**")
                    csv_file = gr.File(file_types=[".csv"], label="Arquivo CSV")
                    upload_feedback = gr.Markdown()

                # Seção PostgreSQL
                with gr.Group(visible=False) as postgresql_section:
                    gr.Markdown("**Conexão PostgreSQL**")
                    pg_host = gr.Textbox(label="Host", placeholder="localhost")
                    pg_port = gr.Textbox(label="Porta", value="5432", placeholder="5432")
                    pg_database = gr.Textbox(label="Banco de Dados", placeholder="nome_do_banco")
                    pg_username = gr.Textbox(label="Usuário", placeholder="usuario")
                    pg_password = gr.Textbox(label="Senha", type="password", placeholder="senha")
                    pg_connect_btn = gr.Button("Conectar PostgreSQL", variant="primary")
                    pg_feedback = gr.Markdown()

                    # Seletor de tabela (visível apenas após conexão)
                    with gr.Group(visible=False) as pg_table_section:
                        gr.Markdown("**Configuração de Tabelas**")

                        # Toggle para modo de tabela única
                        pg_single_table_mode = gr.Checkbox(
                            label="Modo Tabela Única",
                            value=False,
                            info="Ativado: Usar apenas uma tabela | Desativado: Usar todas as tabelas (permite JOINs)"
                        )

                        # Seletor de tabela (visível apenas quando modo único ativado)
                        with gr.Group(visible=False) as pg_table_selector_group:
                            pg_table_selector = gr.Dropdown(
                                choices=[],
                                label="Tabela Selecionada",
                                info="Escolha a tabela para análise (modo único)",
                                interactive=True
                            )

                        pg_table_info = gr.Markdown()

                # Controles do Processing Agent (acima do Refinar Resposta)
                processing_checkbox = gr.Checkbox(label="Usar Processing Agent", value=False)
                processing_model_selector = gr.Dropdown(
                    choices=list(AVAILABLE_MODELS.keys()) + list(REFINEMENT_MODELS.keys()),
                    value="GPT-4o-mini",  # Chave correta do AVAILABLE_MODELS
                    label="Modelo do Processing Agent",
                    visible=False
                )

                advanced_checkbox = gr.Checkbox(label="Refinar Resposta")

                # Status do LangSmith
                if is_langsmith_enabled():
                    gr.Markdown(f"🔍 **LangSmith**: Ativo")
                else:
                    gr.Markdown("🔍 **LangSmith**: Desabilitado")

                reset_btn = gr.Button("Resetar")
                
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
        
        # Event handlers (usando as funções originais do sistema)
        def handle_response_with_graph(message, chat_history, model, advanced, processing_enabled, processing_model, conn_type, pg_host, pg_port, pg_db, pg_user, pg_pass, pg_table, pg_single_mode):
            """Wrapper para lidar com resposta e gráfico"""
            # Prepara configuração PostgreSQL se necessário
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
            """Controla visibilidade das seções de conexão"""
            if conn_type == "csv":
                return gr.update(visible=True), gr.update(visible=False)
            else:  # postgresql
                return gr.update(visible=False), gr.update(visible=True)

        def handle_postgresql_connect(host, port, database, username, password):
            """Wrapper para conexão PostgreSQL"""
            result = handle_postgresql_connection(host, port, database, username, password)

            # Se conexão foi bem-sucedida, retorna tabelas disponíveis
            if "✅" in result:
                try:
                    # Obtém tabelas do ObjectManager
                    from utils.object_manager import get_object_manager
                    obj_manager = get_object_manager()

                    # Busca metadados de conexão mais recente
                    all_metadata = obj_manager.get_all_connection_metadata()
                    if all_metadata:
                        latest_metadata = list(all_metadata.values())[-1]
                        tables = latest_metadata.get("tables", [])

                        # Retorna resultado + atualização do seletor
                        return (
                            result,  # feedback
                            gr.update(visible=True),  # pg_table_section
                            False,  # pg_single_table_mode (padrão desativado)
                            gr.update(visible=False),  # pg_table_selector_group (oculto por padrão)
                            gr.update(choices=tables, value=tables[0] if tables else None),  # pg_table_selector
                            f"**Modo Multi-Tabela ativo** - {len(tables)} tabelas disponíveis: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}"  # pg_table_info
                        )
                except Exception as e:
                    logging.error(f"Erro ao obter tabelas: {e}")

            # Se falhou, mantém seção de tabela oculta
            return (
                result,  # feedback
                gr.update(visible=False),  # pg_table_section
                False,  # pg_single_table_mode
                gr.update(visible=False),  # pg_table_selector_group
                gr.update(choices=[], value=None),  # pg_table_selector
                ""  # pg_table_info
            )

        def toggle_table_mode(single_mode_enabled, current_table):
            """Alterna entre modo multi-tabela e tabela única"""
            if single_mode_enabled:
                # Modo tabela única ativado
                return (
                    gr.update(visible=True),  # pg_table_selector_group
                    f"**Modo Tabela Única ativo** - Usando apenas: {current_table or 'Nenhuma selecionada'}"
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
            outputs=[msg, chatbot, graph_image]
        )

        btn.click(
            handle_response_with_graph,
            inputs=[msg, chatbot, model_selector, advanced_checkbox, processing_checkbox, processing_model_selector, connection_type, pg_host, pg_port, pg_database, pg_username, pg_password, pg_table_selector, pg_single_table_mode],
            outputs=[msg, chatbot, graph_image]
        )

        csv_file.change(
            handle_csv_and_clear_chat,
            inputs=csv_file,
            outputs=[upload_feedback, chatbot, graph_image]
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

        connection_type.change(
            toggle_connection_type,
            inputs=connection_type,
            outputs=[csv_section, postgresql_section]
        )

        pg_connect_btn.click(
            handle_postgresql_connect,
            inputs=[pg_host, pg_port, pg_database, pg_username, pg_password],
            outputs=[pg_feedback, pg_table_section, pg_single_table_mode, pg_table_selector_group, pg_table_selector, pg_table_info]
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
