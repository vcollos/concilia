from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd
import streamlit as st

from ofx_utils import read_ofx_transactions

ENCODING_CANDIDATES: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin1", "cp1252")
SUMMARY_COLUMNS: dict[str, Sequence[str]] = {
    "francesinha": ("Vlr. Cobrado",),
    "contas_pagar": ("Valor",),
    "contas_receber": ("Valor", "Valor PPCNG"),
    "ofx": ("Valor",),
    "csv": ("Valor", "Valor (R$)"),
}


@dataclass
class DataPreview:
    name: str
    kind: str
    df: pd.DataFrame


def _decode_bytes(data: bytes) -> str:
    for enc in ENCODING_CANDIDATES:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _convert_brl(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    s = series.astype(str).str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    s = s.str.replace("\xa0", "", regex=False)
    s = s.str.replace(r"\.(?=\d{3}(\D|$))", "", regex=True)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _strip_strings(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def _parse_dates(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df


def _strip_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def detect_kind(name: str, text: str) -> str:
    lower_name = name.lower()
    if lower_name.endswith(".ofx"):
        return "ofx"
    head = "\n".join(text.splitlines()[:20])
    if "<OFX" in head.upper():
        return "ofx"
    if "Relatório de Contas Pagas" in head:
        return "contas_pagar"
    if "Relatório Receber Recebido" in head:
        return "contas_receber"
    if "Sacado,,,Nosso Número" in head or head.startswith("Sacado,"):
        return "francesinha"
    return "csv"


def read_francesinha_from_text(text: str) -> pd.DataFrame:
    skip_prefixes = ("Ordenado por", "Gerado em", "Relatório", "Cedente", "Tipo Consulta", "Conta Corrente")
    skip_contains = ("Total de Valores", "Total de Registros", "Total Geral")
    rows: List[dict] = []
    header: Optional[List[str]] = None
    for raw in text.splitlines():
        line = raw.lstrip("\ufeff")
        stripped = line.strip()
        if not stripped:
            continue
        normalized = stripped.lstrip(",").strip()
        first_cell = normalized.split(",", 1)[0].strip()
        if any(first_cell.startswith(prefix) for prefix in skip_prefixes):
            continue
        if first_cell.endswith(":"):
            continue
        if any(token in normalized for token in skip_contains):
            continue
        if re.match(r"^\d{1,2}-", first_cell):
            continue
        parsed = next(csv.reader([line]))
        if parsed and parsed[0].strip().startswith("Sacado"):
            header = parsed
            continue
        if header is None:
            continue
        if len(parsed) < len(header):
            parsed += [""] * (len(header) - len(parsed))
        elif len(parsed) > len(header):
            parsed = parsed[: len(header)]
        row: dict[str, str] = {}
        for idx, col in enumerate(header):
            name = col.strip()
            if not name:
                continue
            value = parsed[idx].strip() if idx < len(parsed) else ""
            row[name] = value
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = _strip_object_columns(df)
    str_cols = ["Sacado", "Nosso Número", "Seu Número"]
    df = _strip_strings(df, [c for c in str_cols if c in df.columns])
    money_cols = [
        c
        for c in ["Valor (R$)", "Vlr. Mora", "Vlr. Desc.", "Vlr. Outros Acresc.", "Vlr. Baixado", "Vlr. Cobrado"]
        if c in df.columns
    ]
    for col in money_cols:
        df[col] = _convert_brl(df[col])
    date_cols = [
        c
        for c in ["Dt. Previsão Crédito", "Vencimento", "Dt. Limite Pgto", "Dt. Baixa", "Dt. Liquid."]
        if c in df.columns
    ]
    df = _parse_dates(df, date_cols)
    return df.reset_index(drop=True)


def read_contas_pagar_from_text(text: str) -> pd.DataFrame:
    output_lines: List[str] = []
    header_seen = False
    skip_prefixes = (
        "Relatório de Contas Pagas",
        "Período Inicial",
        "Período Final",
        "Com posição em",
    )
    for raw in text.splitlines():
        line = raw.lstrip("\ufeff")
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        if stripped.startswith("Codigo;Pagamento;Classe Financeira;"):
            if header_seen:
                continue
            header_seen = True
            output_lines.append(line)
            continue
        output_lines.append(line)
    cleaned = "\n".join(output_lines)
    if not cleaned:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(cleaned), sep=";", engine="python")
    df.columns = [col.strip() for col in df.columns]
    df = df.dropna(how="all")
    df = _strip_object_columns(df)
    money_cols = [
        c
        for c in [
            "Valor",
            "Valor PIS",
            "Valor COFINS",
            "Valor CSLL",
            "Valor IRRF",
            "Valor ISS",
            "Valor INSS",
        ]
        if c in df.columns
    ]
    for col in money_cols:
        df[col] = _convert_brl(df[col])
    date_cols = [c for c in ["Pagamento", "Emissao", "Vencimento", "Dt. Conciliação"] if c in df.columns]
    df = _parse_dates(df, date_cols)
    if "Parcela" in df.columns:
        df["Parcela"] = df["Parcela"].astype(str).str.strip("'").str.strip()
    return df.reset_index(drop=True)


DATE_RANGE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4} a \d{2}/\d{2}/\d{4};")


def read_contas_receber_from_text(text: str) -> pd.DataFrame:
    output_lines: List[str] = []
    header_seen = False
    for raw in text.splitlines():
        line = raw.lstrip("\ufeff")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Relatório Receber Recebido"):
            continue
        if DATE_RANGE_PATTERN.match(stripped):
            continue
        if stripped.startswith("Tipo: "):
            continue
        if stripped.startswith("** Subtotal"):
            continue
        if stripped.startswith("** Pagamento"):
            continue
        if stripped.startswith("Codigo Interno;"):
            if header_seen:
                continue
            header_seen = True
            output_lines.append(line)
            continue
        output_lines.append(line)
    cleaned = "\n".join(output_lines)
    if not cleaned:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(cleaned), sep=";", engine="python")
    df.columns = [col.strip() for col in df.columns]
    df = df.dropna(how="all")
    df = _strip_object_columns(df)
    money_cols = [
        c
        for c in [
            "Valor",
            "Valor PPCNG",
            "Valor PIS",
            "Valor COFINS",
            "Valor CSLL",
            "Valor IRRF",
            "Valor ISS",
            "Valor INSS",
        ]
        if c in df.columns
    ]
    for col in money_cols:
        df[col] = _convert_brl(df[col])
    date_cols = [
        c
        for c in ["Emissão", "Vencto", "Pagto", "Pagamento do Boleto"]
        if c in df.columns
    ]
    df = _parse_dates(df, date_cols)
    return df.reset_index(drop=True)


def load_dataset(name: str, data: bytes) -> DataPreview:
    text = _decode_bytes(data)
    kind = detect_kind(name, text)
    if kind == "ofx":
        df = read_ofx_transactions(io.BytesIO(data))
    elif kind == "francesinha":
        df = read_francesinha_from_text(text)
    elif kind == "contas_pagar":
        df = read_contas_pagar_from_text(text)
    elif kind == "contas_receber":
        df = read_contas_receber_from_text(text)
    else:
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
    return DataPreview(name=name, kind=kind, df=df)


@st.cache_data(show_spinner=False)
def cached_load_from_bytes(name: str, data: bytes) -> DataPreview:
    return load_dataset(name, data)


def _fmt_brl(value: float) -> str:
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def _monetary_totals(kind: str, df: pd.DataFrame) -> List[tuple[str, float]]:
    totals: List[tuple[str, float]] = []
    for col in SUMMARY_COLUMNS.get(kind, ()):  # type: ignore[arg-type]
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            totals.append((col, float(df[col].sum(skipna=True))))
    return totals


def _suggest_download_name(preview: DataPreview) -> str:
    stem = Path(preview.name).stem
    return f"{stem}_{preview.kind}.csv"


def _sanitize_key_fragment(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", text)


def _extract_first_timestamp(value) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    result = pd.to_datetime(value, errors="coerce")
    if isinstance(result, pd.Series):
        return result.iloc[0] if not result.empty else None
    if isinstance(result, (pd.DatetimeIndex, pd.Index)):
        return result[0] if len(result) else None
    return result if not pd.isna(result) else None


def _apply_dynamic_filters(
    df: pd.DataFrame,
    kind: str,
    key_prefix: str,
) -> tuple[pd.DataFrame, str]:
    if df.empty:
        return df, "Nenhum filtro aplicado"

    filterable: list[tuple[str, str]] = []
    for col in df.columns:
        if kind == "francesinha" and col == "Vlr. Baixado":
            continue
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            filterable.append((col, "datetime"))
        elif pd.api.types.is_numeric_dtype(series):
            filterable.append((col, "numeric"))
        else:
            unique_values = series.dropna().unique()
            if unique_values.size and unique_values.size <= 200:
                filterable.append((col, "categorical"))

    if not filterable:
        return df, "Nenhum filtro disponível"

    options = [col for col, _ in filterable]
    selected_cols = st.multiselect(
        "Adicionar filtros",
        options=options,
        key=f"{key_prefix}_selected_cols",
    )

    if not selected_cols:
        return df, "Nenhum filtro aplicado"

    info_map = {col: kind_name for col, kind_name in filterable}
    filtered_df = df.copy()
    summaries: list[str] = []

    for col in selected_cols:
        kind_name = info_map.get(col)
        if not kind_name:
            continue
        safe = _sanitize_key_fragment(col)
        col_key = f"{key_prefix}_{safe}"
        series_original = filtered_df[col]

        if kind_name == "datetime":
            series = pd.to_datetime(series_original, errors="coerce")
            valid = series.dropna()
            if valid.empty:
                st.caption(f"Coluna {col}: sem datas válidas para filtrar.")
                continue
            min_dt = valid.min()
            max_dt = valid.max()
            default_range = (
                min_dt.date() if pd.notna(min_dt) else None,
                max_dt.date() if pd.notna(max_dt) else None,
            )
            chosen = st.date_input(
                f"Intervalo para {col}",
                value=default_range,
                key=f"{col_key}_date_range",
            )
            include_nulls = st.checkbox(
                f"Incluir vazios em {col}",
                value=True,
                key=f"{col_key}_include_nulls",
            )

            if isinstance(chosen, (list, tuple)) and len(chosen) == 2:
                start_candidate, end_candidate = chosen
            else:
                start_candidate = chosen
                end_candidate = chosen

            start = _extract_first_timestamp(start_candidate)
            end = _extract_first_timestamp(end_candidate)

            if start and end:
                display_start = start.strftime("%d/%m/%Y")
                display_end = end.strftime("%d/%m/%Y")
                end = end + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                mask = (series >= start) & (series <= end)
                if include_nulls:
                    mask = mask | series.isna()
                filtered_df = filtered_df.loc[mask].copy()
                summary = f"{col}: {display_start} → {display_end}"
                if include_nulls:
                    summary += " (inclui vazios)"
                summaries.append(summary)
            elif not include_nulls:
                filtered_df = filtered_df.loc[series.notna()].copy()
                summaries.append(f"{col}: excluindo vazios")

        elif kind_name == "numeric":
            numeric_series = pd.to_numeric(series_original, errors="coerce")
            valid = numeric_series.dropna()
            if valid.empty:
                st.caption(f"Coluna {col}: sem valores numéricos válidos para filtrar.")
                continue
            min_val = float(valid.min())
            max_val = float(valid.max())
            if math.isclose(min_val, max_val):
                st.caption(f"Coluna {col}: valor único {min_val:.2f}.")
                continue
            step = max((max_val - min_val) / 50.0, 0.01)
            selected_min, selected_max = st.slider(
                f"Faixa de {col}",
                min_value=float(min_val),
                max_value=float(max_val),
                value=(float(min_val), float(max_val)),
                step=step,
                key=f"{col_key}_range",
            )
            include_nulls = st.checkbox(
                f"Incluir vazios em {col}",
                value=True,
                key=f"{col_key}_include_nulls",
            )
            mask = numeric_series.between(selected_min, selected_max)
            if include_nulls:
                mask = mask | numeric_series.isna()
            filtered_df = filtered_df.loc[mask].copy()
            summary = f"{col}: {selected_min:.2f} – {selected_max:.2f}"
            if include_nulls:
                summary += " (inclui vazios)"
            summaries.append(summary)

        elif kind_name == "categorical":
            options = sorted(
                [v for v in series_original.dropna().unique().tolist()],
                key=lambda x: str(x).lower(),
            )
            if not options:
                continue
            selected_values = st.multiselect(
                f"Valores para {col}",
                options=options,
                key=f"{col_key}_values",
            )
            include_nulls = st.checkbox(
                f"Incluir vazios em {col}",
                value=True,
                key=f"{col_key}_include_nulls",
            )
            if selected_values:
                mask = series_original.isin(selected_values)
                if include_nulls:
                    mask = mask | series_original.isna()
                filtered_df = filtered_df.loc[mask].copy()
                summary = f"{col}: {', '.join(str(v) for v in selected_values)}"
                if include_nulls:
                    summary += " (inclui vazios)"
                summaries.append(summary)
            elif not include_nulls:
                filtered_df = filtered_df.loc[series_original.notna()].copy()
                summaries.append(f"{col}: excluindo vazios")

    summary_text = "; ".join(summaries) if summaries else "Nenhum filtro aplicado"
    return filtered_df, summary_text


def render_preview(display_name: str, preview: DataPreview, rows_to_show: int) -> None:
    st.subheader(f"{display_name} · {preview.kind}")
    df = preview.df
    if df.empty:
        st.warning("Dataset sem linhas úteis após limpeza.")
        return
    st.caption(f"Linhas originais: {df.shape[0]} • Colunas: {df.shape[1]}")

    key_prefix = _sanitize_key_fragment(f"{display_name}_{preview.kind}")
    filtered_df, filter_summary = _apply_dynamic_filters(df, preview.kind, key_prefix)
    st.caption(f"Após filtros: {filtered_df.shape[0]} linhas • {filter_summary}")

    totals = _monetary_totals(preview.kind, filtered_df)
    if totals:
        cols = st.columns(len(totals))
        for col_widget, (label, total) in zip(cols, totals):
            col_widget.metric(label, _fmt_brl(total))
    display_df = filtered_df.copy()
    table_height = max(320, min(900, 42 + rows_to_show * 28))

    if preview.kind == "francesinha":
        if "Vlr. Baixado" in display_df.columns:
            display_df = display_df.drop(columns=["Vlr. Baixado"]).copy()

        credit_col = "Dt. Previsão Crédito"
        if credit_col in display_df.columns and "Vlr. Cobrado" in display_df.columns:
            credit_series = pd.to_datetime(display_df[credit_col], errors="coerce")
            available_dates = sorted({d.date() for d in credit_series.dropna()})
            if available_dates:
                label_map = {d.strftime("%d/%m/%Y"): d for d in available_dates}
                selected_labels = st.multiselect(
                    "Filtrar por previsão de crédito",
                    options=list(label_map.keys()),
                )
                if selected_labels:
                    selected_dates = {label_map[label] for label in selected_labels}
                    mask = credit_series.dt.date.isin(selected_dates)
                    display_df = display_df.loc[mask].copy()
                credit_series = pd.to_datetime(display_df[credit_col], errors="coerce")

                show_group = st.checkbox(
                    "Mostrar totais agrupados por previsão de crédito", value=False
                )
                if show_group:
                    grouped = (
                        pd.DataFrame({
                            credit_col: credit_series.dt.date,
                            "Vlr. Cobrado": display_df["Vlr. Cobrado"],
                        })
                        .dropna(subset=[credit_col])
                        .groupby(credit_col, as_index=False)
                        .agg(
                            Quantidade=("Vlr. Cobrado", "count"),
                            Total_Cobrado=("Vlr. Cobrado", "sum"),
                        )
                    )
                    grouped[credit_col] = grouped[credit_col].apply(
                        lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else ""
                    )
                    grouped["Total_Cobrado"] = grouped["Total_Cobrado"].round(2)
                    st.markdown("#### Totais por previsão de crédito")
                    st.dataframe(grouped, use_container_width=True)

            if credit_col in display_df.columns:
                credit_series = pd.to_datetime(display_df[credit_col], errors="coerce")
                display_df[credit_col] = credit_series.dt.strftime("%d/%m/%Y")

    st.dataframe(display_df, use_container_width=True, height=table_height)
    csv_data = filtered_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Baixar CSV limpo",
        data=csv_data,
        file_name=_suggest_download_name(preview),
        mime="text/csv",
    )


def _list_sample_files(base: Path) -> List[Path]:
    if not base.exists():
        return []
    patterns = ("*.csv", "*.CSV", "*.ofx", "*.OFX")
    files: set[Path] = set()
    for pattern in patterns:
        files.update(p for p in base.rglob(pattern) if p.is_file())
    return sorted(files)


def main() -> None:
    st.set_page_config(page_title="Conciliação financeira", layout="wide")
    st.title("Conciliação financeira – visualização dos dados")
    st.caption(
        "Carregue arquivos OFX/CSV do banco, francesinhas ou relatórios de contas para ver os dados limpos."
    )

    st.sidebar.header("Fontes de dados")
    rows_to_show = st.sidebar.slider(
        "Altura da tabela (linhas)", min_value=5, max_value=60, value=20, step=5
    )
    uploaded_files = st.sidebar.file_uploader(
        "Carregar arquivos (OFX ou CSV)",
        type=["csv", "CSV", "ofx", "OFX", "txt", "TXT"],
        accept_multiple_files=True,
    )

    sources: List[dict[str, str | bytes]] = []
    if uploaded_files:
        for file in uploaded_files:
            data = file.getvalue()
            if not data:
                continue
            sources.append(
                {
                    "name": file.name,
                    "display": f"{file.name} (upload)",
                    "data": data,
                }
            )

    sample_dir = Path("arquivos")
    sample_paths = _list_sample_files(sample_dir)
    if sample_paths:
        sample_labels: List[str] = []
        for path in sample_paths:
            try:
                label = str(path.relative_to(sample_dir))
            except ValueError:
                label = str(path)
            sample_labels.append(label)
        label_to_path = dict(zip(sample_labels, sample_paths))
        selected_labels = st.sidebar.multiselect("Arquivos de exemplo", sample_labels)
        for label in selected_labels:
            path = label_to_path[label]
            data = path.read_bytes()
            sources.append(
                {
                    "name": path.name,
                    "display": f"{label} (exemplo)",
                    "data": data,
                }
            )
    else:
        st.sidebar.info("Pasta 'arquivos' não encontrada ou sem arquivos *.csv/*.ofx.")

    if not sources:
        st.info("Selecione ou carregue pelo menos um arquivo para visualizar os dados.")
        return

    previews: List[tuple[str, DataPreview]] = []
    errors: List[tuple[str, str]] = []
    for source in sources:
        name = str(source["name"])
        display = str(source["display"])
        data_bytes = source["data"]
        assert isinstance(data_bytes, (bytes, bytearray))
        try:
            preview = cached_load_from_bytes(name, bytes(data_bytes))
        except Exception as exc:  # noqa: BLE001
            errors.append((display, str(exc)))
            continue
        previews.append((display, preview))

    for display, message in errors:
        st.error(f"Falha ao processar {display}: {message}")

    if not previews:
        st.warning("Não foi possível processar nenhum dos arquivos selecionados.")
        return

    if len(previews) == 1:
        display, preview = previews[0]
        render_preview(display, preview, rows_to_show)
        return

    tab_labels = [f"{display} · {preview.kind}" for display, preview in previews]
    tabs = st.tabs(tab_labels)
    for tab, (display, preview) in zip(tabs, previews):
        with tab:
            render_preview(display, preview, rows_to_show)


if __name__ == "__main__":
    main()
