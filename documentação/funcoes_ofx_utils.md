# Referência de funções — `ofx_utils.py`

## `_read_bytes` — `ofx_utils.py:9`
- **Responsabilidade**: obter bytes de diferentes entradas (UploadedFile, file-like, bytes, caminho).
- **Retorno**: sequência de bytes pronta para decodificação.
- **Notas**: reposiciona o cursor (`seek(0)`) quando o objeto oferece suporte.

## `_decode_text` — `ofx_utils.py:31`
- **Responsabilidade**: decodificar bytes tentando múltiplas codificações (`utf-8-sig`, `utf-8`, `cp1252`, `latin1`).
- **Retorno**: string; fallback ignora erros para preservar o máximo possível.

## `_strip_trailing_tag` — `ofx_utils.py:40`
- **Responsabilidade**: remover conteúdos após um `<` em uma linha OFX (tratando tags sem fechamento).
- **Uso**: limpeza dos valores capturados nos blocos `<STMTTRN>`.

## `_parse_stmttrn_blocks` — `ofx_utils.py:46`
- **Responsabilidade**: iterar sobre o texto OFX e construir dicionários com os campos de cada transação (`<STMTTRN>`).
- **Retorno**: lista de dicionários com chaves maiúsculas.
- **Regra**: lida apenas com tags simples (`<TAG>valor`), ignorando blocos inesperados.

## `_parse_ofx_date` — `ofx_utils.py:78`
- **Responsabilidade**: converter data OFX (com ou sem hora/fuso) para `pd.Timestamp`.
- **Suporta**: formatos `YYYYMMDDHHMMSS`, `YYYYMMDDHHMM`, `YYYYMMDD`, além de fallback via `pd.to_datetime`.
- **Retorno**: `Timestamp` ou `NaT`.

## `_parse_amount` — `ofx_utils.py:102`
- **Responsabilidade**: converter string de valor (padrão americano, `.` decimal) para `float`.
- **Retorno**: `float` ou `None`.

## `read_ofx_transactions` — `ofx_utils.py:114`
- **Responsabilidade**: pipeline completo de leitura OFX.
- **Entradas**: qualquer entrada suportada por `_read_bytes`.
- **Processo**:
  1. Lê bytes e decodifica texto.  
  2. Extrai blocos `<STMTTRN>`.  
  3. Normaliza cada campo (Data, Valor, Tipo, Descrição, Documento, Identificador, Memo, Nome).  
  4. Converte datas e valores com `pandas`.  
  5. Ordena por Data e Identificador.
- **Retorno**: dataframe ordenado e reindexado.

