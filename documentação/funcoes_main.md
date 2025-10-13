# Referência de funções — `main.py`

## `_decode_bytes` — `main.py:33`
- **Responsabilidade**: tentar múltiplas codificações para converter bytes em string.
- **Entradas**: bytes.
- **Retorno**: string decodificada (fallback ignora erros).
- **Uso**: leitura de arquivos antes de detectar o tipo.

## `_convert_brl` — `main.py:42`
- **Responsabilidade**: converter série de strings monetárias brasileiras em valores numéricos.
- **Entradas**: `pd.Series`.
- **Retorno**: série numérica (`float`) com `NaN` para valores inválidos.
- **Notas**: remove espaços, não quebra quando a série já é numérica.

## `_strip_strings` — `main.py:53`
- **Responsabilidade**: eliminar espaços excessivos de colunas de texto específicas.
- **Entradas**: dataframe e conjunto de colunas-alvo.
- **Retorno**: dataframe com colunas alteradas.

## `_parse_dates` — `main.py:60`
- **Responsabilidade**: converter colunas informadas para datetime (`dayfirst=True`).
- **Entradas**: dataframe, iterável de nomes de coluna.
- **Retorno**: dataframe com datas parseadas.

## `_strip_object_columns` — `main.py:67`
- **Responsabilidade**: aplicar `str.strip()` em todas as colunas do tipo objeto.
- **Uso**: limpeza genérica antes de tratamentos específicos.

## `detect_kind` — `main.py:73`
- **Responsabilidade**: classificar o arquivo (ofx, contas_pagar, contas_receber, francesinha ou csv genérico).
- **Entradas**: nome do arquivo e texto inicial.
- **Retorno**: string com o tipo detectado.
- **Regras**: prioriza extensão `.ofx` e padrões textuais nos cabeçalhos.

## `read_francesinha_from_text` — `main.py:89`
- **Responsabilidade**: parsear arquivos “francesinha” (sacados e boletos).
- **Entradas**: texto completo do arquivo CSV-like.
- **Retorno**: dataframe limpo (strings stripadas, datas e valores convertidos).
- **Regras**: ignora linhas de resumo, cabeçalhos repetidos, totais e prefixos específicos (`Ordenado por`, `Relatório`, etc.).

## `read_contas_pagar_from_text` — `main.py:150`
- **Responsabilidade**: processar relatórios de contas pagas exportados em texto delimitado por `;`.
- **Entradas**: texto.
- **Retorno**: dataframe com colunas padronizadas, datas e valores convertidos.
- **Notas**: evita cabeçalhos duplicados e remove linhas vazias.

## `read_contas_receber_from_text` — `main.py:205`
- **Responsabilidade**: processar relatórios de contas a receber (recebidos).
- **Entradas**: texto.
- **Retorno**: dataframe limpo.
- **Regras**: ignora blocos com intervalos de datas, subtotais e cabeçalhos duplicados; converte colunas monetárias e de data.

## `load_dataset` — `main.py:262`
- **Responsabilidade**: função genérica que decodifica o arquivo, detecta o tipo e delega ao parser correto.
- **Entradas**: nome do arquivo e bytes.
- **Retorno**: `DataPreview` (nome, tipo, dataframe).
- **Notas**: fallback para `pd.read_csv` com `sep=None` para formatos desconhecidos.

## `cached_load_from_bytes` — `main.py:279`
- **Responsabilidade**: versão cacheada de `load_dataset`.
- **Uso**: acelerar recargas dentro do Streamlit.

## `_fmt_brl` — `main.py:283`
- **Responsabilidade**: formatar número como moeda brasileira.
- **Uso**: métricas de totais monetários no visualizador.

## `_monetary_totals` — `main.py:290`
- **Responsabilidade**: construir lista de totais monetários relevantes por tipo de dataset (configuração `SUMMARY_COLUMNS`).
- **Entradas**: tipo do dataset, dataframe.
- **Retorno**: lista de tuplas `(nome_coluna, total_float)`.

## `_suggest_download_name` — `main.py:298`
- **Responsabilidade**: gerar nome padrão para o CSV de download (ex.: `arquivo_tipo.csv`).

## `_sanitize_key_fragment` — `main.py:303`
- **Responsabilidade**: limpar strings para uso como chave de estado no Streamlit (remoção de caracteres especiais).

## `_extract_first_timestamp` — `main.py:307`
- **Responsabilidade**: converter diferentes inputs (séries, índices, datas únicas) em um único `Timestamp`.
- **Uso**: suporte aos filtros de datas no mecanismo dinâmico.

## `_apply_dynamic_filters` — `main.py:318`
- **Responsabilidade**: gerar UI dinâmica de filtros (datas, números, categorias) baseada no conteúdo do dataframe.
- **Entradas**: dataframe original, tipo (kind) e prefixo para as chaves do estado.
- **Retorno**: dataframe filtrado e descrição textual dos filtros aplicados.
- **Regras**:
  - Colunas datetime recebem controle `st.date_input`.  
  - Colunas numéricas usam `st.slider`.  
  - Colunas categóricas com até 200 valores únicos oferecem `st.multiselect`.  
  - Sempre existe a opção “incluir vazios”.

## `render_preview` — `main.py:481`
- **Responsabilidade**: renderizar a aba com dados, filtros, métricas e botão de download para um dataset específico.
- **Entradas**: rótulo de exibição, `DataPreview`, número de linhas desejado na tabela.
- **Notas**: tratamento extra para francesinhas (totais por previsão de crédito, remoção de coluna `Vlr. Baixado`).

## `_list_sample_files` — `main.py:558`
- **Responsabilidade**: listar arquivos de exemplo (`*.csv`/`*.ofx`) em `arquivos/`.
- **Entradas**: `Path` base.
- **Retorno**: lista ordenada de caminhos.

## `main` — `main.py:568`
- **Responsabilidade**: função principal do aplicativo Streamlit auxiliar.
- **Fluxo**:
  1. Configura a página e a barra lateral (upload, seleção de exemplos, controle de altura da tabela).
  2. Carrega e processa todos os arquivos selecionados utilizando `cached_load_from_bytes`.
  3. Para cada dataset válido, renderiza uma aba via `render_preview`; erros são mostrados na interface.
- **Saída**: efeitos na UI do Streamlit.

