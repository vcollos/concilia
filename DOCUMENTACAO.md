# Documentação do Projeto Concilia

## Visão geral
O repositório oferece um conjunto de ferramentas para conciliação financeira de dados exportados do Odontotech. O fluxo principal, disponível em `app.py`, é um aplicativo Streamlit que:
- recebe o CSV bruto do Odontotech (arquivos `.csv` ou `.txt`),
- executa limpeza e normalização das colunas,
- aplica filtros por período e por banco,
- gera visões analítica e sintética com agrupamentos dinâmicos,
- exporta relatórios em CSV, Excel e PDF,
- produz arquivos auxiliares de conciliação contábil,
- compara o extrato limpo com lançamentos bancários no formato OFX.

Há ainda um segundo aplicativo (`main.py`) que funciona como um visualizador genérico para múltiplos tipos de arquivos (OFX, relatórios de contas a pagar/receber e “francesinhas”), útil para inspeção rápida das planilhas.

Os arquivos de exemplo na pasta `arquivos/` podem ser usados para testar tanto o app principal quanto o visualizador auxiliar.

## Estrutura dos módulos

### `app.py`
Interface Streamlit focada na conciliação Odontotech. Principais responsabilidades:
- configuração inicial do app e injeção de CSS para impressões;
- leitura e limpeza dos dados via `read_odontotech_csv` e `clean_odontotech_df`;
- gestão do estado dos filtros por data (`render_date_filter_controls` e `apply_date_filter`);
- montagem das seções de resumo, análise, exportação (CSV/Excel/PDF) e agrupamentos livres;
- geração dos arquivos de conciliação contábil, analítica e sintética;
- comparação com um ou mais extratos bancários OFX utilizando `ofx_utils.read_ofx_transactions`;
- criação das métricas de resumo e das seções de resultados.

### `odontotech.py`
Biblioteca de limpeza e transformação do CSV do Odontotech:
- padroniza o cabeçalho através de `canonicalize_columns`, normalizando grafias (acentos, abreviações, etc.);
- ignora registros iniciados com `*` (`_drop_star_rows`);
- faz o parse das colunas de data `Emissão`, `Vencto` e `Pagto`;
- converte valores monetários brasileiros para `float` (`_to_brazil_float`);
- expõe utilitários para agrupamentos (`group_totals`) e detecção de coluna de banco (`detect_banco_column`).

### `ofx_utils.py`
Parser enxuto para arquivos OFX:
- lê diferentes fontes de bytes (`_read_bytes`);
- tenta múltiplas codificações (`_decode_text`);
- identifica blocos `<STMTTRN>` e extrai campos relevantes (data, valor, tipo, identificadores, memo);
- normaliza datas e valores e retorna um `DataFrame` ordenado.

### `main.py`
Visualizador Streamlit que aceita múltiplos formatos:
- detecta o tipo de arquivo pelo conteúdo (`detect_kind`);
- aplica limpeza específica para “francesinha”, relatórios de contas a pagar/receber ou OFX;
- oferece filtros dinâmicos por tipo de dado (`_apply_dynamic_filters`);
- exibe métricas por coluna e exporta o resultado filtrado;
- permite carregar arquivos de exemplo da pasta `arquivos/`.

## Fluxo do aplicativo principal (`app.py`)

1. **Upload**: o usuário seleciona um CSV do Odontotech. Os três primeiros cabeçalhos são ignorados (`read_odontotech_csv`), os dados são limpos (`clean_odontotech_df`) e o resultado fica em cache (`@st.cache_data`).
2. **Filtragem temporal**: o app oferece filtro opcional por data de pagamento (`Pagto`), com granularidade Dia, Semana ISO, Mês ou intervalo personalizado. As escolhas ficam armazenadas em `st.session_state`.
3. **Resumo**: são exibidos contadores de linhas antes/depois da limpeza e o total do valor corrente. As seções a seguir respeitam o filtro de data ativo.
4. **Guia “Dados limpos”**:
   - Visualização da tabela completa (com datas formatadas e totais analíticos).
   - Downloads: CSV limpo, Excel multipáginas (depende de `xlsxwriter`) e PDF (depende de `reportlab`). O Excel inclui abas com agrupamentos por data, classe e banco; o PDF organiza seções de resumo e detalhamento.
5. **Guia “Montar Relatórios”**:
   - Agrupamentos dinâmicos (multiselect) sobre qualquer coluna relevante.
   - Opções de ordenação, filtros por valor e download do resultado agregado.
   - Geração de conciliação contábil analítica (`_build_accounting_export`) e sintética por agrupamento (`_build_grouped_accounting_export`).
   - PDF específico para o agrupamento livre (se `reportlab` estiver disponível).
6. **Guia “Comparar com OFX”**:
   - Filtros adicionais por banco (`_render_bank_filter_controls`) e período.
   - Upload de um ou mais extratos OFX, consolidados em um único `DataFrame`.
   - Casamento de lançamentos por data e valor (`_match_transactions`), com métricas de contagem e totais.
   - Seções para lançamentos casados, presentes apenas no CSV ou apenas nos OFX, todas com possibilidade de download.

## Limpeza e normalização do CSV
- **Padronização de cabeçalhos**: o dicionário `CANONICAL_COLUMNS` (em `odontotech.py`) trata variações frequentes de nome de coluna (ex.: `Histórico`, `historico`, `Histórico_2`).
- **Remoção de linhas de controle**: linhas cujo primeiro campo começa com `*` são descartadas, contabilizadas em `clean_stats['dropped_star_rows']`.
- **Datas**: colunas `Emissão`, `Vencto` e `Pagto` são convertidas para `datetime64[ns]` com `dayfirst=True`.
- **Valores monetários**: a coluna `Valor` é convertida de formatos brasileiros (pontos para milhares, vírgula decimal) para `float`.
- **Trim de strings**: campos textuais têm espaços removidos do início e fim.

Essas transformações garantem que relatórios exportados do Odontotech, mesmo com pequenas variações, possam ser agrupados e filtrados corretamente no app.

## Exportações suportadas
- **CSV limpo**: sempre disponível; datas ficam formatadas em `dd/mm/yyyy` e o arquivo é UTF-8 com BOM para facilitar abertura no Excel.
- **Excel multipáginas** (`xlsxwriter`): aba principal com os dados filtrados, abas extras com agrupamentos por `Pagto`, `CLASSE` e coluna de banco detectada (`detect_banco_column`), com formatação de moeda BRL.
- **PDF** (`reportlab`): relatórios que concatenam seções de resumo e tabelas (resumo + dados selecionados ou agrupamento + detalhes). A função `_build_pdf` controla layout, espaçamento, totais e quebra automática de página.
- **Conciliação contábil**:
  - `conciliacao_contabil.csv`: extrai um lançamento por linha da base filtrada.
  - `conciliacao_contabil_agrupado.csv`: gera lançamentos por linha de agrupamento (ignorando classes que contenham “PJ”).
  - Ambos os arquivos usam `;` como separador e seguem o layout: `Débito`, `Crédito`, `Histórico`, `Data`, `Valor`, `Complemento`.

## Regras de contas contábeis
O mapeamento está na constante `_ACCOUNTING_RULES` de `app.py` (por volta da linha 229). Cada chave corresponde ao valor normalizado da coluna `CLASSE` e define as contas contábeis e o código de histórico:

| CLASSE normalizada            | Débito | Crédito | Histórico | Observações |
|-------------------------------|--------|---------|-----------|-------------|
| `ATO COMPLEMENTAR PF`         | 13709  | 12767   | 79        | Usado para lançamentos de ato complementar pessoa física. |
| `DESCONTO ADMINISTRATIVO`     | 52874  | 13709   | 221       | Identifica descontos administrativos. |
| `DESCONTOS CONCEDIDOS SOBRE MENSALIDADE` | 52874 | 13709 | 221 | Compartilha a mesma configuração de desconto administrativo. |
| `JUROS E MULTA DE MORA`       | 13709  | 31426   | 20        | Aplica-se a receitas por juros/multa. |
| `MENSALIDADE INDIVIDUAL`     | 13709  | 10550   | 79        | Mensalidades individuais (pessoa física). |
| `MENSALIDADE PJ - FAMILIAR`  | 13709  | 10550   | 5         | Mensalidades de pessoa jurídica familiar. |
| `REEMBOLSO ATO COMPLEMENTAR` | 12767  | 13709   | 5         | Reembolso de atos complementares. |
| `TAXA DE ADESAO / INSCRICAO` | 13709  | 31644   | 224       | Taxas de adesão ou inscrição. |

Como as chaves são normalizadas (remoção de acentos, caixa alta, espaços comprimidos), a coluna `CLASSE` pode conter variações de grafia congêneres sem quebrar o mapeamento.

### Como os arquivos de conciliação são gerados
1. `_normalize_text` remove acentos, converte para maiúsculas e elimina caracteres de combinação.
2. `_accounting_entry_from_values` recebe `CLASSE`, `Valor` e data de pagamento (`Pagto`):
   - Consulta `_ACCOUNTING_RULES`. Se não houver correspondência, retorna campos em branco, permitindo uma revisão manual posterior.
   - A data é formatada em `dd/mm/yyyy` quando válida.
   - O valor é convertido para absoluto com duas casas decimais, representado em formato BRL (vírgula como decimal, sem sinal para créditos/ débitos).
3. `_build_accounting_export` cria um `DataFrame` com as colunas alvo para cada linha dos dados filtrados.
4. `_build_grouped_accounting_export` recebe o resultado de `group_totals`:
   - Determina uma data representativa (priorizando colunas de data presentes no agrupamento).
   - Ignora linhas cuja classe contenha “PJ” para evitar sobreposição com conciliações específicas de pessoa jurídica.
   - Converte cada linha agregada em um lançamento seguindo as mesmas regras de normalização.

Para incluir novas regras contábeis, basta adicionar entradas ao dicionário `_ACCOUNTING_RULES`. Recomenda-se utilizar a forma totalmente maiúscula e sem acentos da descrição do Odontotech, conferindo se o texto normalizado (obtido por `_normalize_text`) coincide com a chave.

## Conciliação com OFX
- O app aceita múltiplos arquivos OFX. Cada um é processado por `_load_ofx_files`, que aproveita `read_ofx_transactions` para produzir um `DataFrame` já tipado.
- O casamento de lançamentos (`_match_transactions`) compara data (convertida para `date`) e valor (com duas casas) e gerencia duplicidades pelo índice cumulativo (`cumcount`).
- São produzidos três conjuntos:
  1. `matches`: lançamentos casados, com colunas do CSV e do OFX lado a lado e coluna `Diferença (CSV-OFX)`.
  2. `odo_only`: lançamentos presentes apenas no CSV limpo.
  3. `ofx_only`: lançamentos presentes apenas no OFX.
- Cada conjunto pode ser baixado em CSV, e as métricas exibem quantidade e soma total (formato BRL).
- Caso não haja lançamentos que casem, o app orienta o usuário a revisar filtros ou dados.

## Dependências
- **Obrigatórias**: `pandas`, `streamlit`.
- **Opcional para PDF**: `reportlab`.
- **Opcional para Excel**: `xlsxwriter`.
- **Outras**: `numpy` (via pandas), bibliotecas padrão (`io`, `unicodedata`, etc.). O arquivo `requirements.txt` contém a lista consolidada.

## Como executar
1. Crie e ative um ambiente virtual (Python 3.10–3.12 recomendado).
2. Instale as dependências: `pip install -r requirements.txt`.
3. Rode o app principal: `streamlit run app.py`.
4. Para o visualizador genérico, execute: `streamlit run main.py`.
5. Utilize os arquivos de `arquivos/` como base de teste, se necessário.

## Extensões e pontos de atenção
- **Novas colunas ou formatações**: amplie `CANONICAL_COLUMNS` em `odontotech.py` para manter a padronização.
- **Novos relatórios**: aproveite `group_totals` e `_select_full_columns` para criar visões específicas ou módulos adicionais.
- **Regras contábeis adicionais**: mantenha `_ACCOUNTING_RULES` atualizado e, se preciso, ajuste `_build_grouped_accounting_export` para contemplar exceções (por exemplo, classes que exijam tratamentos distintos de PJ).
- **Validação**: antes de incluir dados oficiais, recomenda-se validar os relatórios com as planilhas de exemplo e verificar se os totais batem contra o OFX e a contabilidade.

Com essa documentação, é possível compreender a arquitetura do projeto, reproduzir o ambiente local, ajustar regras contábeis e expandir as funcionalidades de conciliação.
