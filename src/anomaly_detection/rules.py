"""Rule anomali R1-R6.

Setiap fungsi menerima transaksi yang sudah dinormalisasi dan mengembalikan
DataFrame (index sama dengan input) berisi kolom flag (bool) dan evidence (str).
Evidence kosong berarti rule tidak terpicu.
"""

import pandas as pd

from .config import GUEST_ID, TIER_RANK, RuleConfig


def _result(index, flag: pd.Series, evidence: pd.Series, code: str) -> pd.DataFrame:
    flag = flag.reindex(index).fillna(False).astype(bool)
    evidence = evidence.reindex(index).where(flag, "").fillna("")
    return pd.DataFrame({f"flag_{code}": flag, f"evidence_{code}": evidence}, index=index)


def _is_member(tx: pd.DataFrame) -> pd.Series:
    return tx["member_id"].notna() & (tx["member_id"] != GUEST_ID)


def card_id(tx: pd.DataFrame) -> pd.Series:
    """Identitas kartu = 4 digit terakhir + bank penerbit.

    card_key di data sumber ikut memuat tipe pembayaran, sehingga kartu yang sama
    bisa punya key berbeda (CREDIT CARD vs INSTALLMENT). Transaksi tanpa bank
    tidak diberi ID agar tidak memicu false positive dari tabrakan 4 digit.
    """
    is_card = tx.get("is_card_payment", pd.Series(True, index=tx.index)).astype(bool)
    ok = is_card & tx["card_last4"].notna() & tx["issuing_bank"].notna()
    return (tx["card_last4"] + "|" + tx["issuing_bank"]).where(ok)


def r1_card_sharing(tx: pd.DataFrame, cfg: RuleConfig) -> pd.DataFrame:
    cid = card_id(tx)
    members = tx["member_id"].where(_is_member(tx))
    pairs = pd.DataFrame({"cid": cid, "member_id": members}).dropna()
    members_per_card = pairs.groupby("cid")["member_id"].agg(lambda s: sorted(set(s)))

    def evidence(row):
        users = members_per_card.get(row["cid"], [])
        others = [m for m in users if m != row["member_id"]]
        if not others:
            return ""
        last4, bank = row["cid"].split("|", 1)
        return f"Kartu {last4} ({bank}) juga dipakai member {', '.join(others)}"

    ev = pairs.apply(evidence, axis=1) if len(pairs) else pd.Series(dtype=object)
    return _result(tx.index, ev.astype(str) != "", ev, "R1")


def member_tier_lookup(tx: pd.DataFrame, members: pd.DataFrame) -> pd.Series:
    """Tier dari master member menjadi acuan; fallback ke tier di transaksi."""
    master = members.set_index("member_id")["member_tier"] if len(members) else pd.Series(dtype="string")
    tier = tx["member_id"].map(master)
    return tier.fillna(tx.get("member_tier")).where(_is_member(tx), GUEST_ID)


def r2_tier_mismatch(tx: pd.DataFrame, members: pd.DataFrame, cfg: RuleConfig) -> pd.DataFrame:
    member_tier = member_tier_lookup(tx, members)
    item_tier = tx["item_tier_requirement"].fillna("NONE")
    item_rank = item_tier.map(TIER_RANK).fillna(0)
    member_rank = member_tier.map(TIER_RANK).fillna(0)
    flag = item_rank > member_rank
    ev = "Item membutuhkan tier " + item_tier + " namun pembeli bertier " + member_tier.fillna("tidak diketahui")
    return _result(tx.index, flag, ev, "R2")


def r3_outside_hours(tx: pd.DataFrame, cfg: RuleConfig) -> pd.DataFrame:
    hour = tx["transaction_hour"]
    flag = hour.notna() & ((hour < cfg.operating_hour_start) | (hour > cfg.operating_hour_end))
    clock = tx["transaction_datetime"].dt.strftime("%H:%M").fillna(hour.astype("Int64").astype(str) + ":00")
    ev = (
        "Transaksi pukul " + clock
        + f", di luar jam operasional {cfg.operating_hour_start:02d}:00-{cfg.operating_hour_end:02d}:59"
    )
    return _result(tx.index, flag, ev, "R3")


def r4_bulk_limited(tx: pd.DataFrame, cfg: RuleConfig) -> pd.DataFrame:
    tier = tx["item_tier_requirement"].fillna("NONE")
    limit = tier.map(cfg.tier_qty_limit)
    flag = limit.notna() & (tx["qty"] > limit)
    ev = (
        "Item " + tier + " dibeli " + tx["qty"].astype("Int64").astype(str)
        + " pcs, melebihi batas " + limit.astype("Int64").astype(str)
    )
    return _result(tx.index, flag, ev, "R4")


def r5_impossible_travel(tx: pd.DataFrame, cfg: RuleConfig) -> pd.DataFrame:
    loc_col = cfg.travel_location_column
    offline = tx["channel"].fillna("") != "ONLINE"
    offline &= tx[loc_col].fillna("").str.upper() != "ONLINE"
    scope = tx[offline & _is_member(tx) & tx["transaction_datetime"].notna() & tx[loc_col].notna()]
    scope = scope.sort_values(["member_id", "transaction_datetime"])

    evidence = {}
    for _, grp in scope.groupby("member_id", sort=False):
        prev = grp.shift(1)
        gap = (grp["transaction_datetime"] - prev["transaction_datetime"]).dt.total_seconds() / 60
        moved = prev[loc_col].notna() & (grp[loc_col].str.upper() != prev[loc_col].str.upper())
        hits = moved & (gap >= 0) & (gap < cfg.impossible_travel_minutes)
        for idx in grp.index[hits]:
            pos = grp.index.get_loc(idx)
            prev_idx = grp.index[pos - 1]
            p, c = tx.loc[prev_idx], tx.loc[idx]
            text = (
                f"{p['store_name']} ({p[loc_col]}) {p['transaction_datetime']:%d/%m/%Y %H:%M} "
                f"lalu {c['store_name']} ({c[loc_col]}) {c['transaction_datetime']:%d/%m/%Y %H:%M} "
                f"(selisih {int(round(gap[idx]))} menit, {p['transaction_id']} -> {c['transaction_id']})"
            )
            for i in (prev_idx, idx):
                evidence.setdefault(i, [])
                if text not in evidence[i]:
                    evidence[i].append(text)

    ev = pd.Series({i: "; ".join(v) for i, v in evidence.items()}, dtype=object)
    return _result(tx.index, pd.Series(True, index=ev.index), ev, "R5")


def duplicate_contacts(members: pd.DataFrame) -> pd.DataFrame:
    """Daftar member yang berbagi telepon atau email dengan member lain."""
    rows = []
    for key, label in (("phone_norm", "telepon"), ("email_norm", "email")):
        valid = members[members[key].astype(str) != ""]
        for value, grp in valid.groupby(key):
            ids = sorted(grp["member_id"])
            if len(ids) < 2:
                continue
            for mid in ids:
                rows.append({
                    "member_id": mid,
                    "contact_type": label,
                    "contact_value": value,
                    "shared_with": ", ".join(x for x in ids if x != mid),
                    "group_size": len(ids),
                })
    return pd.DataFrame(rows, columns=["member_id", "contact_type", "contact_value", "shared_with", "group_size"])


def r6_duplicate_account(tx: pd.DataFrame, members: pd.DataFrame, cfg: RuleConfig) -> pd.DataFrame:
    dup = duplicate_contacts(members)
    if dup.empty:
        return _result(tx.index, pd.Series(False, index=tx.index), pd.Series("", index=tx.index), "R6")
    text = dup.assign(t=dup["contact_type"] + " sama dengan member " + dup["shared_with"])
    per_member = text.groupby("member_id")["t"].agg("; ".join)
    ev = tx["member_id"].map(per_member)
    return _result(tx.index, ev.notna() & _is_member(tx), ev, "R6")
