# Conciliação Odontotech

Aplicativo Streamlit para conciliação financeira a partir de relatórios CSV do Odontotech e extratos bancários (futuro). Já faz limpeza, agrupamentos e exportação CSV/Excel/PDF.

## Requisitos

- Python 3.10–3.12 recomendado
- Pip + venv

## Instalação

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Executando

```bash
streamlit run app.py
```

## Funcionalidades

- Upload de CSV do Odontotech (ignora as 3 primeiras linhas)
- Limpeza: remove linhas iniciadas por `*`, normaliza colunas, parse de datas e valores
- Filtros por data (Pagto): Dia, Semana ISO, Mês, ou De… Até
- Agrupamentos por: Pagto, CLASSE e Banco
- Downloads: CSV limpo, agrupamentos em CSV, Excel com abas, PDF (servidor) com resumos e tabela completa (colunas selecionadas)

## Observações

- Para PDFs, instale `reportlab` (já listado no `requirements.txt`). Em Python muito novo, pode ser necessário usar uma versão estável (ex.: 3.12).
- O Excel aplica formatação monetária BRL na coluna `total`.

## Estrutura

- `app.py` – App Streamlit
- `odontotech.py` – Parser e limpeza do CSV
- `requirements.txt` – Dependências

## Licença

Privado/Interno.
