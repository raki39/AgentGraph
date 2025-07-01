"""
Nó para geração de gráficos
"""
import io
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from PIL import Image
from typing import Dict, Any, Optional

from utils.object_manager import get_object_manager

async def graph_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó para geração de gráficos baseado no tipo selecionado
    
    Args:
        state: Estado atual do agente
        
    Returns:
        Estado atualizado com gráfico gerado
    """
    try:
        logging.info("[GRAPH_GENERATION] Iniciando geração de gráfico")
        
        # Verifica se há tipo de gráfico selecionado
        graph_type = state.get("graph_type")
        if not graph_type:
            logging.info("[GRAPH_GENERATION] Nenhum tipo de gráfico selecionado, pulando geração")
            return state
        
        # Verifica se há erro anterior
        if state.get("graph_error"):
            logging.info("[GRAPH_GENERATION] Erro anterior detectado, pulando geração")
            return state
        
        # Recupera dados do gráfico
        graph_data = state.get("graph_data", {})
        data_id = graph_data.get("data_id")
        
        if not data_id:
            error_msg = "ID dos dados do gráfico não encontrado"
            logging.error(f"[GRAPH_GENERATION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        # Recupera DataFrame dos dados
        obj_manager = get_object_manager()
        df = obj_manager.get_object(data_id)
        
        if df is None or df.empty:
            error_msg = "Dados do gráfico não encontrados ou vazios"
            logging.error(f"[GRAPH_GENERATION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        # Gera título do gráfico baseado na pergunta do usuário
        user_query = state.get("user_input", "")
        title = f"Visualização: {user_query[:50]}..." if len(user_query) > 50 else f"Visualização: {user_query}"
        
        # Gera o gráfico
        graph_image = await generate_graph(df, graph_type, title, user_query)
        
        if graph_image is None:
            error_msg = f"Falha ao gerar gráfico do tipo {graph_type}"
            logging.error(f"[GRAPH_GENERATION] {error_msg}")
            state.update({
                "graph_error": error_msg,
                "graph_generated": False
            })
            return state
        
        # Armazena imagem do gráfico no ObjectManager
        graph_image_id = obj_manager.store_object(graph_image, "graph_image")
        
        # Atualiza estado
        state.update({
            "graph_image_id": graph_image_id,
            "graph_generated": True,
            "graph_error": None
        })
        
        logging.info(f"[GRAPH_GENERATION] Gráfico gerado com sucesso: {graph_type}")
        
    except Exception as e:
        error_msg = f"Erro na geração de gráfico: {e}"
        logging.error(f"[GRAPH_GENERATION] {error_msg}")
        state.update({
            "graph_error": error_msg,
            "graph_generated": False
        })
    
    return state

async def generate_graph(df: pd.DataFrame, graph_type: str, title: str = None, user_query: str = None) -> Optional[Image.Image]:
    """
    Gera um gráfico com base no DataFrame e tipo especificado
    
    Args:
        df: DataFrame com os dados
        graph_type: Tipo de gráfico a ser gerado
        title: Título do gráfico
        user_query: Pergunta original do usuário
        
    Returns:
        Imagem PIL do gráfico ou None se falhar
    """
    logging.info(f"[GRAPH_GENERATION] Gerando gráfico tipo {graph_type}. DataFrame: {len(df)} linhas")
    
    if df.empty:
        logging.warning("[GRAPH_GENERATION] DataFrame vazio")
        return None
    
    try:
        # Preparar dados para o gráfico
        prepared_df = prepare_data_for_graph(df, graph_type, user_query)
        if prepared_df.empty:
            logging.warning("[GRAPH_GENERATION] DataFrame preparado está vazio")
            return None
        
        # Configurações gerais
        plt.style.use('default')
        colors = plt.cm.tab10.colors
        
        # Gerar gráfico baseado no tipo
        if graph_type == 'line_simple':
            return await generate_line_simple(prepared_df, title, colors)
        elif graph_type == 'multiline':
            return await generate_multiline(prepared_df, title, colors)
        elif graph_type == 'area':
            return await generate_area(prepared_df, title, colors)
        elif graph_type == 'bar_vertical':
            return await generate_bar_vertical(prepared_df, title, colors)
        elif graph_type == 'bar_horizontal':
            return await generate_bar_horizontal(prepared_df, title, colors)
        elif graph_type == 'bar_grouped':
            return await generate_bar_grouped(prepared_df, title, colors)
        elif graph_type == 'bar_stacked':
            return await generate_bar_stacked(prepared_df, title, colors)
        elif graph_type == 'pie':
            return await generate_pie(prepared_df, title, colors)
        elif graph_type == 'donut':
            return await generate_donut(prepared_df, title, colors)
        elif graph_type == 'pie_multiple':
            return await generate_pie_multiple(prepared_df, title, colors)
        else:
            logging.warning(f"[GRAPH_GENERATION] Tipo '{graph_type}' não reconhecido, usando bar_vertical")
            return await generate_bar_vertical(prepared_df, title, colors)
            
    except Exception as e:
        logging.error(f"[GRAPH_GENERATION] Erro ao gerar gráfico: {e}")
        return None

def prepare_data_for_graph(df: pd.DataFrame, graph_type: str, user_query: str = None) -> pd.DataFrame:
    """
    Prepara os dados para o gráfico, adaptando-os conforme necessário
    
    Args:
        df: DataFrame original
        graph_type: Tipo de gráfico
        user_query: Pergunta do usuário
        
    Returns:
        DataFrame preparado
    """
    logging.info(f"[GRAPH_GENERATION] Preparando dados para {graph_type}")
    
    if df.empty:
        return df
    
    # Fazer cópia para não modificar original
    prepared_df = df.copy()
    
    # Analisar tipos de colunas
    numeric_cols = prepared_df.select_dtypes(include=['number']).columns.tolist()
    date_cols = [col for col in prepared_df.columns if 
                 pd.api.types.is_datetime64_any_dtype(prepared_df[col]) or 'data' in col.lower()]
    categorical_cols = prepared_df.select_dtypes(include=['object']).columns.tolist()
    
    # Preparação específica por tipo de gráfico
    if graph_type in ['line_simple', 'area']:
        if date_cols and numeric_cols:
            # Usar primeira coluna de data e primeira numérica
            x_col, y_col = date_cols[0], numeric_cols[0]
            prepared_df = prepared_df[[x_col, y_col]].sort_values(by=x_col)
        elif categorical_cols and numeric_cols:
            # Usar primeira categórica e primeira numérica
            x_col, y_col = categorical_cols[0], numeric_cols[0]
            prepared_df = prepared_df[[x_col, y_col]].sort_values(by=y_col)
    
    elif graph_type in ['bar_vertical', 'bar_horizontal']:
        if categorical_cols and numeric_cols:
            x_col, y_col = categorical_cols[0], numeric_cols[0]
            prepared_df = prepared_df[[x_col, y_col]].sort_values(by=y_col, ascending=False)
            # Limitar a 15 categorias para barras verticais
            if graph_type == 'bar_vertical' and len(prepared_df) > 15:
                prepared_df = prepared_df.head(15)
    
    elif graph_type in ['pie', 'donut']:
        if categorical_cols and numeric_cols:
            cat_col, val_col = categorical_cols[0], numeric_cols[0]
            # Agrupar e somar valores
            prepared_df = prepared_df.groupby(cat_col)[val_col].sum().reset_index()
            prepared_df = prepared_df.sort_values(by=val_col, ascending=False)
            # Limitar a 10 categorias
            if len(prepared_df) > 10:
                top_9 = prepared_df.head(9)
                others_sum = prepared_df.iloc[9:][val_col].sum()
                if others_sum > 0:
                    others_row = pd.DataFrame({cat_col: ['Outros'], val_col: [others_sum]})
                    prepared_df = pd.concat([top_9, others_row], ignore_index=True)
                else:
                    prepared_df = top_9
    
    logging.info(f"[GRAPH_GENERATION] Dados preparados: {len(prepared_df)} linhas")
    return prepared_df

def save_plot_to_image() -> Image.Image:
    """
    Salva o plot atual do matplotlib como imagem PIL

    Returns:
        Imagem PIL
    """
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img = Image.open(buf)
    plt.close()  # Importante: fechar o plot para liberar memória
    return img

# ==================== FUNÇÕES DE GERAÇÃO ESPECÍFICAS ====================

async def generate_line_simple(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de linha simples"""
    if len(df.columns) < 2:
        return None

    x_col, y_col = df.columns[0], df.columns[1]
    is_date = pd.api.types.is_datetime64_any_dtype(df[x_col])

    plt.figure(figsize=(12, 6))

    if is_date:
        plt.plot(df[x_col], df[y_col], marker='o', linewidth=2, color=colors[0])
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
    else:
        plt.plot(range(len(df)), df[y_col], marker='o', linewidth=2, color=colors[0])
        plt.xticks(range(len(df)), df[x_col], rotation=45, ha='right')

    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(title or f"{y_col} por {x_col}")
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    return save_plot_to_image()

async def generate_multiline(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de múltiplas linhas"""
    if len(df.columns) < 2:
        return None

    x_col = df.columns[0]
    y_cols = [col for col in df.columns[1:] if pd.api.types.is_numeric_dtype(df[col])]

    if not y_cols:
        return await generate_line_simple(df, title, colors)

    is_date = pd.api.types.is_datetime64_any_dtype(df[x_col])

    plt.figure(figsize=(12, 6))

    for i, y_col in enumerate(y_cols):
        if is_date:
            plt.plot(df[x_col], df[y_col], marker='o', linewidth=2,
                    label=y_col, color=colors[i % len(colors)])
        else:
            plt.plot(range(len(df)), df[y_col], marker='o', linewidth=2,
                    label=y_col, color=colors[i % len(colors)])

    if is_date:
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
    else:
        plt.xticks(range(len(df)), df[x_col], rotation=45, ha='right')

    plt.xlabel(x_col)
    plt.ylabel("Valores")
    plt.title(title or f"Comparação por {x_col}")
    plt.legend(title="Séries", loc='best')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    return save_plot_to_image()

async def generate_area(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de área"""
    if len(df.columns) < 2:
        return None

    x_col, y_col = df.columns[0], df.columns[1]
    is_date = pd.api.types.is_datetime64_any_dtype(df[x_col])

    plt.figure(figsize=(12, 6))

    if is_date:
        plt.fill_between(df[x_col], df[y_col], alpha=0.5, color=colors[0])
        plt.plot(df[x_col], df[y_col], color=colors[0], linewidth=2)
        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
    else:
        plt.fill_between(range(len(df)), df[y_col], alpha=0.5, color=colors[0])
        plt.plot(range(len(df)), df[y_col], color=colors[0], linewidth=2)
        plt.xticks(range(len(df)), df[x_col], rotation=45, ha='right')

    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(title or f"{y_col} por {x_col}")
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    return save_plot_to_image()

async def generate_bar_vertical(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de barras verticais"""
    if len(df.columns) < 2:
        return None

    x_col, y_col = df.columns[0], df.columns[1]

    plt.figure(figsize=(12, 8))
    bars = plt.bar(range(len(df)), df[y_col], color=colors[0])

    # Adicionar valores nas barras
    for i, bar in enumerate(bars):
        height = bar.get_height()
        if isinstance(height, (int, float)):
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.02 * max(df[y_col]),
                    f'{height:.2f}', ha='center', fontsize=9)

    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(title or f"{y_col} por {x_col}")
    plt.xticks(range(len(df)), df[x_col], rotation=45, ha='right')
    plt.grid(True, linestyle='--', alpha=0.7, axis='y')
    plt.tight_layout()

    return save_plot_to_image()

async def generate_bar_horizontal(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de barras horizontais"""
    if len(df.columns) < 2:
        return None

    x_col, y_col = df.columns[0], df.columns[1]

    plt.figure(figsize=(12, max(6, len(df) * 0.4)))
    bars = plt.barh(range(len(df)), df[y_col], color=colors[0])

    # Adicionar valores nas barras
    for i, bar in enumerate(bars):
        width = bar.get_width()
        if isinstance(width, (int, float)):
            plt.text(width + 0.02 * max(df[y_col]), bar.get_y() + bar.get_height()/2.,
                    f'{width:.2f}', va='center', fontsize=9)

    plt.xlabel(y_col)
    plt.ylabel(x_col)
    plt.title(title or f"{y_col} por {x_col}")
    plt.yticks(range(len(df)), df[x_col])
    plt.grid(True, linestyle='--', alpha=0.7, axis='x')
    plt.tight_layout()

    return save_plot_to_image()

async def generate_bar_grouped(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de barras agrupadas"""
    if len(df.columns) < 3:
        return await generate_bar_vertical(df, title, colors)

    x_col = df.columns[0]
    y_cols = [col for col in df.columns[1:] if pd.api.types.is_numeric_dtype(df[col])]

    if not y_cols:
        return await generate_bar_vertical(df, title, colors)

    x = np.arange(len(df))
    width = 0.8 / len(y_cols)

    fig, ax = plt.subplots(figsize=(12, 8))

    for i, col in enumerate(y_cols):
        offset = width * i - width * (len(y_cols) - 1) / 2
        bars = ax.bar(x + offset, df[col], width, label=col, color=colors[i % len(colors)])

        # Adicionar valores nas barras
        for bar in bars:
            height = bar.get_height()
            if isinstance(height, (int, float)) and not np.isnan(height):
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.02 * df[y_cols].max().max(),
                        f'{height:.2f}', ha='center', fontsize=8)

    ax.set_xlabel(x_col)
    ax.set_ylabel('Valores')
    ax.set_title(title or f"Comparação por {x_col}")
    ax.set_xticks(x)
    ax.set_xticklabels(df[x_col], rotation=45, ha='right')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.7, axis='y')
    plt.tight_layout()

    return save_plot_to_image()

async def generate_bar_stacked(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de barras empilhadas"""
    if len(df.columns) < 3:
        return await generate_bar_vertical(df, title, colors)

    x_col = df.columns[0]
    y_cols = [col for col in df.columns[1:] if pd.api.types.is_numeric_dtype(df[col])]

    if not y_cols:
        return await generate_bar_vertical(df, title, colors)

    fig, ax = plt.subplots(figsize=(12, 8))
    bottom = np.zeros(len(df))

    for i, col in enumerate(y_cols):
        bars = ax.bar(range(len(df)), df[col], bottom=bottom, label=col, color=colors[i % len(colors)])

        # Adicionar valores nas barras
        for j, bar in enumerate(bars):
            height = bar.get_height()
            if isinstance(height, (int, float)) and height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bottom[j] + height/2,
                        f'{height:.2f}', ha='center', va='center', fontsize=8, color='white')

        bottom += df[col].fillna(0)

    ax.set_xlabel(x_col)
    ax.set_ylabel('Valores')
    ax.set_title(title or f"Distribuição por {x_col}")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df[x_col], rotation=45, ha='right')
    ax.legend()
    plt.tight_layout()

    return save_plot_to_image()

async def generate_pie(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de pizza"""
    if len(df.columns) < 2:
        return None

    label_col, value_col = df.columns[0], df.columns[1]

    # Verificar se os valores são numéricos
    if not pd.api.types.is_numeric_dtype(df[value_col]):
        return await generate_bar_vertical(df, title, colors)

    # Remover valores negativos ou zero
    df_clean = df[df[value_col] > 0]
    if df_clean.empty:
        return None

    plt.figure(figsize=(10, 10))

    # Calcular percentuais para os rótulos
    total = df_clean[value_col].sum()
    labels = [f'{label} ({val:.2f}, {val/total:.1%})' for label, val in zip(df_clean[label_col], df_clean[value_col])]

    plt.pie(df_clean[value_col], labels=labels, autopct='%1.1f%%',
            startangle=90, shadow=False, colors=colors[:len(df_clean)])

    plt.axis('equal')
    plt.title(title or f"Distribuição de {value_col} por {label_col}")
    plt.tight_layout()

    return save_plot_to_image()

async def generate_donut(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera gráfico de donut"""
    if len(df.columns) < 2:
        return None

    label_col, value_col = df.columns[0], df.columns[1]

    # Verificar se os valores são numéricos
    if not pd.api.types.is_numeric_dtype(df[value_col]):
        return await generate_bar_vertical(df, title, colors)

    # Remover valores negativos ou zero
    df_clean = df[df[value_col] > 0]
    if df_clean.empty:
        return None

    plt.figure(figsize=(10, 10))

    # Calcular percentuais para os rótulos
    total = df_clean[value_col].sum()
    labels = [f'{label} ({val:.2f}, {val/total:.1%})' for label, val in zip(df_clean[label_col], df_clean[value_col])]

    # Criar gráfico de donut (pizza com círculo central)
    plt.pie(df_clean[value_col], labels=labels, autopct='%1.1f%%',
            startangle=90, shadow=False, colors=colors[:len(df_clean)],
            wedgeprops=dict(width=0.5))  # Largura do anel

    plt.axis('equal')
    plt.title(title or f"Distribuição de {value_col} por {label_col}")
    plt.tight_layout()

    return save_plot_to_image()

async def generate_pie_multiple(df: pd.DataFrame, title: str, colors) -> Optional[Image.Image]:
    """Gera múltiplos gráficos de pizza"""
    if len(df.columns) < 3:
        return await generate_pie(df, title, colors)

    cat1, cat2, val_col = df.columns[0], df.columns[1], df.columns[2]

    # Verificar se o valor é numérico
    if not pd.api.types.is_numeric_dtype(df[val_col]):
        return await generate_bar_grouped(df, title, colors)

    # Agrupar dados
    grouped = df.groupby([cat1, cat2])[val_col].sum().unstack().fillna(0)

    # Determinar layout da grade
    n_groups = len(grouped)
    if n_groups == 0:
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

    return save_plot_to_image()
