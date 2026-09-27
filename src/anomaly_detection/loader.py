"""Baca dan normalisasi data transaksi serta master member."""

from pathlib import Path

import pandas as pd

from .config import GUEST_ID

_BOOL_MAP = {"TRUE": True, "FALSE": False, "1": True, "0": False, "YES": True, "NO": False}


def _to_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.upper().map(_BOOL_MAP).fillna(False).astype(bool)


def _clean_str(series: pd.Series, upper: bool = False) -> pd.Series:
    out = series.astype("string").str.strip()
    out = out.mask(out == "", pd.NA)
    return out.str.upper() if upper else out


def _read_table(path: Path, sheet_name=0) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path)


def load_transactions(path) -> pd.DataFrame:
    df = _read_table(path)
    # Ekspor Google Sheets sering membawa kolom kosong tanpa header.
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    return normalize_transactions(df)


def normalize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["transaction_id"] = _clean_str(df["transaction_id"])
    df = df[df["transaction_id"].notna()].reset_index(drop=True)

    for col in ["member_id", "store_name", "store_city", "geo_area", "card_last4"]:
        if col in df:
            df[col] = _clean_str(df[col])
    for col in ["member_tier", "item_tier_requirement", "channel", "issuing_bank", "transaction_status"]:
        if col in df:
            df[col] = _clean_str(df[col], upper=True)

    df["member_id"] = df["member_id"].fillna(GUEST_ID)
    df["transaction_datetime"] = pd.to_datetime(
        df["transaction_datetime"], format="mixed", errors="coerce"
    )
    if "transaction_hour" in df:
        df["transaction_hour"] = pd.to_numeric(df["transaction_hour"], errors="coerce")
        df["transaction_hour"] = df["transaction_hour"].fillna(df["transaction_datetime"].dt.hour)
    else:
        df["transaction_hour"] = df["transaction_datetime"].dt.hour
    for col in ["qty", "net_amount_idr", "gross_amount_idr", "unit_price_idr"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["is_card_payment", "is_valid_record", "is_member"]:
        if col in df:
            df[col] = _to_bool(df[col])
    if "is_valid_record" not in df:
        df["is_valid_record"] = True
    return df


def load_members(path, sheet_name=0) -> pd.DataFrame:
    return normalize_members(_read_table(path, sheet_name=sheet_name))


def normalize_phone(value) -> str:
    """Samakan format telepon: hanya digit, tanpa awalan 62/0. '0812-345' == '62812345' == '812345'."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if isinstance(value, float) and str(value).endswith(".0"):
        digits = digits[:-1]
    if digits.startswith("62"):
        digits = digits[2:]
    return digits.lstrip("0")


def normalize_members(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["member_id"] = _clean_str(df["member_id"])
    df = df[df["member_id"].notna()].drop_duplicates("member_id").reset_index(drop=True)
    df["member_tier"] = _clean_str(df["member_tier"], upper=True)
    df["phone_norm"] = df["phone_number"].map(normalize_phone) if "phone_number" in df else ""
    df["email_norm"] = (
        _clean_str(df["email"]).str.lower().fillna("") if "email" in df else ""
    )
    return df
