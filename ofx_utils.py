from __future__ import annotations

import datetime as _dt
from typing import List, Tuple

import pandas as pd


def _read_bytes(file_like) -> bytes:
    """Return raw bytes from several file-like inputs, rewinding when possible."""
    if hasattr(file_like, "getvalue"):
        return file_like.getvalue()
    if hasattr(file_like, "read"):
        try:
            if hasattr(file_like, "seek"):
                file_like.seek(0)
            data = file_like.read()
            return data if isinstance(data, (bytes, bytearray)) else bytes(str(data), "utf-8")
        finally:
            try:
                if hasattr(file_like, "seek"):
                    file_like.seek(0)
            except Exception:
                pass
    if isinstance(file_like, (bytes, bytearray)):
        return bytes(file_like)
    with open(file_like, "rb") as fh:
        return fh.read()


def _decode_text(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _strip_trailing_tag(value: str) -> str:
    if "<" in value:
        return value.split("<", 1)[0].strip()
    return value.strip()


def _parse_stmttrn_blocks(text: str) -> List[dict]:
    records: List[dict] = []
    current: dict | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tag = line.upper()
        if tag.startswith("<STMTTRN>"):
            current = {}
            continue
        if tag.startswith("</STMTTRN>"):
            if current:
                records.append(current)
            current = None
            continue
        if current is None:
            continue
        if not line.startswith("<") or ">" not in line:
            continue
        parts = line[1:].split(">", 1)
        if len(parts) != 2:
            continue
        name, value = parts
        name = name.strip().upper()
        value = _strip_trailing_tag(value)
        current[name] = value
    if current:
        records.append(current)
    return records


def _parse_ofx_date(value: str | None) -> pd.Timestamp:
    if not value:
        return pd.NaT
    cleaned = value.strip()
    if not cleaned:
        return pd.NaT
    cleaned = cleaned.split("[")[0].strip()
    base = cleaned.replace("T", "")
    digits = "".join(ch for ch in base if ch.isdigit())
    candidates: List[Tuple[int, str]] = [
        (14, "%Y%m%d%H%M%S"),
        (12, "%Y%m%d%H%M"),
        (8, "%Y%m%d"),
    ]
    for length, fmt in candidates:
        if len(digits) >= length:
            try:
                dt = _dt.datetime.strptime(digits[:length], fmt)
                return pd.Timestamp(dt)
            except ValueError:
                continue
    return pd.to_datetime(cleaned, errors="coerce")


def _parse_amount(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = text.strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def read_ofx_transactions(file_like) -> pd.DataFrame:
    """Read an OFX file (or file-like) into a normalized DataFrame."""
    content = _read_bytes(file_like)
    text = _decode_text(content)
    raw_records = _parse_stmttrn_blocks(text)
    rows: List[dict] = []
    for rec in raw_records:
        posted = _parse_ofx_date(rec.get("DTPOSTED") or rec.get("DTUSER"))
        amount = _parse_amount(rec.get("TRNAMT"))
        memo = rec.get("MEMO") or ""
        name = rec.get("NAME") or ""
        descricao = name.strip() or memo.strip() or None
        rows.append(
            {
                "Data": posted,
                "Valor": amount,
                "Tipo": (rec.get("TRNTYPE") or "").strip().upper() or None,
                "Descrição": descricao,
                "Documento": (rec.get("CHECKNUM") or rec.get("REFNUM") or "").strip() or None,
                "Identificador": (rec.get("FITID") or rec.get("REFNUM") or "").strip() or None,
                "Memo": memo.strip() or None,
                "Nome": name.strip() or None,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    if "Valor" in df.columns:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    df = df.sort_values([c for c in ["Data", "Identificador"] if c in df.columns]).reset_index(drop=True)
    return df
