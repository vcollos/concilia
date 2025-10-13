# Referência de funções — `odontotech.py`

## `_strip_accents` — `odontotech.py:51`
- **Responsabilidade**: remover acentuação usando normalização Unicode (`NFKD`).
- **Uso**: preparação de chaves canônicas.

## `_normalize_key` — `odontotech.py:55`
- **Responsabilidade**: transformar nomes de colunas em uma chave normalizada (minúsculas, sem acentos, sem pontuação repetida).
- **Entradas**: nome original da coluna.
- **Retorno**: string canônica utilizada para consultar `CANONICAL_COLUMNS`.

## `canonicalize_columns` — `odontotech.py:63`
- **Responsabilidade**: renomear colunas conforme o mapa canônico e evitar colisões.
- **Entradas**: dataframe original.
- **Retorno**: dataframe com colunas padronizadas.
- **Notas**: cria sufixos (`_2`, `_3`) quando necessário e mantém colunas não mapeadas com `strip()`.

## `_to_brazil_float` — `odontotech.py:89`
- **Responsabilidade**: converter série em valores numéricos (suporta formato brasileiro).
- **Entradas**: série (numérica ou texto).
- **Retorno**: série float com `NaN` onde a conversão falhou.
- **Regras**: remove caracteres não numéricos, trata `.` como separador de milhar e `,` como decimal.

## `_parse_dates` — `odontotech.py:104`
- **Responsabilidade**: converter colunas passadas para datetime (`dayfirst=True`).
- **Entradas**: dataframe e lista de colunas.
- **Retorno**: dataframe com datas parseadas.

## `_drop_star_rows` — `odontotech.py:111`
- **Responsabilidade**: remover linhas cujo primeiro campo inicia com `*`.
- **Entradas**: dataframe.
- **Retorno**: tupla `(dataframe_sem_linhas, quantidade_descartada)`.
- **Notas**: cedo na limpeza para evitar que linhas de controle contaminem totais.

## `read_odontotech_csv` — `odontotech.py:122`
- **Responsabilidade**: ler arquivo do Odontotech (Streamlit upload, bytes ou caminho) aplicando heurísticas de codificação e separador.
- **Entradas**: file-like, bytes ou string (caminho).
- **Retorno**: tupla `(dataframe_bruto, stats)`; `stats` contém `encoding`, `sep`, `skipped_header_lines`.
- **Regras**: tenta `utf-8-sig`, `utf-8`, `latin1`, `cp1252`. Se falhar, tenta separadores `;`, `\t`, `,`.

## `clean_odontotech_df` — `odontotech.py:178`
- **Responsabilidade**: aplicar a sequência completa de limpeza do relatório.
- **Entradas**: dataframe bruto.
- **Retorno**: tupla `(dataframe_limpo, stats)` com métricas `dropped_star_rows`, `initial_rows`, `final_rows`, `parsed_dates`, `parsed_valor`.
- **Passos**:
  1. Canonicalização de colunas.  
  2. Remoção de linhas iniciadas com `*`.  
  3. `strip()` em colunas de texto.  
  4. Parse das datas (`Emissão`, `Vencto`, `Pagto`).  
  5. Conversão da coluna `Valor` para float e preenchimento de `NaN` com `0.0`.

## `group_totals` — `odontotech.py:223`
- **Responsabilidade**: agregar dataframe por colunas informadas calculando contagem (`qtd`) e soma (`total`).
- **Entradas**: dataframe, iterável de colunas, nome da coluna de valor (default `Valor`).
- **Retorno**: dataframe agregado ordenado.
- **Validação**: lança `ValueError` se nenhuma coluna válida for passada.

## `detect_banco_column` — `odontotech.py:241`
- **Responsabilidade**: identificar automaticamente qual coluna representa banco/conta.
- **Retorno**: nome da primeira coluna encontrada na ordem de prioridade ou `None`.
- **Uso**: determina a coluna sugerida no filtro por banco e no agrupamento padrão por instituição.

