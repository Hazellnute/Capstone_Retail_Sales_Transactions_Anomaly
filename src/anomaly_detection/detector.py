"""Orkestrasi deteksi: scope data, jalankan R1-R6, gabungkan hasil."""

from dataclasses import dataclass

import pandas as pd

from . import rules
from .config import RULES, RuleConfig


@dataclass
class DetectionResult:
    transactions: pd.DataFrame  # semua transaksi + flag, evidence, anomaly_count
    duplicate_members: pd.DataFrame  # detail R6 per member
    data_quality: pd.DataFrame  # record yang tidak dievaluasi + alasannya
    config: RuleConfig

    @property
    def anomalies(self) -> pd.DataFrame:
        tx = self.transactions
        return tx[tx["is_anomaly"]].sort_values(
            ["anomaly_count", "net_amount_idr"], ascending=[False, False]
        )


def data_quality_reasons(tx: pd.DataFrame) -> pd.Series:
    """Alasan record ditandai tidak valid, untuk dilaporkan ke pemilik data."""
    checks = [
        (tx["transaction_datetime"].isna(), "tanggal/jam tidak terbaca"),
        (tx["qty"].isna(), "qty kosong"),
        (tx["qty"] <= 0, "qty <= 0"),
    ]
    if "unit_price_idr" in tx:
        checks.append((tx["unit_price_idr"] <= 0, "harga satuan <= 0"))
    if "discount_pct" in tx:
        disc = pd.to_numeric(tx["discount_pct"], errors="coerce")
        checks.append(((disc < 0) | (disc > 100), "diskon di luar 0-100%"))
    reasons = pd.Series([[] for _ in range(len(tx))], index=tx.index)
    for mask, label in checks:
        for i in tx.index[mask.fillna(False)]:
            reasons[i].append(label)
    return reasons.map(lambda r: ", ".join(r) if r else "ditandai tidak valid di sumber (is_valid_record = FALSE)")


def detect(transactions: pd.DataFrame, members: pd.DataFrame, cfg: RuleConfig | None = None) -> DetectionResult:
    cfg = cfg or RuleConfig()
    tx = transactions.copy()

    in_scope = tx["is_valid_record"] if cfg.exclude_invalid_records else pd.Series(True, index=tx.index)
    in_scope &= tx["transaction_datetime"].notna()
    scope = tx[in_scope]

    parts = [
        rules.r1_card_sharing(scope, cfg),
        rules.r2_tier_mismatch(scope, members, cfg),
        rules.r3_outside_hours(scope, cfg),
        rules.r4_bulk_limited(scope, cfg),
        rules.r5_impossible_travel(scope, cfg),
        rules.r6_duplicate_account(scope, members, cfg),
    ]
    flags = pd.concat(parts, axis=1)
    flags = flags.rename(columns={f"flag_{code}": col for code, (col, _) in RULES.items()})
    flag_cols = [col for col, _ in RULES.values()]

    flags["anomaly_count"] = flags[flag_cols].sum(axis=1).astype(int)
    codes = list(RULES)
    flags["triggered_rules"] = flags[flag_cols].apply(
        lambda row: ", ".join(c for c, hit in zip(codes, row) if hit), axis=1
    )
    flags["evidence_summary"] = flags.apply(
        lambda row: "\n".join(f"{c}: {row[f'evidence_{c}']}" for c in codes if row[f"evidence_{c}"]),
        axis=1,
    )

    tx["evaluated"] = in_scope
    tx["member_tier_master"] = rules.member_tier_lookup(tx, members)
    tx = tx.join(flags)
    for col in flag_cols:
        tx[col] = tx[col].astype("boolean")
    tx["anomaly_count"] = tx["anomaly_count"].fillna(0).astype(int)
    tx["is_anomaly"] = tx["anomaly_count"] > 0
    for col in ["triggered_rules", "evidence_summary"] + [f"evidence_{c}" for c in codes]:
        tx[col] = tx[col].fillna("")

    dq = tx.loc[~in_scope].copy()
    dq["exclusion_reason"] = data_quality_reasons(dq)

    return DetectionResult(
        transactions=tx,
        duplicate_members=rules.duplicate_contacts(members),
        data_quality=dq,
        config=cfg,
    )


def summarize(result: DetectionResult) -> pd.DataFrame:
    """Ringkasan per rule: jumlah transaksi, member, dan nilai transaksi terdampak."""
    tx = result.transactions[result.transactions["evaluated"]]
    total = len(tx)
    rows = []
    for code, (col, desc) in RULES.items():
        hit = tx[tx[col].fillna(False).astype(bool)]
        rows.append({
            "rule": code,
            "deskripsi": desc,
            "jumlah_transaksi": len(hit),
            "persen_transaksi": round(100 * len(hit) / total, 2) if total else 0.0,
            "jumlah_member": hit.loc[hit["member_id"] != "GUEST", "member_id"].nunique(),
            "jumlah_toko": hit["store_name"].nunique() if "store_name" in hit else None,
            "nilai_net_idr": float(hit["net_amount_idr"].sum()),
        })
    any_hit = tx[tx["is_anomaly"]]
    rows.append({
        "rule": "TOTAL (unik)",
        "deskripsi": "Transaksi dengan >=1 indikator anomali",
        "jumlah_transaksi": len(any_hit),
        "persen_transaksi": round(100 * len(any_hit) / total, 2) if total else 0.0,
        "jumlah_member": any_hit.loc[any_hit["member_id"] != "GUEST", "member_id"].nunique(),
        "jumlah_toko": any_hit["store_name"].nunique() if "store_name" in any_hit else None,
        "nilai_net_idr": float(any_hit["net_amount_idr"].sum()),
    })
    return pd.DataFrame(rows)
