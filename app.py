import io
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
    for sec_title, sec_df in sections:
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
        story.extend(_df_to_table_flowable(sec_df_fmt, sec_title, col_widths=col_widths))
        # Page break after very large sections might be added automatically by flowables

    doc.build(story)
    return buf.getvalue()


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
    enabled = st.checkbox("Filtrar por Pagto", value=enabled, key=f"{ns}_flt_enabled")
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

st.subheader("Resumo do processamento")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Linhas originais", f"{clean_stats['initial_rows']}")
col2.metric("Linhas removidas (*)", f"{clean_stats['dropped_star_rows']}")
col3.metric("Linhas finais", f"{clean_stats['final_rows']}")
total_valor = df["Valor"].sum() if "Valor" in df.columns else 0.0
col4.metric("Total Valor", f"R$ {total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))


st.divider()

tabs = st.tabs(["Dados limpos", "Por datas", "Por CLASSE", "Por banco", "Agrupar livre"]) 

with tabs[0]:
    st.write("Pré-visualização dos dados limpos:")
    render_date_filter_controls(df, ns="tab0")
    df_view, filter_summary = apply_date_filter(df)
    st.caption(f"Filtro: {filter_summary}")
    st.dataframe(df_view, use_container_width=True, height=450)

    # Download cleaned file
    csv_clean = df_view.to_csv(index=False).encode("utf-8-sig")
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
            for c in date_cols_x:
                g = group_totals(df_view, [c])
                sheet_name = f"por_{c[:28]}"
                g.to_excel(writer, index=False, sheet_name=sheet_name)
                if "total" in g.columns:
                    ws = writer.sheets[sheet_name]
                    col_idx = g.columns.get_loc("total")
                    ws.set_column(col_idx, col_idx, None, fmt_currency)
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

with tabs[1]:
    st.write("Totais por data de pagamento (soma de Valor e quantidade):")
    render_date_filter_controls(df, ns="tab1")
    df_view, filter_summary = apply_date_filter(df)
    st.caption(f"Filtro: {filter_summary}")
    
    date_cols: List[str] = [c for c in ["Pagto"] if c in df_view.columns]
    if not date_cols:
        st.warning("Coluna de data 'Pagto' não encontrada.")
    else:
        c = "Pagto"
        st.markdown(f"#### {c}")
        # Optional filter by grouped value(s)
        unique_dates = sorted(pd.to_datetime(df_view[c]).dropna().dt.date.unique())
        sel_dates = st.multiselect(
            "Filtrar datas de pagamento",
            options=unique_dates,
            format_func=lambda d: d.strftime("%d/%m/%Y"),
            key="flt_group_pagto_values",
        )
        df_group_src = df_view
        if sel_dates:
            mask_dates = df_group_src[c].dt.date.isin(sel_dates)
            df_group_src = df_group_src.loc[mask_dates]
        g = group_totals(df_group_src, [c]) if not df_group_src.empty else pd.DataFrame()
        g_disp = _format_total_column(g)
        st.dataframe(g_disp, use_container_width=True)
        st.download_button(
            f"Baixar CSV – {c}",
            data=g_disp.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"totais_por_{c.replace(' ', '_')}.csv",
            mime="text/csv",
            key=f"download_{c}",
        )
        # Full report button
        if REPORTLAB_AVAILABLE and st.button("Baixar PDF – relatório", key="pdf_tab1"):
            sections = []
            sections.extend(_summary_tables(df_view))
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
                key="dl_pdf_tab1",
            )
        elif not REPORTLAB_AVAILABLE:
            st.warning("PDF server-side indisponível: instale 'reportlab' (pip install -r requirements.txt).")

with tabs[2]:
    render_date_filter_controls(df, ns="tab2")
    df_view, filter_summary = apply_date_filter(df)
    if "CLASSE" not in df_view.columns:
        st.warning("Coluna 'CLASSE' não encontrada.")
    else:
        st.caption(f"Filtro: {filter_summary}")
        # Filter by selected classes (optional)
        classes = sorted([x for x in df_view["CLASSE"].dropna().unique().tolist()])
        sel_classes = st.multiselect(
            "Filtrar classes",
            options=classes,
            key="flt_group_classe_values",
        )
        src = df_view
        if sel_classes:
            src = src[src["CLASSE"].isin(sel_classes)]
        g = group_totals(src, ["CLASSE"]) if not src.empty else pd.DataFrame()
        g_disp = _format_total_column(g)
        st.dataframe(g_disp, use_container_width=True)
        st.download_button(
            "Baixar CSV – por CLASSE",
            data=g_disp.to_csv(index=False).encode("utf-8-sig"),
            file_name="totais_por_CLASSE.csv",
            mime="text/csv",
        )
        
        if REPORTLAB_AVAILABLE and st.button("Baixar PDF – relatório", key="pdf_tab2"):
            sections = []
            sections.extend(_summary_tables(df_view))
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
                key="dl_pdf_tab2",
            )
        elif not REPORTLAB_AVAILABLE:
            st.warning("PDF server-side indisponível: instale 'reportlab' (pip install -r requirements.txt).")

with tabs[3]:
    render_date_filter_controls(df, ns="tab3")
    df_view, filter_summary = apply_date_filter(df)
    banco_col_default = detect_banco_column(df_view)
    if not banco_col_default:
        st.warning("Colunas de banco não encontradas (Nome Banco, NºBanco, ID Banco, ID Conta Corrente).")
    else:
        banco_col = st.selectbox(
            "Coluna de banco para agrupar",
            options=[c for c in ["Nome Banco", "NºBanco", "ID Banco", "ID Conta Corrente"] if c in df_view.columns],
            index=[c for c in ["Nome Banco", "NºBanco", "ID Banco", "ID Conta Corrente"] if c in df_view.columns].index(banco_col_default),
        )
        st.caption(f"Filtro: {filter_summary}")
        # Optional filter by bank values
        bank_values = sorted([x for x in df_view[banco_col].dropna().unique().tolist()])
        sel_banks = st.multiselect(
            f"Filtrar {banco_col}",
            options=bank_values,
            key="flt_group_banco_values",
        )
        src = df_view
        if sel_banks:
            src = src[src[banco_col].isin(sel_banks)]
        g = group_totals(src, [banco_col]) if not src.empty else pd.DataFrame()
        g_disp = _format_total_column(g)
        st.dataframe(g_disp, use_container_width=True)
        st.download_button(
            f"Baixar CSV – por {banco_col}",
            data=g_disp.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"totais_por_{banco_col.replace(' ', '_')}.csv",
            mime="text/csv",
        )
        
        if REPORTLAB_AVAILABLE and st.button("Baixar PDF – relatório", key="pdf_tab3"):
            sections = []
            sections.extend(_summary_tables(df_view))
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
                key="dl_pdf_tab3",
            )
        elif not REPORTLAB_AVAILABLE:
            st.warning("PDF server-side indisponível: instale 'reportlab' (pip install -r requirements.txt).")

with tabs[4]:
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
        g = group_totals(df_view, by) if not df_view.empty else pd.DataFrame()
        g_disp = _format_total_column(g)
        st.dataframe(g_disp, use_container_width=True)
        st.download_button(
            "Baixar CSV – agrupamento livre",
            data=g_disp.to_csv(index=False).encode("utf-8-sig"),
            file_name="totais_agrupados.csv",
            mime="text/csv",
        )
        
        # PDF only with the free grouping (relatório total do agrupamento livre)
        if REPORTLAB_AVAILABLE and st.button("Baixar PDF – agrupamento livre", key="pdf_tab4"):
            sections = [("Agrupamento livre", g)]
            summary = {
                "initial_rows": clean_stats.get("initial_rows"),
                "dropped_star_rows": clean_stats.get("dropped_star_rows"),
                "final_rows": df_view.shape[0],
                "total_valor": float(df_view["Valor"].sum()) if "Valor" in df_view.columns else 0.0,
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
