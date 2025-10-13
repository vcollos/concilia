# Histórico de alterações relevantes

> Não mantemos datas/versionamento formal neste repositório. A linha do tempo abaixo resume os marcos conhecidos e o motivo de cada mudança.

## Marco 1 — Fluxo Odontotech inicial
- Leitura do CSV com descarte das três primeiras linhas.
- Limpeza básica (`canonicalize_columns`, `_drop_star_rows`, parse de datas/valores).
- Exibição da tabela limpa e download do CSV.

## Marco 2 — Relatórios consolidados
- Inclusão dos agrupamentos padrão (por data, classe, banco) usando `group_totals`.
- Exportação para Excel multi-aba (`xlsxwriter`) com formatação monetária e de datas.
- Geração de PDF com resumo + tabela principal (dependência `reportlab`).

## Marco 3 — Conciliação contábil
- Implementação das regras `_ACCOUNTING_RULES` para mapear classes em débitos/créditos.
- Exportações analítica e agrupada para CSV com layout esperado pela contabilidade.

## Marco 4 — Comparação com extratos bancários
- Parser dedicado de OFX (`ofx_utils.py`) e upload múltiplo de extratos.
- Casamento de lançamentos por data e valor com controle de duplicidades (`_match_transactions`).
- Tabelas e downloads separados para casamentos, somente CSV e somente OFX.

## Marco 5 — UI simplificada e agrupamento livre
- Remoção das abas fixas “Por CLASSE” e “Por banco”, substituídas por um agrupamento totalmente configurável.
- Adição de filtros dinâmicos por coluna agrupada e ordenação multi-nível.
- PDF específico para o agrupamento livre, mantendo estrutura semelhante ao relatório principal.

## Marco 6 — Visualizador genérico (auxiliar)
- Criação de `main.py` para tratar francesinhas, relatórios de contas e OFX de forma rápida.
- Implementação de filtros automáticos por tipo de coluna e download imediato do subconjunto filtrado.
- Inclusão da lista de arquivos de exemplo na barra lateral (pasta `arquivos/`).

