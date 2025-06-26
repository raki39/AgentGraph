"""
AgentGraph - Aplicação principal com interface Gradio e LangGraph
"""
import asyncio
import logging
import gradio as gr
from typing import List, Tuple, Optional, Dict

from graphs.main_graph import initialize_graph, get_graph_manager
from utils.config import (
    LLAMA_MODELS, 
    DEFAULT_MODEL, 
    GRADIO_SHARE, 
    GRADIO_PORT,
    validate_config
)

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

def chatbot_response(user_input: str, selected_model: str, advanced_mode: bool = False) -> str:
    """
    Processa resposta do chatbot usando LangGraph

    Args:
        user_input: Entrada do usuário
        selected_model: Modelo LLM selecionado
        advanced_mode: Se deve usar refinamento avançado

    Returns:
        Resposta processada
    """
    global graph_manager

    if not graph_manager:
        return "❌ Sistema não inicializado. Tente recarregar a página."

    try:
        # Processa query através do LangGraph
        result = run_async(graph_manager.process_query(
            user_input=user_input,
            selected_model=selected_model,
            advanced_mode=advanced_mode
        ))

        return result.get("response", "Erro ao processar resposta")

    except Exception as e:
        error_msg = f"Erro no chatbot: {e}"
        logging.error(error_msg)
        logging.error(f"Detalhes do erro: {type(e).__name__}: {str(e)}")
        return error_msg

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

def respond(message: str, chat_history: List[Dict[str, str]], selected_model: str, advanced_mode: bool):
    """
    Função de resposta para o chatbot Gradio

    Args:
        message: Mensagem do usuário
        chat_history: Histórico do chat (formato messages)
        selected_model: Modelo selecionado
        advanced_mode: Modo avançado habilitado

    Returns:
        Tupla com (mensagem_vazia, histórico_atualizado)
    """
    if not message.strip():
        return "", chat_history

    # Processa resposta
    response = chatbot_response(message, selected_model, advanced_mode)

    # Atualiza histórico no formato messages
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": response})

    return "", chat_history

def handle_csv_and_clear_chat(file):
    """
    Processa CSV e limpa chat

    Args:
        file: Arquivo CSV

    Returns:
        Tupla com (feedback, chat_limpo)
    """
    feedback = handle_csv_upload(file)
    return feedback, []

def reset_all():
    """
    Reseta tudo e limpa interface
    
    Returns:
        Tupla com (feedback, chat_limpo, arquivo_limpo)
    """
    feedback = reset_system()
    return feedback, [], None

# Interface Gradio
def create_interface():
    """Cria interface Gradio"""
    
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Configurações")
                model_selector = gr.Dropdown(list(LLAMA_MODELS.keys()), value=DEFAULT_MODEL, label="")
                csv_file = gr.File(file_types=[".csv"], label="")
                upload_feedback = gr.Markdown()
                advanced_checkbox = gr.Checkbox(label="Refinar Resposta")
                reset_btn = gr.Button("Resetar")
                
            with gr.Column(scale=4):
                gr.Markdown("## Reasoning Agent")
                chatbot = gr.Chatbot(
                    height=500,
                    show_label=False,
                    container=True,
                    type="messages"
                )
                msg = gr.Textbox(placeholder="Digite sua pergunta aqui...", lines=1, label="")
                btn = gr.Button("Enviar", variant="primary")
                history_btn = gr.Button("Histórico", variant="secondary")
                history_output = gr.JSON()
                download_file = gr.File(visible=False)
        
        # Event handlers (usando as funções originais do sistema)
        msg.submit(
            respond,
            inputs=[msg, chatbot, model_selector, advanced_checkbox],
            outputs=[msg, chatbot]
        )

        btn.click(
            respond,
            inputs=[msg, chatbot, model_selector, advanced_checkbox],
            outputs=[msg, chatbot]
        )

        csv_file.change(
            handle_csv_and_clear_chat,
            inputs=csv_file,
            outputs=[upload_feedback, chatbot]
        )

        reset_btn.click(
            reset_all,
            outputs=[upload_feedback, chatbot, csv_file]
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
