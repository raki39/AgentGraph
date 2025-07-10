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

def chatbot_response(user_input: str, selected_model: str, advanced_mode: bool = False, processing_enabled: bool = False, processing_model: str = "GPT-4o-mini") -> Tuple[str, Optional[str]]:
    """
    Processa resposta do chatbot usando LangGraph

    Args:
        user_input: Entrada do usuário
        selected_model: Modelo LLM selecionado
        advanced_mode: Se deve usar refinamento avançado
        processing_enabled: Se o Processing Agent está habilitado
        processing_model: Modelo para o Processing Agent

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
            processing_model=processing_model
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

def respond(message: str, chat_history: List[Dict[str, str]], selected_model: str, advanced_mode: bool, processing_enabled: bool = False, processing_model: str = "GPT-4o-mini"):
    """
    Função de resposta para o chatbot Gradio

    Args:
        message: Mensagem do usuário
        chat_history: Histórico do chat (formato messages)
        selected_model: Modelo selecionado
        advanced_mode: Modo avançado habilitado
        processing_enabled: Se o Processing Agent está habilitado
        processing_model: Modelo para o Processing Agent

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
    response, graph_image_path = chatbot_response(message, selected_model, advanced_mode, processing_enabled, processing_model)

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
                model_selector = gr.Dropdown(list(AVAILABLE_MODELS.keys()), value=DEFAULT_MODEL, label="")
                csv_file = gr.File(file_types=[".csv"], label="")
                upload_feedback = gr.Markdown()
                advanced_checkbox = gr.Checkbox(label="Refinar Resposta")

                # Controles do Processing Agent
                processing_checkbox = gr.Checkbox(label="Usar Processing Agent", value=False)
                processing_model_selector = gr.Dropdown(
                    choices=list(AVAILABLE_MODELS.keys()) + list(REFINEMENT_MODELS.keys()),
                    value="GPT-4o-mini",  # Chave correta do AVAILABLE_MODELS
                    label="Modelo do Processing Agent",
                    visible=False
                )

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
        def handle_response_with_graph(message, chat_history, model, advanced, processing_enabled, processing_model):
            """Wrapper para lidar com resposta e gráfico"""
            empty_msg, updated_history, graph_path = respond(message, chat_history, model, advanced, processing_enabled, processing_model)

            # Controla visibilidade do componente de gráfico
            if graph_path:
                return empty_msg, updated_history, gr.update(value=graph_path, visible=True)
            else:
                return empty_msg, updated_history, gr.update(visible=False)

        def toggle_processing_agent(enabled):
            """Controla visibilidade do seletor de modelo do Processing Agent"""
            return gr.update(visible=enabled)

        msg.submit(
            handle_response_with_graph,
            inputs=[msg, chatbot, model_selector, advanced_checkbox, processing_checkbox, processing_model_selector],
            outputs=[msg, chatbot, graph_image]
        )

        btn.click(
            handle_response_with_graph,
            inputs=[msg, chatbot, model_selector, advanced_checkbox, processing_checkbox, processing_model_selector],
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
            demo.launch(
                share=GRADIO_SHARE,
                server_port=port if port != 0 else None,
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
