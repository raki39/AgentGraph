#!/usr/bin/env python3
"""
Gerador de relatórios para testes massivos
"""
import pandas as pd
import logging
import os
from datetime import datetime
from typing import Dict, Any, List
import json

class ReportGenerator:
    """
    Gerador de relatórios em CSV e outros formatos
    """
    
    def __init__(self, output_dir: str = "testes/reports"):
        """
        Inicializa o gerador de relatórios
        
        Args:
            output_dir: Diretório para salvar relatórios
        """
        self.output_dir = output_dir
        self._ensure_output_dir()
    
    def _ensure_output_dir(self):
        """Garante que o diretório de saída existe"""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_csv_report(self, results: Dict[str, Any]) -> str:
        """
        Gera relatório completo em CSV/Excel

        Args:
            results: Resultados dos testes

        Returns:
            Caminho do arquivo Excel gerado
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Corrige caminhos para Windows
            excel_filename = f"relatorio_testes_{timestamp}.xlsx"
            excel_path = os.path.join(self.output_dir, excel_filename)
            excel_path = os.path.normpath(excel_path)  # Normaliza barras

            print(f"📊 Gerando relatório Excel: {excel_path}")

            # Cria Excel com múltiplas abas
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:

                # Aba 1: Resumo por Grupo
                group_summary_df = self._create_group_summary_dataframe(results)
                if not group_summary_df.empty:
                    group_summary_df.to_excel(writer, sheet_name='Resumo_Grupos', index=False)
                    print(f"✅ Aba 'Resumo_Grupos' criada com {len(group_summary_df)} linhas")

                # Aba 2: Resultados Individuais
                individual_df = self._create_individual_results_dataframe(results)
                if not individual_df.empty:
                    individual_df.to_excel(writer, sheet_name='Resultados_Individuais', index=False)
                    print(f"✅ Aba 'Resultados_Individuais' criada com {len(individual_df)} linhas")

                # Aba 3: Resumo Geral
                general_summary_df = self._create_general_summary_dataframe(results)
                if not general_summary_df.empty:
                    general_summary_df.to_excel(writer, sheet_name='Resumo_Geral', index=False)
                    print(f"✅ Aba 'Resumo_Geral' criada com {len(general_summary_df)} linhas")

            # Também gera CSVs separados com separador correto
            csv_dir = os.path.join(self.output_dir, f"csv_{timestamp}")
            os.makedirs(csv_dir, exist_ok=True)

            if not group_summary_df.empty:
                csv_grupos = os.path.join(csv_dir, "resumo_grupos.csv")
                group_summary_df.to_csv(csv_grupos, index=False, encoding='utf-8-sig', sep=';')
                print(f"✅ CSV grupos: {csv_grupos}")

            if not individual_df.empty:
                csv_individual = os.path.join(csv_dir, "resultados_individuais.csv")
                individual_df.to_csv(csv_individual, index=False, encoding='utf-8-sig', sep=';')
                print(f"✅ CSV individual: {csv_individual}")

            if not general_summary_df.empty:
                csv_geral = os.path.join(csv_dir, "resumo_geral.csv")
                general_summary_df.to_csv(csv_geral, index=False, encoding='utf-8-sig', sep=';')
                print(f"✅ CSV geral: {csv_geral}")

            print(f"🎉 Relatório completo gerado: {excel_path}")
            logging.info(f"Relatório gerado: {excel_path}")
            return excel_path

        except Exception as e:
            print(f"❌ Erro ao gerar relatório: {e}")
            logging.error(f"Erro ao gerar relatório CSV: {e}")
            raise
    
    def _create_group_summary_dataframe(self, results: Dict[str, Any]) -> pd.DataFrame:
        """
        Cria DataFrame com resumo por grupo
        
        Args:
            results: Resultados dos testes
            
        Returns:
            DataFrame com resumo dos grupos
        """
        group_results = results.get('group_results', [])
        
        if not group_results:
            return pd.DataFrame()
        
        summary_data = []
        
        for group in group_results:
            config = group.get('group_config', {})
            
            summary_data.append({
                'Grupo_ID': group.get('group_id'),
                'Modelo_SQL': config.get('sql_model_name'),
                'Processing_Agent_Ativo': 'Sim' if config.get('processing_enabled') else 'Não',
                'Modelo_Processing': config.get('processing_model_name', 'N/A'),
                'Total_Testes': group.get('total_tests'),
                'Testes_Sucessos': group.get('successful_tests'),
                'Respostas_Válidas': group.get('valid_responses'),
                'Taxa_Sucesso_%': group.get('success_rate'),
                'Taxa_Validação_%': group.get('validation_rate'),
                'Consistência_Resposta_%': group.get('response_consistency'),
                'Consistência_SQL_%': group.get('sql_consistency'),
                'Tempo_Médio_Execução_s': group.get('avg_execution_time'),
                'Erros_Totais': group.get('error_count', 0)
            })
        
        return pd.DataFrame(summary_data)
    
    def _create_individual_results_dataframe(self, results: Dict[str, Any]) -> pd.DataFrame:
        """
        Cria DataFrame com resultados individuais
        
        Args:
            results: Resultados dos testes
            
        Returns:
            DataFrame com resultados individuais
        """
        individual_results = results.get('individual_results', [])
        
        if not individual_results:
            return pd.DataFrame()
        
        individual_data = []
        
        for result in individual_results:
            validation = result.get('validation', {})
            
            individual_data.append({
                'Grupo_ID': result.get('group_id'),
                'Iteração': result.get('iteration'),
                'Thread_ID': result.get('thread_id'),
                'Timestamp': result.get('timestamp'),
                'Modelo_SQL': result.get('sql_model'),
                'Processing_Agent_Ativo': 'Sim' if result.get('processing_enabled') else 'Não',
                'Modelo_Processing': result.get('processing_model', 'N/A'),
                'Pergunta': result.get('question'),
                'Query_SQL': result.get('sql_query'),
                'Resposta_Final': result.get('response'),
                'Sucesso': 'Sim' if result.get('success') else 'Não',
                'Erro': result.get('error', ''),
                'Tempo_Execução_s': result.get('execution_time'),
                'Validação_Válida': 'Sim' if validation.get('valid') else 'Não',
                'Pontuação_Validação': validation.get('score', 0),
                'Razão_Validação': validation.get('reason', ''),
                'Método_Validação': validation.get('method', '')
            })
        
        return pd.DataFrame(individual_data)
    
    def _create_general_summary_dataframe(self, results: Dict[str, Any]) -> pd.DataFrame:
        """
        Cria DataFrame com resumo geral
        
        Args:
            results: Resultados dos testes
            
        Returns:
            DataFrame com resumo geral
        """
        session_info = results.get('session_info', {})
        summary = results.get('summary', {})
        
        general_data = [
            {'Métrica': 'ID da Sessão', 'Valor': session_info.get('id', '')},
            {'Métrica': 'Pergunta do Teste', 'Valor': session_info.get('question', '')},
            {'Métrica': 'Método de Validação', 'Valor': session_info.get('validation_method', '')},
            {'Métrica': 'Total de Grupos', 'Valor': summary.get('total_groups', 0)},
            {'Métrica': 'Total de Testes', 'Valor': summary.get('total_tests', 0)},
            {'Métrica': 'Total de Sucessos', 'Valor': summary.get('total_successful', 0)},
            {'Métrica': 'Total de Válidos', 'Valor': summary.get('total_valid', 0)},
            {'Métrica': 'Taxa Geral de Sucesso (%)', 'Valor': summary.get('overall_success_rate', 0)},
            {'Métrica': 'Taxa Geral de Validação (%)', 'Valor': summary.get('overall_validation_rate', 0)},
            {'Métrica': 'Consistência Média de Resposta (%)', 'Valor': summary.get('avg_response_consistency', 0)},
            {'Métrica': 'Consistência Média de SQL (%)', 'Valor': summary.get('avg_sql_consistency', 0)},
        ]
        
        # Adiciona informações do melhor grupo
        best_group = summary.get('best_performing_group', {})
        if best_group:
            config = best_group.get('group_config', {})
            general_data.extend([
                {'Métrica': 'Melhor Grupo - ID', 'Valor': best_group.get('group_id', '')},
                {'Métrica': 'Melhor Grupo - Modelo SQL', 'Valor': config.get('sql_model_name', '')},
                {'Métrica': 'Melhor Grupo - Processing Agent', 'Valor': 'Sim' if config.get('processing_enabled') else 'Não'},
                {'Métrica': 'Melhor Grupo - Taxa Validação (%)', 'Valor': best_group.get('validation_rate', 0)},
            ])
        
        # Adiciona informações do grupo mais consistente
        consistent_group = summary.get('most_consistent_group', {})
        if consistent_group:
            config = consistent_group.get('group_config', {})
            general_data.extend([
                {'Métrica': 'Grupo Mais Consistente - ID', 'Valor': consistent_group.get('group_id', '')},
                {'Métrica': 'Grupo Mais Consistente - Modelo SQL', 'Valor': config.get('sql_model_name', '')},
                {'Métrica': 'Grupo Mais Consistente - Consistência (%)', 'Valor': consistent_group.get('response_consistency', 0)},
            ])
        
        return pd.DataFrame(general_data)
    
    def generate_json_report(self, results: Dict[str, Any]) -> str:
        """
        Gera relatório em formato JSON
        
        Args:
            results: Resultados dos testes
            
        Returns:
            Caminho do arquivo JSON gerado
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = os.path.join(self.output_dir, f"relatorio_testes_{timestamp}.json")
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            logging.info(f"Relatório JSON gerado: {json_path}")
            return json_path
            
        except Exception as e:
            logging.error(f"Erro ao gerar relatório JSON: {e}")
            raise
    
    def generate_html_summary(self, results: Dict[str, Any]) -> str:
        """
        Gera resumo em HTML
        
        Args:
            results: Resultados dos testes
            
        Returns:
            Caminho do arquivo HTML gerado
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = os.path.join(self.output_dir, f"resumo_testes_{timestamp}.html")
            
            # Cria DataFrames
            group_df = self._create_group_summary_dataframe(results)
            general_df = self._create_general_summary_dataframe(results)
            
            # Gera HTML
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Relatório de Testes - AgentGraph</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #e7f3ff; padding: 15px; margin: 20px 0; }}
        .metric {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>Relatório de Testes Massivos - AgentGraph</h1>
    <p>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
    
    <div class="summary">
        <h2>Resumo Geral</h2>
        {general_df.to_html(index=False, escape=False)}
    </div>
    
    <h2>Resumo por Grupo</h2>
    {group_df.to_html(index=False, escape=False)}
    
</body>
</html>
"""
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logging.info(f"Resumo HTML gerado: {html_path}")
            return html_path
            
        except Exception as e:
            logging.error(f"Erro ao gerar resumo HTML: {e}")
            raise
    
    def generate_all_reports(self, results: Dict[str, Any]) -> Dict[str, str]:
        """
        Gera todos os tipos de relatório
        
        Args:
            results: Resultados dos testes
            
        Returns:
            Dicionário com caminhos dos arquivos gerados
        """
        report_paths = {}
        
        try:
            report_paths['csv'] = self.generate_csv_report(results)
            report_paths['json'] = self.generate_json_report(results)
            report_paths['html'] = self.generate_html_summary(results)
            
            logging.info(f"Todos os relatórios gerados: {report_paths}")
            return report_paths
            
        except Exception as e:
            logging.error(f"Erro ao gerar relatórios: {e}")
            raise
