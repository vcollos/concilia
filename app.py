import io
import unicodedata
from typing import List, Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Optional: ReportLab for server-side PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

from odontotech import (
    clean_odontotech_df,
    detect_banco_column,
    group_totals,
    read_odontotech_csv,
)
from ofx_utils import read_ofx_transactions


st.set_page_config(page_title="Conciliação Odontotech", layout="wide")
st.title("Conciliação financeira – Odontotech → DataFrame limpo")
st.caption(
    "Carregue o CSV do Odontotech (ignora as 3 primeiras linhas, remove linhas iniciadas por '*', parseia datas e valores)."
)

# Inject print CSS for A4 portrait and hide chrome while printing
st.markdown(
    """
    <style>
    @page { size: A4 portrait; margin: 10mm; }
    @media print {
      header, footer, div[data-testid="stSidebar"], section[data-testid="stHeader"], #MainMenu { display: none !important; }
      .block-container { padding: 0 !important; }
      body { -webkit-print-color-adjust: exact; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _process_file(uploaded_file):
    raw_df, read_stats = read_odontotech_csv(uploaded_file)
    cleaned_df, clean_stats = clean_odontotech_df(raw_df)
    return raw_df, read_stats, cleaned_df, clean_stats


def _fmt_brl(n):
    try:
        return (f"R$ {float(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    except Exception:
        return str(n)


def _format_total_column(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if "total" in df.columns:
        out = df.copy()
        out["total"] = out["total"].map(_fmt_brl)
        return out
    return df


def _format_dates_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for c in out.columns:
        if str(out[c].dtype).startswith("datetime64"):
            out[c] = out[c].dt.strftime("%d/%m/%Y")
    return out


def _show_group_totals(g: pd.DataFrame):
    try:
        total_qtd = int(g["qtd"].sum()) if "qtd" in g.columns else None
        total_sum = float(g["total"].sum()) if "total" in g.columns else None
        parts = []
        if total_qtd is not None:
            parts.append(f"Qtd: {total_qtd}")
        if total_sum is not None:
            parts.append(f"Total: {_fmt_brl(total_sum)}")
        if parts:
            st.markdown(" ".join(["**Total do agrupamento:**"] + parts))
    except Exception:
        pass


def _show_analytic_totals(df_src: pd.DataFrame):
    try:
        n = int(df_src.shape[0])
        total_sum = float(df_src["Valor"].sum()) if "Valor" in df_src.columns else 0.0
        st.markdown(f"**Total analítico:** Registros: {n} • Valor: {_fmt_brl(total_sum)}")
    except Exception:
        pass


def _format_df_for_pdf(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    # Format datetimes to dd/mm/yyyy
    for c in out.columns:
        if str(out[c].dtype).startswith("datetime64"):
            out[c] = out[c].dt.strftime("%d/%m/%Y")
    # Format Valor as BRL if present
    if "Valor" in out.columns:
        out["Valor"] = out["Valor"].map(_fmt_brl)
    if "total" in out.columns:
        out["total"] = out["total"].map(_fmt_brl)
    return out


def _df_to_table_flowable(df: pd.DataFrame, title: str, col_widths=None):
    styles = getSampleStyleSheet()
    elems = []
    elems.append(Paragraph(title, styles["Heading3"]))
    if df.empty:
        elems.append(Paragraph("Sem dados.", styles["BodyText"]))
        elems.append(Spacer(1, 6))
        return elems
    # Convert cells to Paragraph for word-wrap
    para_style = ParagraphStyle(
        name="Cell",
        parent=styles["BodyText"],
        fontSize=8,
        leading=9,
        wordWrap="CJK",
    )
    header = [Paragraph(str(c), ParagraphStyle(name="Head", parent=styles["BodyText"], fontSize=8, leading=9)) for c in df.columns]
    rows = [[Paragraph(str(v), para_style) for v in row] for row in df.astype(str).values.tolist()]
    data = [header] + rows
    # Column widths
    if col_widths is None:
        page_width = A4[0] - 2 * 15 * mm
        col_width = max(40, page_width / max(1, len(df.columns)))
        col_widths = [col_width for _ in df.columns]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ]
        )
    )
    elems.append(tbl)
    elems.append(Spacer(1, 8))
    return elems


def _build_pdf(
    title: str,
    summary: dict,
    filter_summary: str,
    sections: list[tuple[str, pd.DataFrame]],
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 6))

    # Summary block
    s = (
        f"Linhas originais: <b>{summary.get('initial_rows', '-')}</b> &nbsp;&nbsp;"
        f"Removidas (*): <b>{summary.get('dropped_star_rows', '-')}</b> &nbsp;&nbsp;"
        f"Linhas finais: <b>{summary.get('final_rows', '-')}</b> &nbsp;&nbsp;"
        f"Total Valor: <b>{_fmt_brl(summary.get('total_valor', 0))}</b>"
    )
    story.append(Paragraph(s, styles["BodyText"]))
    story.append(Paragraph(f"Período: {filter_summary}", styles["BodyText"]))
    story.append(Spacer(1, 8))

    # Sections (tables)
    def _title_with_total(t: str, df_in: pd.DataFrame) -> str:
        try:
            if df_in is None or df_in.empty:
                return t
            if "total" in df_in.columns:
                s = float(pd.to_numeric(df_in["total"], errors="coerce").fillna(0).sum())
                return f"{t} — Total: {_fmt_brl(s)}"
            if "Valor" in df_in.columns:
                s = float(pd.to_numeric(df_in["Valor"], errors="coerce").fillna(0).sum())
                return f"{t} — Total: {_fmt_brl(s)}"
            return t
        except Exception:
            return t

    for sec_title, sec_df in sections:
        sec_title_final = _title_with_total(sec_title, sec_df)
        sec_df_fmt = _format_df_for_pdf(sec_df)
        col_widths = None
        if "Registros (colunas selecionadas)" in sec_title:
            # Allocate widths tailored for the selected columns
            page_width = A4[0] - 2 * 15 * mm
            weights = []
            for c in sec_df_fmt.columns:
                k = c.lower()
                if k.startswith("pagto"):
                    weights.append(0.12)
                elif k == "valor":
                    weights.append(0.10)
                elif k == "classe":
                    weights.append(0.10)
                elif k.startswith("forma de pagamento"):
                    weights.append(0.16)
                elif k.startswith("nome banco"):
                    weights.append(0.16)
                elif "histor" in k:
                    weights.append(0.26)
                elif k.startswith("id conta corrente"):
                    weights.append(0.10)
                else:
                    weights.append(1.0)
            # Normalize weights
            s = sum(weights) if sum(weights) > 0 else 1.0
            weights = [w / s for w in weights]
            col_widths = [max(40, page_width * w) for w in weights]
        story.extend(_df_to_table_flowable(sec_df_fmt, sec_title_final, col_widths=col_widths))
        # Page break after very large sections might be added automatically by flowables

    doc.build(story)
    return buf.getvalue()


_ACCOUNTING_RULES = {
    "ATO COMPLEMENTAR PF": ("13709", "12767", "79"),
    "DESCONTO ADMINISTRATIVO": ("52874", "13709", "221"),
    "DESCONTOS CONCEDIDOS SOBRE MENSALIDADE": ("52874", "13709", "221"),
    "JUROS E MULTA DE MORA": ("13709", "31426", "20"),
    "MENSALIDADE INDIVIDUAL": ("13709", "10550", "79"),
    "MENSALIDADE PJ - FAMILIAR": ("13709", "10550", "5"),
    "REEMBOLSO ATO COMPLEMENTAR": ("12767", "13709", "5"),
    "TAXA DE ADESAO / INSCRICAO": ("13709", "31644", "224"),
}


def _normalize_text(text) -> str:
    if text is None:
        return ""
    norm = unicodedata.normalize("NFKD", str(text)).strip()
    return "".join(ch for ch in norm if not unicodedata.combining(ch)).upper()


def _accounting_entry_from_values(
    complemento_raw,
    amount_raw,
    date_raw,
) -> dict:
    complemento = "" if complemento_raw is None else str(complemento_raw)
    complemento_norm = _normalize_text(complemento)
    debit, credit, history = _ACCOUNTING_RULES.get(complemento_norm, ("", "", ""))

    date_fmt = ""
    try:
        ts = pd.to_datetime(date_raw, errors="coerce")
        if pd.notna(ts):
            date_fmt = ts.strftime("%d/%m/%Y")
    except Exception:
        date_fmt = ""

    valor_fmt = ""
    try:
        if pd.notna(amount_raw):
            valor_float = abs(float(amount_raw))
            valor_fmt = (
                f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
    except Exception:
        valor_fmt = str(amount_raw).replace("-", "") if amount_raw is not None else ""

    return {
        "Débito": debit,
        "Crédito": credit,
        "Histórico": history,
        "Data": date_fmt,
        "Valor": valor_fmt,
        "Complemento": complemento,
    }


def _build_accounting_export(df: pd.DataFrame) -> pd.DataFrame:
    target_cols = ["Débito", "Crédito", "Histórico", "Data", "Valor", "Complemento"]
    if df is None or df.empty:
        return pd.DataFrame(columns=target_cols)
    required_columns = {"Pagto", "Valor", "CLASSE"}
    if not required_columns.issubset(df.columns):
        return pd.DataFrame(columns=target_cols)

    working = df.copy()
    working["_Pagto"] = pd.to_datetime(working["Pagto"], errors="coerce")
    working["_Complemento"] = working["CLASSE"].fillna("").astype(str)

    records = []
    for _, row in working.iterrows():
        complemento_norm = _normalize_text(row.get("_Complemento"))
        if complemento_norm == "ATO COMPLEMENTAR PJ":
            continue
        records.append(
            _accounting_entry_from_values(
                row.get("_Complemento"),
                row.get("Valor"),
                row.get("_Pagto"),
            )
        )

    return pd.DataFrame(records, columns=target_cols)


def _build_grouped_accounting_export(grouped_df: pd.DataFrame, grouping_cols: list[str]) -> pd.DataFrame:
    target_cols = ["Débito", "Crédito", "Histórico", "Data", "Valor", "Complemento"]
    if grouped_df is None or grouped_df.empty:
        return pd.DataFrame(columns=target_cols)
    if "CLASSE" not in grouped_df.columns or "total" not in grouped_df.columns:
        return pd.DataFrame(columns=target_cols)

    def _pick_date(row):
        if "Pagto" in grouped_df.columns:
            return row.get("Pagto")
        for col in grouping_cols:
            val = row.get(col)
            try:
                ts = pd.to_datetime(val, errors="coerce")
            except Exception:
                ts = pd.NaT
            if pd.notna(ts):
                return ts
        return None

    records = []
    for _, row in grouped_df.iterrows():
        complemento_norm = _normalize_text(row.get("CLASSE"))
        if complemento_norm == "ATO COMPLEMENTAR PJ":
            continue
        records.append(
            _accounting_entry_from_values(
                row.get("CLASSE"),
                row.get("total"),
                _pick_date(row),
            )
        )

    return pd.DataFrame(records, columns=target_cols)


def _select_full_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return view with only required columns for the full data table, in order.
    Target columns: Pagto, HISTORICO, Valor, CLASSE, Forma de Pagamento, Nome Banco, ID Conta Corrente
    Handles canonical variants like 'Historico'/'Histórico'.
    """
    cols_order = [
        "Pagto",
        ("HISTORICO", ["HISTORICO", "Historico", "Histórico"]),
        "Valor",
        "CLASSE",
        "Forma de Pagamento",
        "Nome Banco",
        "ID Conta Corrente",
    ]
    selected = []
    for item in cols_order:
        if isinstance(item, tuple):
            target, variants = item
            found = next((v for v in variants if v in df.columns), None)
            if found:
                selected.append(found)
        else:
            if item in df.columns:
                selected.append(item)
    return df[selected].copy() if selected else df.copy()


def _summary_tables(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Build the three summary tables with new titles and preferred columns.
    - Totais por Pagto -> Totais por Data de Pagamento
    - Totais por CLASSE -> Totais por Classe
    - Totais por Nome Banco -> Totais por Banco
    """
    sections: list[tuple[str, pd.DataFrame]] = []
    if "Pagto" in df.columns:
        sections.append(("Totais por Data de Pagamento", group_totals(df, ["Pagto"])) )
    if "CLASSE" in df.columns:
        sections.append(("Totais por Classe", group_totals(df, ["CLASSE"])) )
    if "Nome Banco" in df.columns:
        sections.append(("Totais por Banco", group_totals(df, ["Nome Banco"])) )
    return sections


def _detail_sections_from_summary(src_df: pd.DataFrame, g_summary: pd.DataFrame, by_cols: List[str]) -> list[tuple[str, pd.DataFrame]]:
    """Build analytic sections per group row in g_summary, using by_cols order.
    The detail tables include only selected report columns.
    """
    if src_df is None or src_df.empty or g_summary is None or g_summary.empty:
        return []
    sections: list[tuple[str, pd.DataFrame]] = []
    for _, row in g_summary.iterrows():
        mask = pd.Series(True, index=src_df.index)
        parts = []
        for col in by_cols:
            val = row[col] if col in row else None
            if pd.isna(val):
                mask &= src_df[col].isna()
                parts.append(f"{col}=nulo")
            else:
                if isinstance(val, pd.Timestamp):
                    mask &= src_df[col] == val
                    parts.append(val.strftime("%d/%m/%Y"))
                else:
                    mask &= src_df[col] == val
                    parts.append(str(val))
        detail = src_df.loc[mask]
        if detail.empty:
            continue
        title = "Detalhes – " + " | ".join(parts)
        sections.append((title, _select_full_columns(detail)))
    return sections


uploaded = st.file_uploader("CSV do Odontotech", type=["csv", "txt"]) 

if not uploaded:
    st.info(
        "Selecione um arquivo CSV do Odontotech. As 3 primeiras linhas do relatório serão ignoradas."
    )
    st.stop()


with st.spinner("Processando arquivo…"):
    raw_df, read_stats, df, clean_stats = _process_file(uploaded)


def _date_columns(current_df: pd.DataFrame) -> List[str]:
    # Keep only payment date for filtering
    return [c for c in ["Pagto"] if c in current_df.columns]


def render_date_filter_controls(current_df: pd.DataFrame, ns: str) -> None:
    st.markdown("### Filtro por data de pagamento")
    if "Pagto" not in current_df.columns:
        st.caption("Coluna 'Pagto' não encontrada no arquivo.")
        return
    # Toggle enable/disable
    enabled = st.session_state.get("flt_enabled", False)
    enabled = st.checkbox("Filtrar por Período", value=enabled, key=f"{ns}_flt_enabled")
    st.session_state["flt_enabled"] = enabled
    if not enabled:
        return
    gran_options = ["Dia", "Semana", "Mês", "De... Até"]
    global_gran = st.session_state.get("flt_gran", "Dia")
    gran_idx = gran_options.index(global_gran) if global_gran in gran_options else 0
    gran = st.radio("Granularidade", options=gran_options, horizontal=True, index=gran_idx, key=f"{ns}_flt_gran")
    st.session_state["flt_gran"] = gran

    date_col = "Pagto"
    col_min = pd.to_datetime(current_df[date_col])
    min_date = col_min.min()
    max_date = col_min.max()
    if gran == "Dia":
        default_day = st.session_state.get("flt_day", None)
        chosen = st.date_input(
            "Dia",
            value=default_day,
            min_value=min_date.date() if pd.notna(min_date) else None,
            max_value=max_date.date() if pd.notna(max_date) else None,
            key=f"{ns}_flt_day",
        )
        if chosen:
            st.session_state["flt_day"] = chosen
    elif gran == "Semana":
        iso = current_df[date_col].dt.isocalendar()
        week_pairs = sorted(set(zip(iso.year.fillna(0).astype(int), iso.week.fillna(0).astype(int))))
        labels = [f"{y}-W{int(w):02d}" for (y, w) in week_pairs if y > 0 and w > 0]
        if labels:
            default_week = st.session_state.get("flt_week_label", None)
            widx = labels.index(default_week) if default_week in labels else 0
            chosen = st.selectbox("Semana (ISO)", options=labels, index=widx, key=f"{ns}_flt_week_label")
            st.session_state["flt_week_label"] = chosen
    elif gran == "Mês":
        months = current_df[date_col].dt.to_period("M").dropna().unique()
        months = sorted(months)
        labels = [str(p) for p in months]
        if labels:
            default_month = st.session_state.get("flt_month_label", None)
            midx = labels.index(default_month) if default_month in labels else 0
            chosen = st.selectbox("Mês", options=labels, index=midx, key=f"{ns}_flt_month_label")
            st.session_state["flt_month_label"] = chosen
    elif gran == "De... Até":
        default_range = st.session_state.get("flt_range", (None, None))
        chosen = st.date_input(
            "Período (De... Até)",
            value=default_range,
            min_value=min_date.date() if pd.notna(min_date) else None,
            max_value=max_date.date() if pd.notna(max_date) else None,
            key=f"{ns}_flt_range",
        )
        if isinstance(chosen, (list, tuple)) and len(chosen) == 2:
            st.session_state["flt_range"] = (chosen[0], chosen[1])


def apply_date_filter(current_df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    if "Pagto" not in current_df.columns or not st.session_state.get("flt_enabled"):
        return current_df, "Sem filtro de data"
    date_col = "Pagto"
    gran = st.session_state.get("flt_gran")
    if gran == "Dia" and st.session_state.get("flt_day"):
        start = pd.to_datetime(st.session_state["flt_day"])
        end = start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        mask = (current_df[date_col] >= start) & (current_df[date_col] <= end)
        return current_df.loc[mask].copy(), f"{date_col} no dia {start.date()}"
    if gran == "Semana" and st.session_state.get("flt_week_label"):
        y_sel, w_sel = str(st.session_state["flt_week_label"]).split("-W")
        y_sel = int(y_sel)
        w_sel = int(w_sel)
        iso_all = current_df[date_col].dt.isocalendar()
        mask = (iso_all.year == y_sel) & (iso_all.week == w_sel)
        return current_df.loc[mask].copy(), f"{date_col} na semana ISO {y_sel}-W{w_sel:02d}"
    if gran == "Mês" and st.session_state.get("flt_month_label"):
        period = pd.Period(st.session_state["flt_month_label"], freq="M")
        mask = current_df[date_col].dt.to_period("M") == period
        return current_df.loc[mask].copy(), f"{date_col} no mês {period}"
    if gran == "De... Até" and st.session_state.get("flt_range"):
        start_date, end_date = st.session_state["flt_range"]
        if start_date and end_date:
            start = pd.to_datetime(start_date)
            # inclusive end-of-day
            end = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            mask = (current_df[date_col] >= start) & (current_df[date_col] <= end)
            return current_df.loc[mask].copy(), f"{date_col} de {start.date()} até {end_date}"
    return current_df, "Sem filtro de data"


def _load_ofx_files(files: List) -> tuple[pd.DataFrame, List[str]]:
    frames: List[pd.DataFrame] = []
    messages: List[str] = []
    for upload in files:
        try:
            df_tmp = read_ofx_transactions(upload)
        except Exception as exc:  # pragma: no cover - defensive
            messages.append(f"{upload.name}: erro ao ler ({exc})")
            continue
        if df_tmp is None or df_tmp.empty:
            messages.append(f"{upload.name}: nenhum lançamento encontrado")
            continue
        tmp = df_tmp.copy()
        tmp["Arquivo"] = upload.name
        frames.append(tmp)
    if not frames:
        return pd.DataFrame(), messages
    combined = pd.concat(frames, ignore_index=True)
    if "Data" in combined.columns:
        combined["Data"] = pd.to_datetime(combined["Data"], errors="coerce")
    if "Valor" in combined.columns:
        combined["Valor"] = pd.to_numeric(combined["Valor"], errors="coerce")
    sort_cols = [col for col in ["Data", "Valor", "Identificador", "Arquivo"] if col in combined.columns]
    if sort_cols:
        combined = combined.sort_values(sort_cols, na_position="last").reset_index(drop=True)
    return combined, messages


def _match_transactions(df_clean: pd.DataFrame, df_ofx: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df_clean is None or df_clean.empty or df_ofx is None or df_ofx.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if "Pagto" not in df_clean.columns or "Valor" not in df_clean.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    odo = df_clean.copy()
    ofx = df_ofx.copy()

    odo["match_date"] = pd.to_datetime(odo["Pagto"], errors="coerce").dt.date
    odo["match_value"] = pd.to_numeric(odo["Valor"], errors="coerce").round(2)
    ofx["match_date"] = pd.to_datetime(ofx["Data"], errors="coerce").dt.date
    ofx["match_value"] = pd.to_numeric(ofx["Valor"], errors="coerce").round(2)

    odo = odo.dropna(subset=["match_date", "match_value"]).copy()
    ofx = ofx.dropna(subset=["match_date", "match_value"]).copy()

    odo["match_idx"] = odo.groupby(["match_date", "match_value"]).cumcount()
    ofx["match_idx"] = ofx.groupby(["match_date", "match_value"]).cumcount()

    merged = odo.merge(
        ofx,
        how="outer",
        left_on=["match_date", "match_value", "match_idx"],
        right_on=["match_date", "match_value", "match_idx"],
        suffixes=("_odontotech", "_ofx"),
        indicator=True,
    )

    matches = merged.loc[merged["_merge"] == "both"].copy()
    odo_only = merged.loc[merged["_merge"] == "left_only"].copy()
    ofx_only = merged.loc[merged["_merge"] == "right_only"].copy()

    for df_out in (matches, odo_only, ofx_only):
        for col in ["match_date", "match_value", "match_idx", "_merge"]:
            if col in df_out.columns:
                df_out.drop(columns=col, inplace=True)

    if not matches.empty and {"Valor_odontotech", "Valor_ofx"}.issubset(matches.columns):
        matches["Diferença"] = matches["Valor_odontotech"] - matches["Valor_ofx"]

    return matches, odo_only, ofx_only


def _select_existing(df: pd.DataFrame, columns: List[str]) -> List[str]:
    return [col for col in columns if col in df.columns]


def _sum_column(df: pd.DataFrame, column: str) -> float:
    if df is None or df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def _render_bank_filter_controls(df: pd.DataFrame, ns: str) -> tuple[pd.DataFrame, str]:
    if df is None or df.empty:
        return df, "Sem filtro de banco"

    available = [
        col
        for col in ["Nome Banco", "NºBanco", "ID Banco", "ID Conta Corrente"]
        if col in df.columns
    ]
    if not available:
        st.caption("Nenhuma coluna de banco encontrada no CSV limpo.")
        return df, "Sem filtro de banco"

    default_col = detect_banco_column(df) or available[0]
    if default_col not in available:
        default_col = available[0]

    try:
        default_index = available.index(default_col)
    except ValueError:
        default_index = 0

    banco_col = st.selectbox(
        "Coluna para identificar o banco",
        options=available,
        index=default_index,
        key=f"{ns}_bank_col",
    )

    valores_disponiveis = sorted(
        [v for v in df[banco_col].dropna().unique().tolist()],
        key=lambda x: str(x).lower(),
    )

    selecionados = st.multiselect(
        "Qual(is) banco(s) deseja conciliar?",
        options=valores_disponiveis,
        key=f"{ns}_bank_values",
    )

    if selecionados:
        filtrado = df[df[banco_col].isin(selecionados)].copy()
        resumo = f"{banco_col}: {', '.join(str(v) for v in selecionados)}"
        if filtrado.empty:
            st.warning("Nenhum registro do CSV corresponde aos bancos selecionados.")
        return filtrado, resumo

    return df, "Sem filtro de banco"

st.subheader("Resumo do processamento (visão atual)")
# Apply global period filter (if any) to reflect current view in the summary
df_top_view, filter_summary_top = apply_date_filter(df)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Linhas originais", f"{clean_stats['initial_rows']}")
col2.metric("Linhas removidas (*)", f"{clean_stats['dropped_star_rows']}")
col3.metric("Linhas finais", f"{df_top_view.shape[0]}")
total_valor = df_top_view["Valor"].sum() if "Valor" in df_top_view.columns else 0.0
col4.metric("Total Valor", f"R$ {total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
st.caption(f"Período: {filter_summary_top}")


st.divider()

tabs = st.tabs(["Dados limpos", "Montar Relatórios", "Comparar com OFX"]) 

with tabs[0]:
    st.write("Pré-visualização dos dados limpos:")
    render_date_filter_controls(df, ns="tab0")
    df_view, filter_summary = apply_date_filter(df)
    st.caption(f"Filtro: {filter_summary}")
    st.dataframe(_format_dates_for_display(df_view), use_container_width=True, height=450)
    _show_analytic_totals(df_view)

    # Download cleaned file
    csv_clean = _format_dates_for_display(df_view).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Baixar CSV limpo",
        data=csv_clean,
        file_name="odontotech_limpo.csv",
        mime="text/csv",
    )

    # Build full report PDF (all main tabs except Agrupar livre)
    if REPORTLAB_AVAILABLE:
        if st.button("Baixar PDF – relatório", key="pdf_tab0"):
            sections = []
            # Summary tables first, intended to fit on first page
            sections.extend(_summary_tables(df_view))
            # Then full data with limited columns
            full_df = _select_full_columns(df_view)
            sections.append(("Registros (colunas selecionadas)", full_df))

            summary = {
                "initial_rows": clean_stats.get("initial_rows"),
                "dropped_star_rows": clean_stats.get("dropped_star_rows"),
                "final_rows": df_view.shape[0],
                "total_valor": float(df_view["Valor"].sum()) if "Valor" in df_view.columns else 0.0,
            }
            pdf_bytes = _build_pdf("Relatório – Conciliação Odontotech", summary, filter_summary, sections)
            st.download_button(
                "Baixar PDF gerado",
                data=pdf_bytes,
                file_name="relatorio_conciliacao.pdf",
                mime="application/pdf",
                key="dl_pdf_tab0",
            )
    else:
        st.warning("PDF server-side indisponível: instale 'reportlab' (pip install -r requirements.txt).")
    # Excel export with multiple sheets
    try:
        import xlsxwriter  # noqa: F401
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_view.to_excel(writer, index=False, sheet_name="limpo")
            # Precompute standard groupings
            date_cols_x = [c for c in ["Pagto"] if c in df_view.columns]
            workbook = writer.book
            fmt_currency = workbook.add_format({"num_format": "R$ #,##0.00"})
            fmt_date = workbook.add_format({"num_format": "dd/mm/yyyy"})
            # Format date columns on limpo sheet
            ws_limpo = writer.sheets["limpo"]
            for col_name in df_view.columns:
                if str(df_view[col_name].dtype).startswith("datetime64"):
                    idx = df_view.columns.get_loc(col_name)
                    ws_limpo.set_column(idx, idx, None, fmt_date)
            for c in date_cols_x:
                g = group_totals(df_view, [c])
                sheet_name = f"por_{c[:28]}"
                g.to_excel(writer, index=False, sheet_name=sheet_name)
                if "total" in g.columns:
                    ws = writer.sheets[sheet_name]
                    col_idx = g.columns.get_loc("total")
                    ws.set_column(col_idx, col_idx, None, fmt_currency)
                # Date column formatting on grouped sheet
                if c in g.columns:
                    col_idx_date = g.columns.get_loc(c)
                    ws.set_column(col_idx_date, col_idx_date, None, fmt_date)
            if "CLASSE" in df_view.columns:
                g = group_totals(df_view, ["CLASSE"]) 
                g.to_excel(writer, index=False, sheet_name="por_CLASSE")
                if "total" in g.columns:
                    ws = writer.sheets["por_CLASSE"]
                    col_idx = g.columns.get_loc("total")
                    ws.set_column(col_idx, col_idx, None, fmt_currency)
            banco_col_default = detect_banco_column(df_view)
            if banco_col_default:
                g = group_totals(df_view, [banco_col_default])
                g.to_excel(writer, index=False, sheet_name="por_banco")
                if "total" in g.columns:
                    ws = writer.sheets["por_banco"]
                    col_idx = g.columns.get_loc("total")
                    ws.set_column(col_idx, col_idx, None, fmt_currency)
        st.download_button(
            "Baixar Excel (todas as abas)",
            data=buffer.getvalue(),
            file_name="odontotech_agrupado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.caption("Instale 'xlsxwriter' para exportar Excel com múltiplas abas.")

# Removed tabs for Por datas/Classe/Banco to simplify UI

## Tab removida: Por CLASSE

## Tab removida: Por banco

with tabs[1]:
    st.write("Monte seu agrupamento livremente.")
    render_date_filter_controls(df, ns="tab4")
    df_view, filter_summary = apply_date_filter(df)
    # Hide certain columns from grouping options
    hidden_cols = {"Histórico", "Historico", "CPF", "Fone1", "Fone2", "Fone3", "Fone4", "Celular", "Razão Social"}
    choices = [c for c in list(df_view.columns) if c not in hidden_cols]
    default_opts = [c for c in ["Pagto", "CLASSE"] if c in choices]
    by = st.multiselect("Agrupar por", options=choices, default=default_opts)
    if by:
        st.caption(f"Filtro: {filter_summary}")
        src = df_view
        # Filters based on selected grouping dimensions
        for dim in by:
            key_base = f"tab4_group_filter_{dim}".replace(" ", "_")
            if str(src[dim].dtype).startswith("datetime64"):
                opts = sorted(pd.to_datetime(src[dim]).dropna().dt.date.unique())
                sel = st.multiselect(
                    f"Filtrar {dim}", options=opts, format_func=lambda d: d.strftime("%d/%m/%Y"), key=key_base
                )
                if sel:
                    src = src[src[dim].dt.date.isin(sel)]
            else:
                opts = sorted([x for x in src[dim].dropna().unique().tolist()])
                sel = st.multiselect(f"Filtrar {dim}", options=opts, key=key_base)
                if sel:
                    src = src[src[dim].isin(sel)]

        g = group_totals(src, by) if not src.empty else pd.DataFrame()
        # Multi-level sorting controls
        if not g.empty:
            sort_options = list(g.columns)
            sort_default = [c for c in by if c in sort_options]
            sort_by = st.multiselect(
                "Classificar por (ordem de prioridade)",
                options=sort_options,
                default=sort_default,
                key="tab4_sort_by",
            )
            if sort_by:
                ascending = []
                for col in sort_by:
                    desc = st.checkbox(
                        f"Decrescente: {col}", value=False, key=f"tab4_sort_desc_{col}"
                    )
                    ascending.append(not desc)
                try:
                    g = g.sort_values(sort_by, ascending=ascending, kind="mergesort")
                except Exception:
                    g = g.sort_values(sort_by, kind="mergesort")
        g_disp = _format_total_column(_format_dates_for_display(g))
        st.dataframe(g_disp, use_container_width=True)
        _show_group_totals(g)
        st.download_button(
            "Baixar CSV – agrupamento livre",
            data=g_disp.to_csv(index=False).encode("utf-8-sig"),
            file_name="totais_agrupados.csv",
            mime="text/csv",
        )
        grouped_accounting_df = _build_grouped_accounting_export(g, by)
        grouped_accounting_csv = grouped_accounting_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "Baixar conciliação contábil (agrupado)",
            data=grouped_accounting_csv,
            file_name="conciliacao_contabil_agrupado.csv",
            mime="text/csv",
            disabled=grouped_accounting_df.empty,
        )
        if grouped_accounting_df.empty and "CLASSE" not in g.columns:
            st.caption("Inclua a coluna CLASSE no agrupamento para gerar a conciliação contábil agrupada.")
        # Analítico (lançamentos)
        st.markdown("#### Lançamentos filtrados (analítico)")
        accounting_df = _build_accounting_export(src)
        accounting_csv = accounting_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "Baixar conciliação contábil",
            data=accounting_csv,
            file_name="conciliacao_contabil.csv",
            mime="text/csv",
            disabled=accounting_df.empty,
        )
        if accounting_df.empty:
            st.caption("Nenhum registro elegível para conciliação contábil nos filtros atuais.")
        st.dataframe(_format_dates_for_display(src), use_container_width=True, height=360)
        _show_analytic_totals(src)

        # PDF only with the free grouping (relatório total do agrupamento livre)
        if REPORTLAB_AVAILABLE and st.button("Baixar PDF – agrupamento livre", key="pdf_tab4"):
            sections = [("Agrupamento livre", g)]
            # Per-group details following current grouping selection 'by'
            try:
                details = _detail_sections_from_summary(src if 'src' in locals() else df_view, g, by)
                sections.extend(details)
            except Exception:
                pass
            full_df = _select_full_columns(src if 'src' in locals() else df_view)
            sections.append(("Registros (colunas selecionadas)", full_df))
            summary = {
                "initial_rows": clean_stats.get("initial_rows"),
                "dropped_star_rows": clean_stats.get("dropped_star_rows"),
                "final_rows": (src if 'src' in locals() else df_view).shape[0],
                "total_valor": float((src if 'src' in locals() else df_view)["Valor"].sum()) if "Valor" in (src if 'src' in locals() else df_view).columns else 0.0,
            }
            pdf_bytes = _build_pdf("Relatório – Agrupamento livre", summary, filter_summary, sections)
            st.download_button(
                "Baixar PDF gerado",
                data=pdf_bytes,
                file_name="relatorio_agrupamento_livre.pdf",
                mime="application/pdf",
                key="dl_pdf_tab4",
            )
        elif not REPORTLAB_AVAILABLE:
            st.warning("PDF server-side indisponível: instale 'reportlab' (pip install -r requirements.txt).")
    else:
        st.info("Selecione ao menos uma coluna para agrupar.")

with tabs[2]:
    st.write("Compare os lançamentos do CSV limpo com um ou mais extratos OFX.")
    render_date_filter_controls(df, ns="tab_ofx")
    df_filtered, filter_summary = apply_date_filter(df)
    st.caption(f"Filtro: {filter_summary}")

    df_for_compare, bank_filter_summary = _render_bank_filter_controls(df_filtered, ns="tab_ofx")
    st.caption(f"Banco: {bank_filter_summary}")

    ofx_uploads = st.file_uploader(
        "Extrato bancário (OFX)",
        type=["ofx"],
        accept_multiple_files=True,
        key="ofx_files",
    )

    if not ofx_uploads:
        st.info("Envie ao menos um arquivo OFX para executar a comparação.")
    else:
        ofx_df, load_messages = _load_ofx_files(ofx_uploads)
        for msg in load_messages:
            st.warning(msg)

        if ofx_df.empty:
            st.error("Não encontramos lançamentos válidos nos arquivos OFX enviados.")
        else:
            st.markdown("#### Extrato OFX consolidado")
            st.dataframe(
                _format_dates_for_display(ofx_df),
                use_container_width=True,
                height=320,
            )

            if df_for_compare.empty:
                st.warning("Nenhum lançamento do CSV atende aos filtros atuais de data/banco. Ajuste a seleção para conciliar.")

            matches, odo_only, ofx_only = _match_transactions(df_for_compare, ofx_df)

            total_matches = _sum_column(matches, "Valor_odontotech")
            total_odo_only = _sum_column(odo_only, "Valor_odontotech")
            total_ofx_only = _sum_column(ofx_only, "Valor_ofx")

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Lançamentos casados", f"{matches.shape[0]}", _fmt_brl(total_matches))
            col_b.metric("Somente CSV", f"{odo_only.shape[0]}", _fmt_brl(total_odo_only))
            col_c.metric("Somente OFX", f"{ofx_only.shape[0]}", _fmt_brl(total_ofx_only))

            st.divider()

            if not matches.empty:
                st.markdown("#### Casamentos encontrados")
                match_cols = _select_existing(
                    matches,
                    [
                        "Pagto",
                        "Valor_odontotech",
                        "CLASSE",
                        "Forma de Pagamento",
                        "Nome Banco",
                        "Histórico",
                        "Historico",
                        "Valor_ofx",
                        "Data",
                        "Descrição",
                        "Documento",
                        "Identificador",
                        "Arquivo",
                        "Diferença",
                    ],
                )
                matches_display = matches[match_cols].copy()
                if "Histórico" in matches_display.columns and "Historico" in matches_display.columns:
                    matches_display.drop(columns=["Historico"], inplace=True)
                matches_display.rename(
                    columns={
                        "Valor_odontotech": "Valor (CSV)",
                        "Valor_ofx": "Valor (OFX)",
                        "Diferença": "Diferença (CSV-OFX)",
                    },
                    inplace=True,
                )
                st.dataframe(
                    _format_dates_for_display(matches_display),
                    use_container_width=True,
                    height=360,
                )
                st.download_button(
                    "Baixar casamentos (CSV)",
                    data=matches_display.to_csv(index=False).encode("utf-8-sig"),
                    file_name="casamentos_ofx.csv",
                    mime="text/csv",
                )
            else:
                st.caption("Nenhum casamento encontrado com as regras atuais (mesma data e valor).")

            if not odo_only.empty:
                st.markdown("#### Somente no CSV limpo")
                odo_cols = _select_existing(
                    odo_only,
                    [
                        "Pagto",
                        "Valor_odontotech",
                        "CLASSE",
                        "Forma de Pagamento",
                        "Nome Banco",
                        "Histórico",
                        "Historico",
                        "Doc.",
                    ],
                )
                odo_display = odo_only[odo_cols].copy()
                if "Histórico" in odo_display.columns and "Historico" in odo_display.columns:
                    odo_display.drop(columns=["Historico"], inplace=True)
                odo_display.rename(columns={"Valor_odontotech": "Valor (CSV)"}, inplace=True)
                st.dataframe(
                    _format_dates_for_display(odo_display),
                    use_container_width=True,
                    height=300,
                )
                st.download_button(
                    "Baixar somente CSV (CSV)",
                    data=odo_display.to_csv(index=False).encode("utf-8-sig"),
                    file_name="somente_csv.csv",
                    mime="text/csv",
                )
            else:
                st.caption("Nenhum lançamento exclusivo do CSV no período filtrado.")

            if not ofx_only.empty:
                st.markdown("#### Somente no OFX")
                ofx_cols = _select_existing(
                    ofx_only,
                    [
                        "Data",
                        "Valor_ofx",
                        "Tipo",
                        "Descrição",
                        "Documento",
                        "Identificador",
                        "Arquivo",
                        "Memo",
                    ],
                )
                ofx_display = ofx_only[ofx_cols].copy()
                ofx_display.rename(columns={"Valor_ofx": "Valor (OFX)"}, inplace=True)
                st.dataframe(
                    _format_dates_for_display(ofx_display),
                    use_container_width=True,
                    height=300,
                )
                st.download_button(
                    "Baixar somente OFX (CSV)",
                    data=ofx_display.to_csv(index=False).encode("utf-8-sig"),
                    file_name="somente_ofx.csv",
                    mime="text/csv",
                )
            else:
                st.caption("Nenhum lançamento exclusivo do OFX para o filtro atual.")
