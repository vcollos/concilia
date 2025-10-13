# Funcionalidades principais

## Aplicativo de conciliação (`app.py`)

- **Upload e leitura inteligente**  
  - Aceita CSV/TXT exportados pelo Odontotech.  
  - Ignora automaticamente as três linhas de cabeçalho fixo do relatório e tenta múltiplas codificações/sepadores (`read_odontotech_csv`).  
  - Mostra alertas quando bibliotecas opcionais (`reportlab`, `xlsxwriter`) não estão disponíveis.

- **Limpeza e normalização**  
  - Canonicaliza nomes das colunas, remove linhas de controle iniciadas por `*`, normaliza datas (`Emissão`, `Vencto`, `Pagto`) e converte valores monetários para `float` (`clean_odontotech_df`).  
  - Mantém estatísticas de limpeza (linhas removidas, total de registros finais, valores parseados).

- **Resumo global da carga**  
  - Exibe métricas consolidadas (linhas originais/finais, total de valor vigente) sempre respeitando o filtro de período ativo (`apply_date_filter`).

- **Filtros interativos**  
  - Filtro temporal por data de pagamento (`Pagto`) com granularidades Dia, Semana ISO, Mês e intervalo personalizado, persistindo a seleção na `session_state`.  
  - Filtro de bancos (`_render_bank_filter_controls`) que detecta automaticamente a coluna mais adequada para identificar instituição financeira.

- **Visualização analítica (aba “Dados limpos”)**  
  - Dataframe formatado com datas em `dd/mm/yyyy`, totals analíticos e download direto do CSV limpo.  
  - Exportação para PDF (se `reportlab` disponível) com resumo, agrupamentos padrão e tabela principal.  
  - Exportação Excel com múltiplas abas (se `xlsxwriter` disponível), incluindo formatação monetária e agrupamentos por data, classe e banco.

- **Agrupamentos dinâmicos (aba “Montar Relatórios”)**  
  - Seleção livre de colunas para agrupar, filtros adicionais por valores específicos e ordenação multi-nível.  
  - Exibição da tabela agregada já formatada e download em CSV.  
  - Geração de conciliação contábil analítica e sintética em CSV (colunas `Débito`, `Crédito`, `Histórico`, `Data`, `Valor`, `Complemento`).  
  - PDF opcional com resumo do agrupamento escolhido e detalhamento por grupo (quando `reportlab` está disponível).

- **Comparação com extratos bancários (aba “Comparar com OFX”)**  
  - Upload de múltiplos arquivos OFX, consolidação em um único dataframe (`_load_ofx_files`).  
  - Casamento entre CSV limpo e OFX por data e valor, com controle de duplicidades via `cumcount` (`_match_transactions`).  
  - Métricas de quantidades e valores para lançamentos casados, exclusivos do CSV ou exclusivos do OFX.  
  - Visualização e download das três listas (casamentos, somente CSV, somente OFX), mantendo colunas relevantes (classe, histórico, identificadores bancários).

## Biblioteca de parsing Odontotech (`odontotech.py`)

- Mapeamento extensivo de variações de colunas para nomes canônicos (`CANONICAL_COLUMNS`).  
- Conversão de valores monetários brasileiros (`1.234,56`) para `float` e parse de datas com `dayfirst`.  
- Funções de apoio para agrupamentos (`group_totals`) e para identificar qual coluna representa banco/conta (`detect_banco_column`), reutilizadas em todo o app.

## Utilitário de OFX (`ofx_utils.py`)

- Lê arquivos/ofx de diferentes origens (objetos do Streamlit, caminho, bytes).  
- Faz fallback para várias codificações ao decodificar texto.  
- Parser manual dos blocos `<STMTTRN>`, extraindo data, valor, tipo, memo, identificadores.  
- Normaliza datas e valores, entregando um `DataFrame` ordenado e pronto para conciliação.

## Visualizador genérico (`main.py`)

- Detecta automaticamente o tipo de arquivo (OFX, relatórios de contas a pagar/receber, “francesinha” ou CSV genérico).  
- Possui leitores específicos para cada formato textual, removendo cabeçalhos e rodapés irrelevantes e tratando valores monetários/datas.  
- Aplica filtros dinâmicos por tipo de coluna (datas, numéricos, categóricos) e gera arquivo CSV filtrado para download.  
- Exibe totais monetários por coluna relevante conforme o tipo do arquivo.  
- Lista arquivos de exemplo a partir da pasta `arquivos/`, facilitando demonstrações rápidas.

## Fluxo completo em alto nível

1. **Entrada de dados** → Upload (Streamlit) ou seleção de amostras locais.  
2. **Parsing/Limpeza** → Funções em `odontotech.py` (CSV) ou em `main.py`/`ofx_utils.py` (demais formatos).  
3. **Normalização** → Conversão de datas e valores, padronização de cabeçalhos.  
4. **Visualização e filtros** → Controles de data/banco/agrupamento + tabelas interativas.  
5. **Exportação** → CSV limpo, agrupamentos, conciliação contábil, PDF e Excel.  
6. **Conciliação** → Matching CSV × OFX com métricas e relatórios dedicados.

