# Regras de negócio e decisões operacionais

## Limpeza e padronização dos dados Odontotech

- **Cabeçalho**: as três primeiras linhas do relatório são descartadas por conterem apenas metadados.  
- **Codificação**: o leitor tenta `utf-8-sig`, `utf-8`, `latin1` e `cp1252` antes de falhar.  
- **Colunas canônicas**: variações de nomes (acentos, abreviações, espaçamentos) são mapeadas para um conjunto padrão (`CANONICAL_COLUMNS`). Em caso de duplicidade, são criados sufixos numéricos para evitar perda de dados.  
- **Linhas de controle**: qualquer linha cujo primeiro campo comece com `*` é removida e contabilizada em `dropped_star_rows`.  
- **Datas**: colunas `Emissão`, `Vencto` e `Pagto` são convertidas para `datetime` com `dayfirst=True`. Conversões mal-sucedidas viram `NaT`.  
- **Valores monetários**: strings no formato brasileiro (`1.234,56`) são limpas, milhares removidos e vírgula transformada em ponto antes de virar `float`. Valores inválidos viram `NaN` e depois `0.0` quando necessário.

## Filtros e estado

- **Filtro global de período (Pagto)**: só é aplicado quando o checkbox “Filtrar por Período” está ativo.  
  - *Dia*: intervalo fechado no dia selecionado.  
  - *Semana*: usa o calendário ISO (`year`, `week`).  
  - *Mês*: compara o período `to_period("M")`.  
  - *De… Até*: transforma a data final em final de dia (23:59:59.999999) para incluir registros completos.  
- **Filtro de bancos**: identifica automaticamente a melhor coluna (`Nome Banco` > `NºBanco` > `ID Banco` > `ID Conta Corrente`). O usuário pode restringir a um subconjunto de bancos; avisos são exibidos se não houver correspondências.

## Agrupamentos e totais

- `group_totals` agrega por uma ou mais colunas válidas, calculando `qtd` (contagem de registros) e `total` (soma do valor de referência, padrão `Valor`).  
- Agrupamentos livres permitem filtros adicionais por valores selecionados e ordenação multi-coluna com controle de crescente/decrescente.  
- Totais analíticos mostram sempre o número de linhas e soma da coluna `Valor` após os filtros atuais.

## Exportações contábeis

- O mapa `_ACCOUNTING_RULES` (arquivo `app.py`) traduz classes específicas do Odontotech em combinações de contas (`Débito`, `Crédito`) e códigos de histórico.  
- A exportação **analítica** (`_build_accounting_export`) gera uma linha por lançamento filtrado, respeitando o sinal do valor (exportado como valor absoluto).  
- A exportação **agrupada** (`_build_grouped_accounting_export`) consolida totals por grupo e ignora classes contendo “PJ” (não devem gerar lançamentos). Quando não existe data explícita no agrupamento, tenta usar `Pagto` ou outra coluna com valor convertível para data.  
- Tanto analítico quanto agrupado produzem CSV com `;` como separador, atendendo sistemas contábeis nacionais.

## Conciliação com OFX

- Arquivos OFX são combinados em um único dataframe, mantendo a coluna `Arquivo` para rastreabilidade.  
- Datas são normalizadas (`pd.to_datetime`) e valores convertidos para `float`.  
- O casamento considera pares (`data`, `valor`) após arredondamento para duas casas decimais e controla duplicidades via `cumcount`, garantindo que múltiplas ocorrências do mesmo valor no mesmo dia sejam tratadas individualmente.  
- Resultados são divididos em três conjuntos:
  - `matches`: presentes nas duas fontes (`Valor_odontotech` x `Valor_ofx`) com diferença calculada.  
  - `odo_only`: lançamentos do CSV sem par correspondente no OFX.  
  - `ofx_only`: lançamentos do OFX não presentes no CSV.  
- Cada conjunto é disponibilizado para download e exibido com colunas relevantes (classe, histórico, documento, memo, etc.).

## Visualizador genérico (`main.py`)

- **Detecção de tipo**: considera extensão `.ofx`, presença de tags `<OFX>`, textos característicos de relatórios (“Relatório de Contas Pagas/Receber”, “Sacado,,,Nosso Número”).  
- **Francesinha**: remove linhas com prefixos conhecidos, ignora totais, padroniza colunas monetárias e de data, permite filtrar por previsão de crédito e gerar totais por data.  
- **Relatórios de contas**: tratam cabeçalhos duplicados, removem cabeçalhos/rodapés e convertem valores e datas relevantes.  
- **Filtros dinâmicos**: apenas colunas com até 200 valores únicos viram filtros categóricos para evitar componentes pesados. Valores nulos podem ser incluídos conforme opção do usuário.  
- **Exportação**: sempre oferece download do dataframe filtrado como CSV com BOM em `utf-8`.

## Outras considerações

- A aplicação usa `@st.cache_data` para evitar reprocessamento ao refazer downloads com o mesmo arquivo.  
- Todos os downloads usam codificação `utf-8-sig`, evitando problemas em Excel/Windows.  
- Mensagens de alerta são exibidas quando bibliotecas opcionais estão ausentes ou quando filtros resultam em conjuntos vazios.

