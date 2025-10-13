# Referência de funções — `app.py`

## `_process_file` — `app.py:59`
- **Responsabilidade**: ler o arquivo enviado pelo usuário, aplicando `read_odontotech_csv` e `clean_odontotech_df`, e devolver tanto os dados brutos quanto os limpos com estatísticas associadas.
- **Entradas**: objeto retornado pelo `st.file_uploader` (possui `.read()` e metadata).
- **Retorno**: tupla `(raw_df, read_stats, cleaned_df, clean_stats)`.
- **Notas**: função cacheada com `@st.cache_data` para evitar retrabalho ao trocar de abas usando o mesmo arquivo.

## `_fmt_brl` — `app.py:65`
- **Responsabilidade**: formatar um número para string monetária brasileira (`R$ 1.234,56`).
- **Entradas**: número ou string convertível.
- **Retorno**: string formatada ou valor original em caso de erro.
- **Uso**: métricas (`st.metric`) e colunas exibidas/baixadas.

## `_format_total_column` — `app.py:72`
- **Responsabilidade**: aplicar `_fmt_brl` à coluna `total` de um dataframe agregado.
- **Entradas**: `pd.DataFrame`.
- **Retorno**: dataframe com coluna `total` transformada em texto.
- **Uso**: exibição de agrupamentos na aba “Montar Relatórios”.

## `_format_dates_for_display` — `app.py:82`
- **Responsabilidade**: converter colunas datetime para `dd/mm/yyyy`.
- **Entradas**: `pd.DataFrame`.
- **Retorno**: cópia formatada.
- **Uso**: tabelas mostradas no Streamlit e downloads.

## `_show_group_totals` — `app.py:92`
- **Responsabilidade**: exibir resumo com quantidade e total monetário de um agrupamento.
- **Entradas**: dataframe agregado (colunas `qtd` e `total`).
- **Retorno**: nenhum (efeitos visuais via `st.markdown`).

## `_show_analytic_totals` — `app.py:107`
- **Responsabilidade**: apresentar totais analíticos (número de registros e soma do valor) da tabela filtrada.
- **Entradas**: dataframe não agregado.
- **Retorno**: nenhum.

## `_format_df_for_pdf` — `app.py:116`
- **Responsabilidade**: preparar dataframe para exportação PDF (datas formatadas, valores monetários formatados).
- **Entradas**: dataframe.
- **Retorno**: dataframe formatado (strings).

## `_df_to_table_flowable` — `app.py:132`
- **Responsabilidade**: converter dataframe em elementos (Flowables) do ReportLab.
- **Entradas**: dataframe, título da seção, largura de colunas opcional.
- **Retorno**: lista de flowables (Paragraph, Table, Spacer).
- **Dependências**: requer `reportlab`; quando ausente, a função não é chamada.

## `_build_pdf` — `app.py:175`
- **Responsabilidade**: montar o PDF completo (capa, resumo, seções).
- **Entradas**: título, dicionário de resumo (estatísticas), texto do filtro aplicado, lista de seções `(título, dataframe)`.
- **Retorno**: bytes do PDF.
- **Notas**: centraliza a lógica para os dois botões de download (dados limpos e agrupamento livre).

## `_normalize_text` — `app.py:272`
- **Responsabilidade**: remover acentos e normalizar strings (maiúsculas) antes de consultar `_ACCOUNTING_RULES`.
- **Entradas**: valor textual.
- **Retorno**: string limpa.

## `_accounting_entry_from_values` — `app.py:279`
- **Responsabilidade**: construir um dicionário com campos contábeis a partir de uma linha do CSV limpo.
- **Entradas**: complemento/classe, valor monetário, data para o lançamento.
- **Retorno**: dict com chaves `Débito`, `Crédito`, `Histórico`, `Data`, `Valor`, `Complemento`.
- **Notas**: formata o valor como absoluto e data no padrão brasileiro.

## `_build_accounting_export` — `app.py:316`
- **Responsabilidade**: gerar dataframe analítico para exportação contábil, linha a linha.
- **Entradas**: dataframe filtrado (espera colunas `Pagto`, `Valor`, `CLASSE`).
- **Retorno**: dataframe com colunas contábeis.
- **Notas**: ignora quando pré-condições não são atendidas (colunas ausentes ou dados vazios).

## `_build_grouped_accounting_export` — `app.py:341`
- **Responsabilidade**: gerar dataframe contábil a partir de agregados (`group_totals`).
- **Entradas**: dataframe agregado e lista de colunas usadas no agrupamento.
- **Retorno**: dataframe contábil agrupado.
- **Regras**: ignora linhas cuja classe contém “PJ”; tenta inferir uma data para o lançamento.

### Função interna `_pick_date`
- Utilizada dentro de `_build_grouped_accounting_export` para selecionar a melhor coluna que possa ser interpretada como data.

## `_select_full_columns` — `app.py:377`
- **Responsabilidade**: retornar vista da tabela com colunas-chave na ordem desejada (Pagto, Histórico, Valor, CLASSE, Forma de Pagamento, Nome Banco, ID Conta Corrente).
- **Entradas**: dataframe.
- **Retorno**: dataframe filtrado/reordenado.
- **Notas**: lida com variantes de “Histórico”.

## `_summary_tables` — `app.py:404`
- **Responsabilidade**: montar os agrupamentos padrão (por Pagto, CLASSE, Nome Banco) para uso em PDFs e abas.
- **Entradas**: dataframe.
- **Retorno**: lista de tuplas `(título, dataframe)`.

## `_detail_sections_from_summary` — `app.py:420`
- **Responsabilidade**: criar seções detalhadas por grupo com base no resumo agregado.
- **Entradas**: dataframe original, dataframe agregado, lista de colunas de agrupamento.
- **Retorno**: lista de tuplas `(título, dataframe)` filtradas.

## `_date_columns` — `app.py:463`
- **Responsabilidade**: fornecer a lista de colunas de data relevantes para filtros (hoje retorna apenas `Pagto` se existir).
- **Uso atual**: função disponível para extensões futuras; o fluxo atual utiliza diretamente `Pagto`.

## `render_date_filter_controls` — `app.py:468`
- **Responsabilidade**: renderizar os controles de filtro temporal e salvar as escolhas na `session_state`.
- **Entradas**: dataframe atual e namespace (`ns`) para compor as keys do estado.
- **Retorno**: nenhum (manipula `st.session_state` e elementos visuais).

## `apply_date_filter` — `app.py:531`
- **Responsabilidade**: aplicar o filtro de data baseado no estado salvo por `render_date_filter_controls`.
- **Entradas**: dataframe atual.
- **Retorno**: tupla `(dataframe_filtrado, descrição_do_filtro)`.
- **Regras**: trata individualmente cada granularidade e garante intervalo inclusivo.

## `_load_ofx_files` — `app.py:563`
- **Responsabilidade**: ler múltiplos uploads OFX, consolidar em um dataframe e registrar mensagens de alerta/erro.
- **Entradas**: lista de uploads (`UploadedFile`).
- **Retorno**: tupla `(dataframe, mensagens)`.

## `_match_transactions` — `app.py:591`
- **Responsabilidade**: conciliar lançamentos CSV × OFX com base em data e valor arredondado.
- **Entradas**: dataframe limpo (`df_clean`), dataframe OFX consolidado.
- **Retorno**: três dataframes (casamentos, somente CSV, somente OFX).
- **Regras**: usa `cumcount` para diferenciar duplicidades; remove a coluna `_merge` após o merge.

## `_select_existing` — `app.py:635`
- **Responsabilidade**: filtrar lista de nomes de coluna mantendo apenas as existentes em um dataframe.
- **Uso**: definir colunas exibidas em cada tabela de comparação CSV × OFX.

## `_sum_column` — `app.py:639`
- **Responsabilidade**: somar com segurança uma coluna numérica (tratando `NaN` como zero).
- **Uso**: métricas do cabeçalho na aba de comparação.

## `_render_bank_filter_controls` — `app.py:645`
- **Responsabilidade**: exibir controles de filtro por banco e aplicar o filtro selecionado.
- **Entradas**: dataframe atual e namespace (`ns`).
- **Retorno**: tupla `(dataframe_filtrado, descrição_do_filtro)`.
- **Regras**: prioriza a coluna sugerida por `detect_banco_column` e alerta quando não há correspondências.

