Tools function:

def generate_graph_type_context(user_query, sql_query, df_columns, df_sample):
    # Criar uma descrição dos dados para ajudar a LLM a entender melhor a estrutura
    data_description = ""
    if not df_sample.empty:
        # Verificar tipos de dados
        numeric_cols = df_sample.select_dtypes(include=['number']).columns.tolist()
        date_cols = [col for col in df_sample.columns if 'data' in col.lower() or df_sample[col].dtype == 'datetime64[ns]']
        categorical_cols = df_sample.select_dtypes(include=['object']).columns.tolist()
        
        # Adicionar informações sobre os primeiros valores de cada coluna
        data_description = "\nAmostra dos dados:\n"
        data_description += df_sample.head(3).to_string()
        
        # Adicionar informações sobre os tipos de dados
        data_description += "\n\nTipos de colunas:"
        if numeric_cols:
            data_description += f"\n- Colunas numéricas: {', '.join(numeric_cols)}"
        if date_cols:
            data_description += f"\n- Colunas de data/tempo: {', '.join(date_cols)}"
        if categorical_cols:
            data_description += f"\n- Colunas categóricas: {', '.join(categorical_cols)}"
    
    return (
        f"Você é um especialista em visualização de dados que escolhe o tipo de gráfico mais adequado para representar dados.\n\n"
        f"Pergunta do usuário: {user_query}\n\n"
        f"Query SQL gerada:\n{sql_query}\n\n"
        f"Colunas retornadas pela query: {', '.join(df_columns)}\n"
        f"{data_description}\n\n"
        "Escolha o tipo de gráfico mais adequado para visualizar esses dados. Considere os seguintes tipos de gráficos e suas aplicações:\n\n"
        "1. Linha Simples → Ideal para mostrar tendências ao longo do tempo ou sequências. Use quando tiver uma coluna de data/tempo/sequência e uma coluna numérica.\n"
        "2. Multilinhas → Ideal para comparar tendências de diferentes categorias ao longo do tempo. Use quando tiver uma coluna de data/tempo e múltiplas colunas numéricas, ou quando tiver uma coluna categórica que pode ser usada para agrupar os dados.\n"
        "3. Área → Similar ao gráfico de linha, mas com área preenchida abaixo da linha. Ideal para mostrar volume ao longo do tempo. Use quando tiver uma coluna de data/tempo e uma coluna numérica.\n"
        "4. Barras Verticais → Ideal para comparar valores entre diferentes categorias. Use quando tiver uma coluna categórica e uma coluna numérica.\n"
        "5. Barras Horizontais → Similar às barras verticais, mas melhor quando há muitas categorias ou nomes longos. Use quando tiver uma coluna categórica e uma coluna numérica.\n"
        "6. Barras Agrupadas → Ideal para comparar valores de múltiplas categorias. Use quando tiver uma coluna categórica e múltiplas colunas numéricas para comparação.\n"
        "7. Barras Empilhadas → Ideal para mostrar partes de um todo por categoria. Use quando tiver uma coluna categórica e múltiplas colunas numéricas que representam partes de um todo.\n"
        "8. Pizza Simples → Ideal para mostrar proporções de um todo. Use quando tiver uma coluna categórica e uma coluna numérica, com poucas categorias (máximo 7).\n"
        "9. Dona → Similar ao gráfico de pizza, mas com um espaço no centro. Melhor para visualizar proporções quando há muitas categorias.\n"
        "10. Pizzas Múltiplas → Ideal para comparar proporções entre diferentes grupos. Use quando tiver duas colunas categóricas e uma coluna numérica.\n\n"
        "Analise cuidadosamente a pergunta do usuário e os dados retornados. Escolha o tipo de gráfico que melhor representa a informação que o usuário está buscando.\n\n"
        "Responda apenas com o número do tipo de gráfico mais adequado (1-10). Não inclua explicações ou texto adicional."
    )


Grapichs function:

def get_graph_type_with_llm(user_query, sql_query, df):
    """Consulta a LLM para determinar o tipo de gráfico mais adequado."""
    # Obter uma amostra dos dados para análise
    df_sample = df.head(3)
    
    graph_type_context = generate_graph_type_context(user_query, sql_query, df.columns.tolist(), df_sample)
    logging.info(f"[DEBUG] Contexto enviado ao Llama para tipo de gráfico:\n{graph_type_context}\n")
    
    try:
        response = hf_client.chat.completions.create(
            model=LLAMA_MODEL,
            messages=[{"role": "system", "content": graph_type_context}],
            max_tokens=10,
            stream=False
        )
        llama_response = response["choices"][0]["message"]["content"].strip()
        logging.info(f"[DEBUG] Resposta do Llama para tipo de gráfico: {llama_response}")
        
        # Mapear a resposta numérica para o tipo de gráfico
        graph_type_map = {
            "1": "line_simple",
            "2": "multiline",
            "3": "area",
            "4": "bar_vertical",
            "5": "bar_horizontal",
            "6": "bar_grouped",
            "7": "bar_stacked",
            "8": "pie",
            "9": "donut",
            "10": "pie_multiple"
        }
        
        # Extrair apenas o número da resposta
        match = re.search(r"\b([1-9]|10)\b", llama_response)
        if match:
            graph_number = match.group(0)
            graph_type = graph_type_map.get(graph_number, "bar_vertical")  # Default para bar_vertical se não encontrar
            logging.info(f"[DEBUG] Tipo de gráfico escolhido pela LLM: {graph_type} (número {graph_number})")
            return graph_type
        else:
            logging.warning("[DEBUG] Não foi possível extrair um número válido da resposta da LLM")
            return "bar_vertical"  # Default para bar_vertical
            
    except Exception as e:
        logging.error(f"[ERRO] Falha ao consultar LLM para tipo de gráfico: {e}")
        return "bar_vertical"  # Default para bar_vertical em caso de erro

def extract_sql_query(llama_response):
    """Extrai e sanitiza a query SQL da resposta do Llama."""
    if "Opção de Query SQL:" in llama_response:
        parts = llama_response.split("Opção de Query SQL:")
        if len(parts) > 1:
            query_part = parts[1].strip()

            # Remove qualquer ocorrência de blocos markdown ```sql ou ```
            query_part = re.sub(r"```sql", "", query_part, flags=re.IGNORECASE)
            query_part = re.sub(r"```", "", query_part)
            query_part = query_part.strip()

            # Remove textos adicionais se existirem
            if "Idioma:" in query_part:
                query_part = query_part.split("Idioma:")[0].strip()
            if "Gráfico:" in query_part:
                query_part = query_part.split("Gráfico:")[0].strip()

            # Remove ponto e vírgula no final
            if query_part.endswith(";"):
                query_part = query_part[:-1].strip()

            return query_part
    return None

def should_generate_graph(llama_response):
    """Verifica se a resposta do Llama indica que um gráfico deve ser gerado."""
    logging.info(f"[DEBUG] Verificando se deve gerar gráfico na resposta: {llama_response}")
    
    # Usar expressão regular para encontrar "Gráfico: sim" independente de maiúsculas/minúsculas
    match = re.search(r"Gr[áa]fico\s*:\s*[Ss][Ii][Mm]", llama_response)
    if match:
        logging.info(f"[DEBUG] Encontrou indicação de gráfico: {match.group(0)}")
        return True
    
    logging.info("[DEBUG] Não encontrou indicação de gráfico")
    return False

def analyze_dataframe(df):
    """Analisa o DataFrame para determinar características importantes para visualização."""
    analysis = {
        "num_rows": len(df),
        "num_cols": len(df.columns),
        "numeric_cols": [],
        "date_cols": [],
        "categorical_cols": [],
        "time_series": False,
        "multi_numeric": False,
        "has_categories": False
    }
    
    # Identificar tipos de colunas
    for col in df.columns:
        # Verificar se é coluna numérica
        if pd.api.types.is_numeric_dtype(df[col]):
            analysis["numeric_cols"].append(col)
        # Verificar se é coluna de data
        elif pd.api.types.is_datetime64_any_dtype(df[col]) or 'data' in col.lower():
            analysis["date_cols"].append(col)
            analysis["time_series"] = True
        # Caso contrário, considerar categórica
        else:
            analysis["categorical_cols"].append(col)
            analysis["has_categories"] = True
    
    # Verificar se há múltiplas colunas numéricas
    if len(analysis["numeric_cols"]) > 1:
        analysis["multi_numeric"] = True
    
    # Tentar converter colunas de data que não foram detectadas automaticamente
    for col in analysis["categorical_cols"]:
        if 'data' in col.lower() or 'date' in col.lower():
            try:
                # Tentar converter para datetime
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if not df[col].isna().all():  # Se pelo menos um valor foi convertido com sucesso
                    analysis["date_cols"].append(col)
                    analysis["categorical_cols"].remove(col)
                    analysis["time_series"] = True
            except:
                pass
    
    return analysis

def prepare_data_for_graph(df, graph_type, user_query):
    """Prepara os dados para o gráfico, adaptando-os conforme necessário."""
    logging.info(f"[DEBUG] Preparando dados para gráfico tipo {graph_type}")
    
    # Verificar se o DataFrame está vazio
    if df.empty:
        logging.warning("[DEBUG] DataFrame vazio, não é possível preparar dados")
        return df
    
    # Fazer uma cópia para não modificar o original
    prepared_df = df.copy()
    
    # Analisar o DataFrame
    analysis = analyze_dataframe(prepared_df)
    logging.info(f"[DEBUG] Análise do DataFrame: {analysis}")
    
    # Converter colunas de data para datetime se existirem
    for col in prepared_df.columns:
        if col in analysis["date_cols"] and not pd.api.types.is_datetime64_any_dtype(prepared_df[col]):
            try:
                prepared_df[col] = pd.to_datetime(prepared_df[col])
                logging.info(f"[DEBUG] Convertida coluna {col} para datetime")
            except:
                logging.warning(f"[DEBUG] Não foi possível converter coluna {col} para datetime")
    
    # Preparação específica para cada tipo de gráfico
    if graph_type == 'line_simple':
        # Para gráfico de linha simples, precisamos de uma coluna para o eixo x (preferencialmente data) e uma coluna numérica
        if analysis["time_series"] and len(analysis["numeric_cols"]) > 0:
            # Usar a primeira coluna de data como x e a primeira coluna numérica como y
            x_col = analysis["date_cols"][0]
            y_col = analysis["numeric_cols"][0]
            
            # Ordenar por data
            prepared_df = prepared_df.sort_values(by=x_col)
            logging.info(f"[DEBUG] Dados ordenados pela coluna de data {x_col}")
            
            # Selecionar apenas as colunas necessárias
            prepared_df = prepared_df[[x_col, y_col]]
        
        elif len(analysis["categorical_cols"]) > 0 and len(analysis["numeric_cols"]) > 0:
            # Se não tiver data, usar a primeira coluna categórica como x e a primeira numérica como y
            x_col = analysis["categorical_cols"][0]
            y_col = analysis["numeric_cols"][0]
            
            # Ordenar por valor numérico para melhor visualização
            prepared_df = prepared_df.sort_values(by=y_col)
            logging.info(f"[DEBUG] Dados ordenados pela coluna numérica {y_col}")
            
            # Selecionar apenas as colunas necessárias
            prepared_df = prepared_df[[x_col, y_col]]
    
    elif graph_type == 'multiline':
        # Para gráfico de multilinhas, precisamos de uma coluna para o eixo x e múltiplas colunas numéricas
        if analysis["time_series"] and analysis["multi_numeric"]:
            # Usar a primeira coluna de data como x e todas as colunas numéricas
            x_col = analysis["date_cols"][0]
            
            # Ordenar por data
            prepared_df = prepared_df.sort_values(by=x_col)
            logging.info(f"[DEBUG] Dados ordenados pela coluna de data {x_col}")
            
            # Selecionar apenas as colunas necessárias (data + todas numéricas)
            cols_to_keep = [x_col] + analysis["numeric_cols"]
            prepared_df = prepared_df[cols_to_keep]
        
        elif len(analysis["categorical_cols"]) > 0 and analysis["multi_numeric"]:
            # Se não tiver data, usar a primeira coluna categórica como x e todas as numéricas
            x_col = analysis["categorical_cols"][0]
            
            # Selecionar apenas as colunas necessárias (categórica + todas numéricas)
            cols_to_keep = [x_col] + analysis["numeric_cols"]
            prepared_df = prepared_df[cols_to_keep]
        
        elif len(analysis["categorical_cols"]) >= 2 and len(analysis["numeric_cols"]) > 0:
            # Se tiver duas colunas categóricas, podemos usar uma para agrupar
            cat1 = analysis["categorical_cols"][0]
            cat2 = analysis["categorical_cols"][1]
            val_col = analysis["numeric_cols"][0]
            
            # Criar um pivot para multilinhas
            try:
                pivot_df = prepared_df.pivot_table(index=cat1, columns=cat2, values=val_col, aggfunc='mean')
                prepared_df = pivot_df.reset_index()
                logging.info(f"[DEBUG] Criado pivot com índice={cat1}, colunas={cat2}, valores={val_col}")
            except Exception as e:
                logging.error(f"[ERRO] Falha ao criar pivot para multilinhas: {e}")
    
    elif graph_type == 'area':
        # Similar ao gráfico de linha simples
        if analysis["time_series"] and len(analysis["numeric_cols"]) > 0:
            x_col = analysis["date_cols"][0]
            y_col = analysis["numeric_cols"][0]
            
            # Ordenar por data
            prepared_df = prepared_df.sort_values(by=x_col)
            
            # Selecionar apenas as colunas necessárias
            prepared_df = prepared_df[[x_col, y_col]]
        
        elif len(analysis["categorical_cols"]) > 0 and len(analysis["numeric_cols"]) > 0:
            x_col = analysis["categorical_cols"][0]
            y_col = analysis["numeric_cols"][0]
            
            # Ordenar por valor numérico
            prepared_df = prepared_df.sort_values(by=y_col)
            
            # Selecionar apenas as colunas necessárias
            prepared_df = prepared_df[[x_col, y_col]]
    
    elif graph_type in ['bar_vertical', 'bar_horizontal']:
        # Para gráficos de barras, precisamos de uma coluna categórica e uma numérica
        if len(analysis["categorical_cols"]) > 0 and len(analysis["numeric_cols"]) > 0:
            x_col = analysis["categorical_cols"][0]
            y_col = analysis["numeric_cols"][0]
            
            # Ordenar por valor numérico em ordem decrescente
            prepared_df = prepared_df.sort_values(by=y_col, ascending=False)
            logging.info(f"[DEBUG] Dados ordenados pela coluna {y_col} em ordem decrescente")
            
            # Limitar o número de categorias se for muito grande
            if len(prepared_df) > 15 and graph_type == 'bar_vertical':
                logging.info(f"[DEBUG] Limitando dados para gráfico de barras verticais (de {len(prepared_df)} para 15 linhas)")
                prepared_df = prepared_df.head(15)
            
            # Selecionar apenas as colunas necessárias
            prepared_df = prepared_df[[x_col, y_col]]
    
    elif graph_type == 'bar_grouped':
        # Para barras agrupadas, precisamos de uma coluna categórica e múltiplas numéricas
        if len(analysis["categorical_cols"]) > 0 and analysis["multi_numeric"]:
            x_col = analysis["categorical_cols"][0]
            
            # Limitar o número de categorias
            if len(prepared_df) > 10:
                logging.info(f"[DEBUG] Limitando dados para gráfico de barras agrupadas (de {len(prepared_df)} para 10 linhas)")
                prepared_df = prepared_df.head(10)
            
            # Selecionar apenas as colunas necessárias (categórica + todas numéricas)
            cols_to_keep = [x_col] + analysis["numeric_cols"]
            prepared_df = prepared_df[cols_to_keep]
        
        elif len(analysis["categorical_cols"]) >= 2 and len(analysis["numeric_cols"]) > 0:
            # Se tiver duas colunas categóricas, podemos usar uma para agrupar
            cat1 = analysis["categorical_cols"][0]
            cat2 = analysis["categorical_cols"][1]
            val_col = analysis["numeric_cols"][0]
            
            # Limitar o número de categorias
            unique_cat1 = prepared_df[cat1].nunique()
            unique_cat2 = prepared_df[cat2].nunique()
            
            if unique_cat1 > 10 or unique_cat2 > 10:
                logging.info(f"[DEBUG] Muitas categorias para barras agrupadas, limitando dados")
                # Pegar as categorias mais frequentes
                top_cat1 = prepared_df[cat1].value_counts().head(10).index.tolist()
                top_cat2 = prepared_df[cat2].value_counts().head(10).index.tolist()
                
                prepared_df = prepared_df[
                    prepared_df[cat1].isin(top_cat1) & 
                    prepared_df[cat2].isin(top_cat2)
                ]
            
            # Criar um pivot para barras agrupadas
            try:
                pivot_df = prepared_df.pivot_table(index=cat1, columns=cat2, values=val_col, aggfunc='mean')
                prepared_df = pivot_df.reset_index()
                logging.info(f"[DEBUG] Criado pivot com índice={cat1}, colunas={cat2}, valores={val_col}")
            except Exception as e:
                logging.error(f"[ERRO] Falha ao criar pivot para barras agrupadas: {e}")
    
    elif graph_type == 'bar_stacked':
        # Similar ao bar_grouped, mas para mostrar partes de um todo
        if len(analysis["categorical_cols"]) >= 2 and len(analysis["numeric_cols"]) > 0:
            cat1 = analysis["categorical_cols"][0]
            cat2 = analysis["categorical_cols"][1]
            val_col = analysis["numeric_cols"][0]
            
            # Limitar o número de categorias
            unique_cat1 = prepared_df[cat1].nunique()
            unique_cat2 = prepared_df[cat2].nunique()
            
            if unique_cat1 > 10 or unique_cat2 > 10:
                logging.info(f"[DEBUG] Muitas categorias para barras empilhadas, limitando dados")
                # Pegar as categorias mais frequentes
                top_cat1 = prepared_df[cat1].value_counts().head(10).index.tolist()
                top_cat2 = prepared_df[cat2].value_counts().head(10).index.tolist()
                
                prepared_df = prepared_df[
                    prepared_df[cat1].isin(top_cat1) & 
                    prepared_df[cat2].isin(top_cat2)
                ]
            
            # Criar um pivot para barras empilhadas
            try:
                pivot_df = prepared_df.pivot_table(index=cat1, columns=cat2, values=val_col, aggfunc='mean')
                prepared_df = pivot_df.reset_index()
                logging.info(f"[DEBUG] Criado pivot com índice={cat1}, colunas={cat2}, valores={val_col}")
            except Exception as e:
                logging.error(f"[ERRO] Falha ao criar pivot para barras empilhadas: {e}")
        
        elif len(analysis["categorical_cols"]) > 0 and analysis["multi_numeric"]:
            # Se tiver uma coluna categórica e múltiplas numéricas
            x_col = analysis["categorical_cols"][0]
            
            # Limitar o número de categorias
            if len(prepared_df) > 10:
                logging.info(f"[DEBUG] Limitando dados para gráfico de barras empilhadas (de {len(prepared_df)} para 10 linhas)")
                prepared_df = prepared_df.head(10)
            
            # Selecionar apenas as colunas necessárias (categórica + todas numéricas)
            cols_to_keep = [x_col] + analysis["numeric_cols"]
            prepared_df = prepared_df[cols_to_keep]
    
    elif graph_type in ['pie', 'donut']:
        # Para gráficos de pizza/donut, precisamos de uma coluna categórica e uma numérica
        if len(analysis["categorical_cols"]) > 0 and len(analysis["numeric_cols"]) > 0:
            cat_col = analysis["categorical_cols"][0]
            val_col = analysis["numeric_cols"][0]
            
            # Limitar o número de categorias para no máximo 10
            if prepared_df[cat_col].nunique() > 10:
                logging.info(f"[DEBUG] Limitando categorias para gráfico de pizza/donut")
                
                # Agrupar por categoria e somar valores
                grouped = prepared_df.groupby(cat_col)[val_col].sum().reset_index()
                
                # Ordenar por valor e pegar as 9 maiores categorias
                grouped = grouped.sort_values(by=val_col, ascending=False)
                top_9 = grouped.head(9)
                
                # Agrupar o resto como "Outros"
                if len(grouped) > 9:
                    others_sum = grouped.iloc[9:][val_col].sum()
                    others_row = pd.DataFrame({cat_col: ['Outros'], val_col: [others_sum]})
                    prepared_df = pd.concat([top_9, others_row], ignore_index=True)
                    logging.info(f"[DEBUG] Criada categoria 'Outros' com valor {others_sum}")
                else:
                    prepared_df = top_9
            else:
                # Agrupar por categoria e somar valores
                prepared_df = prepared_df.groupby(cat_col)[val_col].sum().reset_index()
            
            # Ordenar por valor em ordem decrescente
            prepared_df = prepared_df.sort_values(by=val_col, ascending=False)
            
            # Selecionar apenas as colunas necessárias
            prepared_df = prepared_df[[cat_col, val_col]]
    
    elif graph_type == 'pie_multiple':
        # Para múltiplos gráficos de pizza, precisamos de duas colunas categóricas e uma numérica
        if len(analysis["categorical_cols"]) >= 2 and len(analysis["numeric_cols"]) > 0:
            cat1 = analysis["categorical_cols"][0]
            cat2 = analysis["categorical_cols"][1]
            val_col = analysis["numeric_cols"][0]
            
            # Limitar o número de categorias
            unique_cat1 = prepared_df[cat1].nunique()
            unique_cat2 = prepared_df[cat2].nunique()
            
            if unique_cat1 > 6 or unique_cat2 > 10:
                logging.info(f"[DEBUG] Muitas categorias para múltiplos gráficos de pizza, limitando dados")
                # Pegar as categorias mais frequentes
                top_cat1 = prepared_df[cat1].value_counts().head(6).index.tolist()
                top_cat2 = prepared_df[cat2].value_counts().head(10).index.tolist()
                
                prepared_df = prepared_df[
                    prepared_df[cat1].isin(top_cat1) & 
                    prepared_df[cat2].isin(top_cat2)
                ]
            
            # Agrupar e somar valores
            prepared_df = prepared_df.groupby([cat1, cat2])[val_col].sum().reset_index()
    
    # Verificar se há palavras-chave na pergunta do usuário que possam ajudar a identificar colunas importantes
    if user_query:
        user_query_lower = user_query.lower()
        
        # Procurar por colunas mencionadas na pergunta
        for col in df.columns:
            col_lower = col.lower()
            # Verificar se o nome da coluna (ou parte dele) está na pergunta
            if col_lower in user_query_lower or any(part in user_query_lower for part in col_lower.split('_')):
                logging.info(f"[DEBUG] Coluna {col} mencionada na pergunta do usuário")
                
                # Se for uma coluna numérica e o gráfico for de barras, linha ou área, priorizar esta coluna
                if col in analysis["numeric_cols"] and graph_type in ['bar_vertical', 'bar_horizontal', 'line_simple', 'area']:
                    if len(analysis["categorical_cols"]) > 0:
                        cat_col = analysis["categorical_cols"][0]
                        prepared_df = df[[cat_col, col]].copy()
                        prepared_df = prepared_df.sort_values(by=col, ascending=False)
                        logging.info(f"[DEBUG] Priorizando coluna {col} mencionada na pergunta")
                        break
    
    logging.info(f"[DEBUG] Dados preparados: {len(prepared_df)} linhas, colunas: {prepared_df.columns.tolist()}")
    return prepared_df

def generate_graph(df, graph_type, title=None, user_query=None):
    """Gera um gráfico com base no DataFrame e tipo especificado."""
    logging.info(f"[DEBUG] Iniciando geração de gráfico tipo {graph_type}. DataFrame vazio? {df.empty}")
    if df.empty:
        logging.info("[DEBUG] DataFrame vazio, não é possível gerar gráfico")
        return None
    
    # Preparar dados para o gráfico
    prepared_df = prepare_data_for_graph(df, graph_type, user_query)
    if prepared_df.empty:
        logging.info("[DEBUG] DataFrame preparado está vazio, não é possível gerar gráfico")
        return None
    
    try:
        # Analisar o DataFrame preparado
        analysis = analyze_dataframe(prepared_df)
        
        # Configurações gerais para todos os gráficos
        plt.figure(figsize=(12, 8))
        plt.title(title or "Visualização de Dados", fontsize=14)
        
        # Definir cores atraentes
        colors = plt.cm.tab10.colors
        
        # Gerar gráfico com base no tipo
        if graph_type == 'line_simple':
            if len(prepared_df.columns) >= 2:
                x_col = prepared_df.columns[0]
                y_col = prepared_df.columns[1]
                logging.info(f"[DEBUG] Criando gráfico de linha simples com x={x_col}, y={y_col}")
                
                # Verificar se x é data
                is_date = pd.api.types.is_datetime64_any_dtype(prepared_df[x_col])
                
                # Criar gráfico de linha
                plt.figure(figsize=(12, 6))
                
                if is_date:
                    # Formatar eixo x para datas
                    plt.plot(prepared_df[x_col], prepared_df[y_col], marker='o', linewidth=2, color=colors[0])
                    plt.gcf().autofmt_xdate()
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
                else:
                    plt.plot(range(len(prepared_df)), prepared_df[y_col], marker='o', linewidth=2, color=colors[0])
                    plt.xticks(range(len(prepared_df)), prepared_df[x_col], rotation=45, ha='right')
                
                # Adicionar rótulos nos pontos
                for i, y in enumerate(prepared_df[y_col]):
                    if isinstance(y, (int, float)):
                        plt.annotate(f'{y:.2f}', (i, y), textcoords="offset points", 
                                    xytext=(0, 5), ha='center', fontsize=9)
                
                plt.xlabel(x_col)
                plt.ylabel(y_col)
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.tight_layout()
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de linha simples")
                return None
        
        elif graph_type == 'multiline':
            # Verificar se temos um DataFrame pivotado (primeira coluna categórica, resto numéricas)
            if len(prepared_df.columns) >= 2:
                x_col = prepared_df.columns[0]
                
                # Verificar se x é data
                is_date = pd.api.types.is_datetime64_any_dtype(prepared_df[x_col])
                
                # Obter colunas numéricas (todas exceto a primeira)
                y_cols = [col for col in prepared_df.columns[1:] if pd.api.types.is_numeric_dtype(prepared_df[col])]
                
                if y_cols:
                    logging.info(f"[DEBUG] Criando gráfico de multilinhas com x={x_col}, y={y_cols}")
                    
                    plt.figure(figsize=(12, 6))
                    
                    # Plotar cada linha
                    for i, y_col in enumerate(y_cols):
                        if is_date:
                            plt.plot(prepared_df[x_col], prepared_df[y_col], marker='o', linewidth=2, 
                                    label=y_col, color=colors[i % len(colors)])
                        else:
                            plt.plot(range(len(prepared_df)), prepared_df[y_col], marker='o', linewidth=2, 
                                    label=y_col, color=colors[i % len(colors)])
                    
                    if is_date:
                        plt.gcf().autofmt_xdate()
                        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
                    else:
                        plt.xticks(range(len(prepared_df)), prepared_df[x_col], rotation=45, ha='right')
                    
                    plt.xlabel(x_col)
                    plt.ylabel("Valores")
                    plt.legend(title="Séries", loc='best')
                    plt.grid(True, linestyle='--', alpha=0.7)
                    plt.tight_layout()
                else:
                    logging.warning("[DEBUG] Não há colunas numéricas para gráfico de multilinhas")
                    # Fallback para linha simples
                    return generate_graph(df, 'line_simple', title, user_query)
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de multilinhas")
                # Fallback para linha simples
                return generate_graph(df, 'line_simple', title, user_query)
        
        elif graph_type == 'area':
            if len(prepared_df.columns) >= 2:
                x_col = prepared_df.columns[0]
                y_col = prepared_df.columns[1]
                logging.info(f"[DEBUG] Criando gráfico de área com x={x_col}, y={y_col}")
                
                # Verificar se x é data
                is_date = pd.api.types.is_datetime64_any_dtype(prepared_df[x_col])
                
                plt.figure(figsize=(12, 6))
                
                if is_date:
                    # Formatar eixo x para datas
                    plt.fill_between(prepared_df[x_col], prepared_df[y_col], alpha=0.5, color=colors[0])
                    plt.plot(prepared_df[x_col], prepared_df[y_col], color=colors[0], linewidth=2)
                    plt.gcf().autofmt_xdate()
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
                else:
                    plt.fill_between(range(len(prepared_df)), prepared_df[y_col], alpha=0.5, color=colors[0])
                    plt.plot(range(len(prepared_df)), prepared_df[y_col], color=colors[0], linewidth=2)
                    plt.xticks(range(len(prepared_df)), prepared_df[x_col], rotation=45, ha='right')
                
                plt.xlabel(x_col)
                plt.ylabel(y_col)
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.tight_layout()
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de área")
                # Fallback para linha simples
                return generate_graph(df, 'line_simple', title, user_query)
        
        elif graph_type == 'bar_vertical':
            if len(prepared_df.columns) >= 2:
                x_col = prepared_df.columns[0]
                y_col = prepared_df.columns[1]
                logging.info(f"[DEBUG] Criando gráfico de barras verticais com x={x_col}, y={y_col}")
                
                plt.figure(figsize=(12, 8))
                bars = plt.bar(range(len(prepared_df)), prepared_df[y_col], color=colors[0])
                
                # Adicionar valores nas barras
                for i, bar in enumerate(bars):
                    height = bar.get_height()
                    if isinstance(height, (int, float)):
                        plt.text(bar.get_x() + bar.get_width()/2., height + 0.02 * max(prepared_df[y_col]),
                                f'{height:.2f}', ha='center', fontsize=9)
                
                plt.xlabel(x_col)
                plt.ylabel(y_col)
                plt.xticks(range(len(prepared_df)), prepared_df[x_col], rotation=45, ha='right')
                plt.grid(True, linestyle='--', alpha=0.7, axis='y')
                plt.tight_layout()
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de barras verticais")
                return None
        
        elif graph_type == 'bar_horizontal':
            if len(prepared_df.columns) >= 2:
                x_col = prepared_df.columns[0]
                y_col = prepared_df.columns[1]
                logging.info(f"[DEBUG] Criando gráfico de barras horizontais com x={x_col}, y={y_col}")
                
                plt.figure(figsize=(12, max(6, len(prepared_df) * 0.4)))  # Ajustar altura com base no número de categorias
                bars = plt.barh(range(len(prepared_df)), prepared_df[y_col], color=colors[0])
                
                # Adicionar valores nas barras
                for i, bar in enumerate(bars):
                    width = bar.get_width()
                    if isinstance(width, (int, float)):
                        plt.text(width + 0.02 * max(prepared_df[y_col]), bar.get_y() + bar.get_height()/2.,
                                f'{width:.2f}', va='center', fontsize=9)
                
                plt.xlabel(y_col)
                plt.ylabel(x_col)
                plt.yticks(range(len(prepared_df)), prepared_df[x_col])
                plt.grid(True, linestyle='--', alpha=0.7, axis='x')
                plt.tight_layout()
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de barras horizontais")
                return None
        
        elif graph_type == 'bar_grouped':
            # Verificar se temos um DataFrame pivotado (primeira coluna categórica, resto numéricas)
            if len(prepared_df.columns) >= 3:
                x_col = prepared_df.columns[0]
                
                # Obter colunas numéricas (todas exceto a primeira)
                y_cols = [col for col in prepared_df.columns[1:] if pd.api.types.is_numeric_dtype(prepared_df[col])]
                
                if y_cols:
                    logging.info(f"[DEBUG] Criando gráfico de barras agrupadas com x={x_col}, valores={y_cols}")
                    
                    # Configurar largura e posições das barras
                    x = np.arange(len(prepared_df))
                    width = 0.8 / len(y_cols)
                    
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    # Plotar cada grupo de barras
                    for i, col in enumerate(y_cols):
                        offset = width * i - width * (len(y_cols) - 1) / 2
                        bars = ax.bar(x + offset, prepared_df[col], width, label=col)
                        
                        # Adicionar valores nas barras
                        for bar in bars:
                            height = bar.get_height()
                            if isinstance(height, (int, float)) and not np.isnan(height):
                                ax.text(bar.get_x() + bar.get_width()/2., height + 0.02 * prepared_df[y_cols].max().max(),
                                        f'{height:.2f}', ha='center', fontsize=8)
                    
                    ax.set_xlabel(x_col)
                    ax.set_ylabel('Valores')
                    ax.set_xticks(x)
                    ax.set_xticklabels(prepared_df[x_col], rotation=45, ha='right')
                    ax.legend()
                    ax.grid(True, linestyle='--', alpha=0.7, axis='y')
                    plt.tight_layout()
                else:
                    logging.warning("[DEBUG] Não há colunas numéricas suficientes para gráfico de barras agrupadas")
                    # Fallback para barras verticais
                    return generate_graph(df, 'bar_vertical', title, user_query)
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de barras agrupadas")
                # Fallback para barras verticais
                return generate_graph(df, 'bar_vertical', title, user_query)
        
        elif graph_type == 'bar_stacked':
            # Verificar se temos um DataFrame pivotado (primeira coluna categórica, resto numéricas)
            if len(prepared_df.columns) >= 3:
                x_col = prepared_df.columns[0]
                
                # Obter colunas numéricas (todas exceto a primeira)
                y_cols = [col for col in prepared_df.columns[1:] if pd.api.types.is_numeric_dtype(prepared_df[col])]
                
                if y_cols:
                    logging.info(f"[DEBUG] Criando gráfico de barras empilhadas com x={x_col}, valores={y_cols}")
                    
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    # Criar barras empilhadas
                    bottom = np.zeros(len(prepared_df))
                    
                    for i, col in enumerate(y_cols):
                        bars = ax.bar(range(len(prepared_df)), prepared_df[col], bottom=bottom, label=col)
                        
                        # Adicionar valores nas barras
                        for j, bar in enumerate(bars):
                            height = bar.get_height()
                            if isinstance(height, (int, float)) and height > 0:
                                ax.text(bar.get_x() + bar.get_width()/2., bottom[j] + height/2,
                                        f'{height:.2f}', ha='center', va='center', fontsize=8, color='white')
                        
                        bottom += prepared_df[col].fillna(0)
                    
                    ax.set_xlabel(x_col)
                    ax.set_ylabel('Valores')
                    ax.set_xticks(range(len(prepared_df)))
                    ax.set_xticklabels(prepared_df[x_col], rotation=45, ha='right')
                    ax.legend()
                    plt.tight_layout()
                else:
                    logging.warning("[DEBUG] Não há colunas numéricas suficientes para gráfico de barras empilhadas")
                    # Fallback para barras verticais
                    return generate_graph(df, 'bar_vertical', title, user_query)
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de barras empilhadas")
                # Fallback para barras verticais
                return generate_graph(df, 'bar_vertical', title, user_query)
        
        elif graph_type == 'pie':
            if len(prepared_df.columns) >= 2:
                label_col = prepared_df.columns[0]
                value_col = prepared_df.columns[1]
                logging.info(f"[DEBUG] Criando gráfico de pizza com labels={label_col}, valores={value_col}")
                
                # Verificar se os valores são numéricos
                if pd.api.types.is_numeric_dtype(prepared_df[value_col]):
                    # Remover valores negativos ou zero
                    prepared_df = prepared_df[prepared_df[value_col] > 0]
                    
                    if prepared_df.empty:
                        logging.warning("[DEBUG] Não há valores positivos para gráfico de pizza")
                        return None
                    
                    plt.figure(figsize=(10, 10))
                    
                    # Calcular percentuais para os rótulos
                    total = prepared_df[value_col].sum()
                    labels = [f'{label} ({val:.2f}, {val/total:.1%})' for label, val in zip(prepared_df[label_col], prepared_df[value_col])]
                    
                    plt.pie(prepared_df[value_col], labels=labels, autopct='%1.1f%%', 
                            startangle=90, shadow=False, colors=colors[:len(prepared_df)])
                    
                    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                    plt.title(title or f"Distribuição de {value_col} por {label_col}")
                    plt.tight_layout()
                else:
                    logging.warning(f"[DEBUG] Coluna {value_col} não é numérica para gráfico de pizza")
                    # Fallback para barras verticais
                    return generate_graph(df, 'bar_vertical', title, user_query)
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de pizza")
                # Fallback para barras verticais
                return generate_graph(df, 'bar_vertical', title, user_query)
        
        elif graph_type == 'donut':
            if len(prepared_df.columns) >= 2:
                label_col = prepared_df.columns[0]
                value_col = prepared_df.columns[1]
                logging.info(f"[DEBUG] Criando gráfico de donut com labels={label_col}, valores={value_col}")
                
                # Verificar se os valores são numéricos
                if pd.api.types.is_numeric_dtype(prepared_df[value_col]):
                    # Remover valores negativos ou zero
                    prepared_df = prepared_df[prepared_df[value_col] > 0]
                    
                    if prepared_df.empty:
                        logging.warning("[DEBUG] Não há valores positivos para gráfico de donut")
                        return None
                    
                    plt.figure(figsize=(10, 10))
                    
                    # Calcular percentuais para os rótulos
                    total = prepared_df[value_col].sum()
                    labels = [f'{label} ({val:.2f}, {val/total:.1%})' for label, val in zip(prepared_df[label_col], prepared_df[value_col])]
                    
                    # Criar gráfico de donut (pizza com círculo central)
                    plt.pie(prepared_df[value_col], labels=labels, autopct='%1.1f%%', 
                            startangle=90, shadow=False, colors=colors[:len(prepared_df)],
                            wedgeprops=dict(width=0.5))  # Largura do anel
                    
                    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                    plt.title(title or f"Distribuição de {value_col} por {label_col}")
                    plt.tight_layout()
                else:
                    logging.warning(f"[DEBUG] Coluna {value_col} não é numérica para gráfico de donut")
                    # Fallback para barras verticais
                    return generate_graph(df, 'bar_vertical', title, user_query)
            else:
                logging.warning("[DEBUG] Dados insuficientes para gráfico de donut")
                # Fallback para barras verticais
                return generate_graph(df, 'bar_vertical', title, user_query)
        
        elif graph_type == 'pie_multiple':
            # Verificar se temos dados agrupados por duas categorias
            if len(prepared_df.columns) >= 3:
                cat1 = prepared_df.columns[0]
                cat2 = prepared_df.columns[1]
                val_col = prepared_df.columns[2]
                
                logging.info(f"[DEBUG] Criando múltiplos gráficos de pizza com grupo={cat1}, categorias={cat2}, valor={val_col}")
                
                # Verificar se o valor é numérico
                if pd.api.types.is_numeric_dtype(prepared_df[val_col]):
                    # Agrupar dados
                    grouped = prepared_df.groupby([cat1, cat2])[val_col].sum().unstack().fillna(0)
                    
                    # Determinar layout da grade
                    n_groups = len(grouped)
                    if n_groups == 0:
                        logging.warning("[DEBUG] Não há grupos para múltiplos gráficos de pizza")
                        return None
                    
                    cols = min(3, n_groups)  # Máximo 3 colunas
                    rows = (n_groups + cols - 1) // cols  # Arredondar para cima
                    
                    # Criar subplots
                    fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows))
                    if rows == 1 and cols == 1:
                        axes = np.array([axes])  # Garantir que axes seja um array
                    axes = axes.flatten()
                    
                    # Plotar cada pizza
                    for i, (group_name, group_data) in enumerate(grouped.iterrows()):
                        if i < len(axes):
                            # Remover valores zero
                            data = group_data[group_data > 0]
                            
                            if not data.empty:
                                # Calcular percentuais
                                total = data.sum()
                                
                                # Criar rótulos com valores e percentuais
                                labels = [f'{idx} ({val:.2f}, {val/total:.1%})' for idx, val in data.items()]
                                
                                # Plotar pizza
                                axes[i].pie(data, labels=labels, autopct='%1.1f%%', 
                                           startangle=90, colors=colors[:len(data)])
                                axes[i].set_title(f"{group_name}")
                                axes[i].axis('equal')
                    
                    # Esconder eixos não utilizados
                    for j in range(i + 1, len(axes)):
                        axes[j].axis('off')
                    
                    plt.suptitle(title or f"Distribuição de {val_col} por {cat2} para cada {cat1}", fontsize=16)
                    plt.tight_layout()
                    plt.subplots_adjust(top=0.9)
                else:
                    logging.warning(f"[DEBUG] Coluna {val_col} não é numérica para múltiplos gráficos de pizza")
                    # Fallback para barras agrupadas
                    return generate_graph(df, 'bar_grouped', title, user_query)
            else:
                logging.warning("[DEBUG] Dados insuficientes para múltiplos gráficos de pizza")
                # Fallback para pizza simples
                return generate_graph(df, 'pie', title, user_query)
        
        else:
            # Tipo de gráfico não reconhecido, usar barras verticais como padrão
            logging.warning(f"[DEBUG] Tipo de gráfico '{graph_type}' não reconhecido. Usando gráfico de barras verticais como padrão.")
            return generate_graph(df, 'bar_vertical', title, user_query)
        
        # Salvar o gráfico em um buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        # Converter para imagem PIL
        img = Image.open(buf)
        logging.info(f"[DEBUG] Gráfico gerado com sucesso, tamanho: {img.size}")
        return img
    
    except Exception as e:
        logging.error(f"[ERRO] Falha ao gerar gráfico: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        
        # Tentar fallback para barras verticais em caso de erro
        try:
            logging.info("[DEBUG] Tentando fallback para gráfico de barras verticais")
            return generate_graph(df, 'bar_vertical', title, user_query)
        except:
            return None