"""Tulis hasil deteksi ke workbook Excel untuk review auditor."""

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .config import RULES
from .detector import DetectionResult, summarize

_BASE_COLS = [
    "transaction_id", "transaction_datetime", "store_name", "store_city", "geo_area", "channel",
    "cashier_id", "member_id", "member_tier_master", "item_code", "item_category",
    "item_tier_requirement", "qty", "net_amount_idr", "payment_type", "card_last4",
    "issuing_bank", "transaction_status",
]


def _cols(df: pd.DataFrame, cols) -> list:
    return [c for c in cols if c in df.columns]


def write_report(result: DetectionResult, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    codes = list(RULES)
    flag_cols = [col for col, _ in RULES.values()]

    anomalies = result.anomalies
    anomaly_view = anomalies[_cols(anomalies, _BASE_COLS + ["anomaly_count", "triggered_rules", "evidence_summary"])]
    all_view = result.transactions[
        _cols(result.transactions, _BASE_COLS + ["evaluated"] + flag_cols + ["anomaly_count", "triggered_rules"]
              + [f"evidence_{c}" for c in codes])
    ]
    dq_view = result.data_quality[
        _cols(result.data_quality, ["transaction_id", "transaction_datetime", "store_name", "member_id",
                                    "qty", "unit_price_idr", "discount_pct", "net_amount_idr",
                                    "transaction_status", "exclusion_reason"])
    ]
    params = pd.DataFrame(
        [{"parameter": k, "nilai": str(v)} for k, v in asdict(result.config).items()]
    )

    sheets = {
        "Ringkasan": summarize(result),
        "Transaksi_Anomali": anomaly_view,
        "Member_Kontak_Duplikat": result.duplicate_members,
        "Data_Quality": dq_view,
        "Semua_Transaksi": all_view,
        "Parameter": params,
    }
    with pd.ExcelWriter(path, engine="openpyxl", datetime_format="dd/mm/yyyy hh:mm") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_cells in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells[:200])
                ws.column_dimensions[col_cells[0].column_letter].width = min(max(10, width + 2), 60)
            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True)
    return path
