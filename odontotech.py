from __future__ import annotations

import io
import re
import unicodedata
from typing import Iterable, Optional, Tuple

import pandas as pd


CANONICAL_COLUMNS = {
    "codigo interno": "Codigo Interno",
    "emissao": "Emissão",
    "emissão": "Emissão",
    "vencto": "Vencto",
    "pagto": "Pagto",
    "doc": "Doc.",
    "historico": "Historico",
    "histórico": "Historico",
    "valor": "Valor",
    "classe": "CLASSE",
    "parc": "Parc.",
    "orcamento": "Orçamento.",
    "orçamento": "Orçamento.",
    "fat ant": "Fat. Ant.",
    "gerar rps": "Gerar RPS",
    "nome plano": "Nome Plano",
    "adm benef": "ADM.Benef.",
    "valor ppcng": "Valor PPCNG",
    "vo tid": "VO TID",
    "vindi tid": "VINDI TID",
    "forma de pagamento": "Forma de Pagamento",
    "id banco": "ID Banco",
    "n banco": "NºBanco",
    "no banco": "NºBanco",
    "nºbanco": "NºBanco",
    "nome banco": "Nome Banco",
    "id conta corrente": "ID Conta Corrente",
    "historico_2": "Histórico",
    "cpf": "CPF",
    "fone1": "Fone1",
    "fone2": "Fone2",
    "fone3": "Fone3",
    "fone4": "Fone4",
    "celular": "Celular",
    "razao social": "Razão Social",
    "razão social": "Razão Social",
}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _normalize_key(text: str) -> str:
    # Lowercase, strip accents, collapse spaces and punctuation
    t = _strip_accents(text).lower().strip()
    t = re.sub(r"[\s\._\-\/]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    seen_targets = set()
    for col in df.columns:
        key = _normalize_key(str(col))
        target = CANONICAL_COLUMNS.get(key, None)
        if not target:
            # handle special case: sometimes there are two historico columns; disambiguate
            if key == "historico" and "Historico" in seen_targets:
                target = "Histórico"
            else:
                # Keep as-is but strip spaces
                target = str(col).strip()
        # Ensure we don't overwrite duplicate canonical names
        if target in mapping.values():
            # Append suffix to avoid collision
            suffix = 2
            base = target
            while f"{base}_{suffix}" in mapping.values():
                suffix += 1
            target = f"{base}_{suffix}"
        mapping[col] = target
        seen_targets.add(target)
    return df.rename(columns=mapping)


def _to_brazil_float(series: pd.Series) -> pd.Series:
    # Convert Brazilian formatted numbers like 1.234,56 into float 1234.56
    # Keep NaNs
    if series.dtype.kind in ("f", "i"):  # already numeric
        return series.astype(float)
    s = series.astype(str).str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    # remove anything that's not digit, comma, dot, or minus
    s = s.str.replace(r"[^0-9,\.-]", "", regex=True)
    # if there are both . and , assume . is thousands and , is decimal
    s = s.str.replace(r"\.(?=\d{3}(\D|$))", "", regex=True)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _parse_dates(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df


def _drop_star_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    if df.empty:
        return df, 0
    first_col = df.columns[0]
    mask = df[first_col].astype(str).str.strip().str.startswith("*")
    dropped = int(mask.sum())
    if dropped:
        df = df.loc[~mask].copy()
    return df, dropped


def read_odontotech_csv(file_like) -> Tuple[pd.DataFrame, dict]:
    """
    Read the Odontotech CSV, skipping the first 3 header lines.
    Tries common encodings and flexible separators, returning a raw DataFrame and basic stats.
    """
    stats = {
        "encoding": None,
        "sep": None,
        "skipped_header_lines": 3,
    }

    content = None
    if hasattr(file_like, "read"):
        # It's a file-like from Streamlit uploader
        raw = file_like.read()
        if isinstance(raw, str):
            content = raw.encode("utf-8", errors="ignore")
        else:
            content = raw
    elif isinstance(file_like, (bytes, bytearray)):
        content = bytes(file_like)
    else:
        # assume it is a path-like
        with open(file_like, "rb") as f:
            content = f.read()

    for enc in ("utf-8-sig", "utf-8", "latin1", "cp1252"):
        try:
            buf = io.StringIO(content.decode(enc, errors="strict"))
            df = pd.read_csv(buf, skiprows=3, sep=None, engine="python")
            stats["encoding"] = enc
            stats["sep"] = getattr(df.attrs, "sep", None)  # may not be present
            break
        except Exception:
            df = None
            continue

    if df is None:
        # Last resort: decode best-effort and try semicolon/tab/comma
        buf_text = content.decode("utf-8", errors="ignore")
        for sep in (";", "\t", ","):
            try:
                df = pd.read_csv(io.StringIO(buf_text), skiprows=3, sep=sep, engine="python")
                stats["encoding"] = "utf-8?"
                stats["sep"] = sep
                break
            except Exception:
                continue
    if df is None:
        raise ValueError("Não foi possível ler o CSV. Verifique o arquivo.")

    # Drop completely empty columns and rows
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    return df, stats


def clean_odontotech_df(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Apply Odontotech-specific cleaning:
    - Canonicalize column names
    - Drop rows starting with '*'
    - Parse dates (Emissão, Vencto, Pagto)
    - Parse Valor as float
    - Trim strings
    Returns the cleaned DataFrame and cleaning stats.
    """
    stats = {
        "dropped_star_rows": 0,
        "initial_rows": int(df_raw.shape[0]),
        "final_rows": None,
        "parsed_dates": [],
        "parsed_valor": False,
    }

    df = df_raw.copy()

    # Standardize columns
    df = canonicalize_columns(df)

    # Drop star-prefixed rows
    df, dropped = _drop_star_rows(df)
    stats["dropped_star_rows"] = dropped

    # Trim strings
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()

    # Parse dates
    date_cols = [c for c in ("Emissão", "Vencto", "Pagto") if c in df.columns]
    df = _parse_dates(df, date_cols)
    stats["parsed_dates"] = date_cols

    # Parse Valor
    if "Valor" in df.columns:
        df["Valor"] = _to_brazil_float(df["Valor"]).fillna(0.0)
        stats["parsed_valor"] = True

    stats["final_rows"] = int(df.shape[0])
    return df, stats


def group_totals(
    df: pd.DataFrame,
    by: Iterable[str],
    value_col: str = "Valor",
) -> pd.DataFrame:
    """Group by given columns and compute count and sum of Valor."""
    cols = [c for c in by if c in df.columns]
    if not cols:
        raise ValueError("Nenhuma coluna válida para agrupamento.")
    agg = (
        df.groupby(cols, dropna=False)
        .agg(qtd=(value_col, "size"), total=(value_col, "sum"))
        .reset_index()
        .sort_values(cols)
    )
    return agg


def detect_banco_column(df: pd.DataFrame) -> Optional[str]:
    """Choose the most appropriate bank column available."""
    candidates = ["Nome Banco", "NºBanco", "ID Banco", "ID Conta Corrente"]
    for c in candidates:
        if c in df.columns:
            return c
    return None

