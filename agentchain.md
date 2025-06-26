import os
import time
import shutil
import pandas as pd
from sqlalchemy import create_engine
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase
from huggingface_hub import InferenceClient
import gradio as gr
from dotenv import load_dotenv
import logging
from sqlalchemy.types import DateTime, Integer, Float

load_dotenv()

UPLOAD_DIR = "uploaded_data"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_CSV_PATH = "tabela.csv"
UPLOADED_CSV_PATH = os.path.join(UPLOAD_DIR, "tabela.csv")
SQL_DB_PATH = "data.db"

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

LLAMA_MODELS = {
    "LLaMA 70B": "meta-llama/Llama-3.3-70B-Instruct",
    "LlaMA 8B": "meta-llama/Llama-3.1-8B-Instruct",
    "Qwen 32B": "Qwen/QwQ-32B"
}

MAX_TOKENS_MAP = {
    "meta-llama/Llama-3.3-70B-Instruct": 900,
    "meta-llama/Llama-3.1-8B-Instruct": 700,
    "Qwen/QwQ-32B": 8192
}

hf_client = InferenceClient(
    provider="together", api_key=HUGGINGFACE_API_KEY
)

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

query_cache = {}
history_log = []  
recent_history = []  
show_history_flag = False
engine = None 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_active_csv_path():
    """Retorna o CSV ativo: o carregado ou o padrão.."""
    if os.path.exists(UPLOADED_CSV_PATH):
        logging.info(f"[CSV] Usando arquivo CSV carregado: {UPLOADED_CSV_PATH}")
        return UPLOADED_CSV_PATH
    else:
        logging.info(f"[CSV] Usando arquivo CSV padrão: {DEFAULT_CSV_PATH}")
        return DEFAULT_CSV_PATH

def create_engine_and_load_db(csv_path, sql_db_path):
    if os.path.exists(sql_db_path):
        print("Banco de dados SQL já existe. Carregando...")
        return create_engine(f"sqlite:///{sql_db_path}")
    else:
        print("Banco de dados SQL não encontrado. Criando...")
        engine = create_engine(f"sqlite:///{sql_db_path}")

        df = pd.read_csv(
            csv_path,
            sep=";",
            encoding='utf-8',
            parse_dates=["DATA_INICIAL", "DATA_FINAL"],
            dayfirst=True,
            on_bad_lines="skip"
        )

        colunas_para_float = [
            "PRECO_VISTA", "PRECO_CHEIO"
        ]

        colunas_para_int = [
            "QUANTIDADE", "TOTAL_PAGINAS_CAPA", "VALOR_MEDIDA", "DIAS_VALIDADE"
        ]

        for col in colunas_para_float:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].replace("-", None), errors="coerce")

        for col in colunas_para_int:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].replace("-", None), errors="coerce")
                df[col] = df[col].where(df[col].dropna() == df[col].dropna().astype(int))
                df[col] = df[col].astype("Int64")

        sql_dtype = {
            "DATA_INICIAL": DateTime(),
            "DATA_FINAL": DateTime(),
            "QUANTIDADE": Integer(),
            "PRECO_VISTA": Float(),
            "PRECO_CHEIO": Float(),
            "TOTAL_PAGINAS_CAPA": Integer(),
            "VALOR_MEDIDA": Integer(),
            "DIAS_VALIDADE": Integer()

        }

        print("[DEBUG] Tipos das colunas:")
        print(df.dtypes)

        df.to_sql("tabela", engine, index=False, if_exists="replace", dtype=sql_dtype)
        print("Banco de dados SQL criado com sucesso!")
        return engine

def handle_csv_upload(file):
    global engine, db, sql_agent

    try:
        file_path = file.name
        shutil.copy(file_path, UPLOADED_CSV_PATH)
        logging.info(f"[UPLOAD] CSV salvo como: {UPLOADED_CSV_PATH}")

        engine = create_engine_and_load_db(UPLOADED_CSV_PATH, SQL_DB_PATH)
        db = SQLDatabase(engine=engine)
        logging.info("[UPLOAD] Novo banco carregado e DB atualizado.")

        sql_agent = create_sql_agent(
            ChatOpenAI(model="gpt-4o-mini", temperature=0),
            db=db,
            agent_type="openai-tools",
            verbose=True,
            max_iterations=40,
            return_intermediate_steps=True
        )
        
        logging.info("[UPLOAD] Novo banco carregado e agente recriado. Cache limpo.")
        query_cache.clear()
        history_log.clear()
        recent_history.clear()

        return "✅ CSV carregado com sucesso!"
        
    except Exception as e:
        logging.error(f"[ERRO] Falha ao processar novo CSV: {e}")
        return f"❌ Erro ao processar CSV: {e}"

def reset_app():
    global engine, db, sql_agent, query_cache, history_log, recent_history
    
    try:
        if os.path.exists(UPLOADED_CSV_PATH):
            os.remove(UPLOADED_CSV_PATH)
            logging.info("[RESET] CSV personalizado removido.")
            
        engine = create_engine_and_load_db(DEFAULT_CSV_PATH, SQL_DB_PATH)
        db = SQLDatabase(engine=engine)
        sql_agent = create_sql_agent(ChatOpenAI(model="gpt-4o-mini", temperature=0), db=db, agent_type="openai-tools", verbose=True, max_iterations=40, return_intermediate_steps=True)
        query_cache.clear()
        history_log.clear()
        recent_history.clear()
        
        return "🔄 Sistema resetado para o estado inicial."
        
    except Exception as e:
        return f"❌ Erro ao resetar: {e}"

engine = create_engine_and_load_db(get_active_csv_path(), SQL_DB_PATH)
db = SQLDatabase(engine=engine)
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
sql_agent = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True, max_iterations=40, return_intermediate_steps=True)

def generate_initial_context(db_sample):
    return (
        f"Você é um assistente que gera queries SQL objetivas e eficientes. Sempre inclua LIMIT 20 nas queries. Aqui está o banco de dados:\n\n"
        f"Exemplos do banco de dados:\n{db_sample.head().to_string(index=False)}\n\n"
        "\n***IMPORTANTE***: Detecte automaticamente o idioma da pergunta do usuário e responda sempre no mesmo idioma."
        "\nEsta base contém os SKUs (produtos) que foram promocionados por meio de TABLOIDE OU PROMOCAO OU ANUNCIO.\n"
        "Cada linha representa um SKU OU PRODUTO único PRESENTE NO TABLOIDE OU PROMOCAO OU ANUNCIO, incluindo sua descrição completa, os veículos OU MIDIAS de promoção utilizados e o respectivo período em que a promoção ocorreu.\n"

        "\nInformações imporatantes:\n"
        "- Use `LIKE '%<palavras-chave>%'` para buscas em colunas de texto.\n"
        "- Quando o usuário mencionar uma categoria, procure nas colunas: `CATEGORIA_PRODUTO_SKU`.\n"
        "- Se o usuário se referir a Nestle, o jeito correto de se escrever é Nestle sem acento e não Nestlé.\n"
        "- Você está usando um banco de dados SQLite.\n"
        
        "\nRetorne apenas a pergunta e a query SQL mais eficiente para entregar ao agent SQL do LangChain para gerar uma resposta para a pergunta. O formato deve ser:\n"
        "\nPergunta: <pergunta do usuário>\n"
        "\nOpção de Query SQL:\n<query SQL>"
        "\nIdioma: <idioma>"
    )

def is_greeting(user_query):
    greetings = ["olá", "oi", "bom dia", "boa tarde", "boa noite", "oi, tudo bem?"]
    return user_query.lower().strip() in greetings

def query_with_llama(user_query, db_sample, selected_model_name):
    model_id = LLAMA_MODELS[selected_model_name]
    max_tokens = MAX_TOKENS_MAP.get(model_id, 512)
    
    initial_context = generate_initial_context(db_sample)
    formatted_history = "\n".join(
        [f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent_history[-2:]]
    )
    
    full_prompt = f"{initial_context}\n\nHistórico recente:\n{formatted_history}\n\nPergunta do usuário:\n{user_query}"
    
    logging.info(f"[DEBUG] Contexto enviado ao ({selected_model_name}):\n{full_prompt}\n")
    
    start_time = time.time()
    
    try:
        response = hf_client.chat.completions.create(
            model=model_id,
            messages=[{"role": "system", "content": full_prompt}],
            max_tokens=max_tokens,
            stream=False
        )
        
        llama_response = response["choices"][0]["message"]["content"]
        end_time = time.time()
        logging.info(f"[DEBUG] Resposta do {selected_model_name} para o Agent SQL:\n{llama_response.strip()}\n[Tempo de execução: {end_time - start_time:.2f}s]\n")
        return llama_response.strip(), model_id
        
    except Exception as e:
        logging.error(f"[ERRO] Falha ao interagir com o modelo {selected_model_name}: {e}")
        return None, model_id

def query_sql_agent(user_query, selected_model_name):
    try:
        if user_query in query_cache:
            print(f"[CACHE] Retornando resposta do cache para a consulta: {user_query}")
            return query_cache[user_query]

        if is_greeting(user_query):
            greeting_response = "Olá! Estou aqui para ajudar com suas consultas. Pergunte algo relacionado aos dados carregados no agente!"
            query_cache[user_query] = greeting_response 
            return greeting_response

        column_data = pd.read_sql_query("SELECT * FROM tabela LIMIT 10", engine)
        llama_instruction = query_with_llama(user_query, column_data, selected_model_name)
        
        if not llama_instruction:
            return "Erro: O modelo Llama não conseguiu gerar uma instrução válida."

        print("------- Agent SQL: Executando query -------")
        response = sql_agent.invoke({"input": llama_instruction})
        sql_response = response.get("output", "Erro ao obter a resposta do agente.")

        query_cache[user_query] = sql_response
        return sql_response
        
    except Exception as e:
        return f"Erro ao consultar o agente SQL: {e}"

advanced_mode_enabled = False  # Novo estado global

def toggle_advanced_mode(state):
    global advanced_mode_enabled
    advanced_mode_enabled = state
    logging.info(f"[MODO AVANÇADO] {'Ativado' if state else 'Desativado'}")
    return "Modo avançado ativado." if state else "Modo avançado desativado."

def refine_response_with_llm(user_question, sql_response, chart_md=""):
    prompt = (
        f"Pergunta do usuário:\n{user_question}\n\n"
        f"Resposta gerada pelo agente SQL:\n{sql_response}\n\n"
        "Sua tarefa é refinar, complementar e melhorar a resposta.\n" 
        "Adicione interpretações estatísticas ou insights relevantes."
    )

    logging.info(f"[DEBUG] Prompt enviado ao modelo de refinamento:\n{prompt}\n")

    try:
        response = hf_client.chat.completions.create(
            model=LLAMA_MODELS["LLaMA 70B"],
            messages=[{"role": "system", "content": prompt}],
            max_tokens=1200,
            stream=False
        )
        improved_response = response["choices"][0]["message"]["content"]
        logging.info(f"[DEBUG] Resposta do modelo de refinamento:\n{improved_response}\n")
        return improved_response + ("\n\n" + chart_md if chart_md else "")

    except Exception as e:
        logging.error(f"[ERRO] Falha ao refinar resposta com LLM: {e}")
        return sql_response + ("\n\n" + chart_md if chart_md else "")

def chatbot_response(user_input, selected_model_name):
    start_time = time.time()
    response = query_sql_agent(user_input, selected_model_name)
    end_time = time.time()

    model_id = LLAMA_MODELS[selected_model_name]

    if advanced_mode_enabled:
        response = refine_response_with_llm(user_input, response)

    history_log.append({
        "Modelo LLM": model_id,
        "Pergunta": user_input,
        "Resposta": response,
        "Tempo de Resposta (s)": round(end_time - start_time, 2)
    })

    recent_history.append({"role": "user", "content": user_input})
    recent_history.append({"role": "assistant", "content": response})

    if len(recent_history) > 4:
        recent_history.pop(0)
        recent_history.pop(0)

    return response

def toggle_history():
    global show_history_flag
    show_history_flag = not show_history_flag
    return history_log if show_history_flag else {}


with gr.Blocks(theme=gr.themes.Soft()) as demo:
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Configurações")
            model_selector = gr.Dropdown(list(LLAMA_MODELS.keys()), value="LLaMA 70B", label="")
            csv_file = gr.File(file_types=[".csv"], label="")
            upload_feedback = gr.Markdown()
            advanced_checkbox = gr.Checkbox(label="Refinar Resposta")
            reset_btn = gr.Button("Resetar")

        with gr.Column(scale=4):
            gr.Markdown("## Reasoning Agent")
            chatbot = gr.Chatbot(height=500)
            msg = gr.Textbox(placeholder="Digite sua pergunta aqui...", lines=1, label="")
            btn = gr.Button("Enviar", variant="primary")
            history_btn = gr.Button("Histórico", variant="secondary")
            history_output = gr.JSON()
            download_file = gr.File(visible=False)

            def respond(message, chat_history, selected_model):
                response = chatbot_response(message, selected_model)
                chat_history.append((message, response))
                return "", chat_history

            def handle_csv_and_clear_chat(file):
                feedback = handle_csv_upload(file)
                return feedback, []

            def reset_all():
                feedback = reset_app()
                return feedback, [], None

            msg.submit(respond, [msg, chatbot, model_selector], [msg, chatbot])
            btn.click(respond, [msg, chatbot, model_selector], [msg, chatbot])
            history_btn.click(toggle_history, outputs=history_output)
            csv_file.change(handle_csv_and_clear_chat, inputs=csv_file, outputs=[upload_feedback, chatbot])
            reset_btn.click(reset_all, outputs=[upload_feedback, chatbot, csv_file])
            advanced_checkbox.change(toggle_advanced_mode, inputs=advanced_checkbox, outputs=[])

if __name__ == "__main__":
    demo.launch(share=False)