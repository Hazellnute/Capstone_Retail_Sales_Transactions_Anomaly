import pandas as pd
import pytest

from anomaly_detection import RuleConfig, detect, summarize
from anomaly_detection.loader import normalize_members, normalize_phone, normalize_transactions


def make_tx(**overrides):
    base = {
        "transaction_id": "TRX1",
        "transaction_datetime": "3/1/2026 12:00",
        "transaction_hour": 12,
        "store_name": "Plaza Senayan",
        "store_city": "Jakarta Selatan",
        "geo_area": "Jakarta",
        "channel": "Store",
        "member_id": "M1",
        "member_tier": "SILVER",
        "item_tier_requirement": "NONE",
        "qty": 1,
        "net_amount_idr": 1_000_000,
        "is_card_payment": "TRUE",
        "card_last4": "****1111",
        "issuing_bank": "BCA",
        "is_valid_record": "TRUE",
    }
    base.update(overrides)
    return base


def members_df(rows=None):
    rows = rows or [
        {"member_id": "M1", "member_tier": "Silver", "phone_number": 81111, "email": "m1@x.com"},
        {"member_id": "M2", "member_tier": "GOLD", "phone_number": 82222, "email": "m2@x.com"},
        {"member_id": "M3", "member_tier": "PLATINUM", "phone_number": 83333, "email": "m3@x.com"},
    ]
    return normalize_members(pd.DataFrame(rows))


def run(tx_rows, members=None, cfg=None):
    tx = normalize_transactions(pd.DataFrame(tx_rows))
    return detect(tx, members if members is not None else members_df(), cfg).transactions.set_index("transaction_id")


# ---------- R1 ----------

def test_r1_same_card_two_members_flags_both():
    t = run([make_tx(transaction_id="A", member_id="M1"), make_tx(transaction_id="B", member_id="M2")])
    assert t.loc["A", "flag_R1_card_sharing"] and t.loc["B", "flag_R1_card_sharing"]
    assert "M2" in t.loc["A", "evidence_R1"]


def test_r1_same_last4_different_bank_not_flagged():
    t = run([make_tx(transaction_id="A", member_id="M1"),
             make_tx(transaction_id="B", member_id="M2", issuing_bank="BNI")])
    assert not t["flag_R1_card_sharing"].any()


def test_r1_card_key_payment_type_does_not_split_card():
    # Kartu sama, tipe pembayaran beda: tetap satu kartu.
    t = run([make_tx(transaction_id="A", member_id="M1", card_key="****1111-BCA-CREDIT CARD"),
             make_tx(transaction_id="B", member_id="M2", card_key="****1111-BCA-INSTALLMENT")])
    assert t["flag_R1_card_sharing"].all()


def test_r1_missing_bank_and_guest_ignored():
    t = run([make_tx(transaction_id="A", member_id="M1", issuing_bank=None),
             make_tx(transaction_id="B", member_id="M2", issuing_bank=None),
             make_tx(transaction_id="C", member_id="GUEST", member_tier="GUEST"),
             make_tx(transaction_id="D", member_id="M3")])
    assert not t.loc[["A", "B", "C"], "flag_R1_card_sharing"].any()
    assert not t.loc["D", "flag_R1_card_sharing"]


# ---------- R2 ----------

@pytest.mark.parametrize("item,member,expected", [
    ("GOLD", "M1", True),       # SILVER beli GOLD
    ("PLATINUM", "M2", True),   # GOLD beli PLATINUM
    ("GOLD", "M2", False),
    ("NONE", "GUEST", False),
    ("GOLD", "GUEST", True),
])
def test_r2_tier_mismatch(item, member, expected):
    t = run([make_tx(item_tier_requirement=item, member_id=member)])
    assert bool(t.loc["TRX1", "flag_R2_tier_mismatch"]) is expected


def test_r2_uses_master_tier_case_insensitive():
    # Tier di transaksi GOLD, tapi master bilang Silver -> master yang dipakai.
    t = run([make_tx(member_id="M1", member_tier="GOLD", item_tier_requirement="GOLD")])
    assert t.loc["TRX1", "flag_R2_tier_mismatch"]
    assert t.loc["TRX1", "member_tier_master"] == "SILVER"


# ---------- R3 ----------

@pytest.mark.parametrize("dt,hour,expected", [
    ("3/1/2026 8:59", 8, True),
    ("3/1/2026 9:00", 9, False),
    ("3/1/2026 21:59", 21, False),
    ("3/1/2026 22:00", 22, True),
    ("3/1/2026 2:15", None, True),  # jam kosong -> diambil dari datetime
])
def test_r3_operating_hours_boundaries(dt, hour, expected):
    t = run([make_tx(transaction_datetime=dt, transaction_hour=hour)])
    assert bool(t.loc["TRX1", "flag_R3_outside_hours"]) is expected


# ---------- R4 ----------

@pytest.mark.parametrize("tier,qty,expected", [
    ("PLATINUM", 1, False), ("PLATINUM", 2, True),
    ("GOLD", 2, False), ("GOLD", 3, True),
    ("NONE", 10, False),
])
def test_r4_bulk_limits(tier, qty, expected):
    t = run([make_tx(item_tier_requirement=tier, qty=qty, member_id="M3")])
    assert bool(t.loc["TRX1", "flag_R4_bulk_limited"]) is expected


# ---------- R5 ----------

def test_r5_different_area_within_window_flags_both():
    t = run([make_tx(transaction_id="A", transaction_datetime="3/1/2026 12:00", card_last4="****1"),
             make_tx(transaction_id="B", transaction_datetime="3/1/2026 13:00", card_last4="****2",
                     store_name="Beachwalk Kuta", geo_area="Bali")])
    assert t.loc["A", "flag_R5_impossible_travel"] and t.loc["B", "flag_R5_impossible_travel"]
    assert "60 menit" in t.loc["B", "evidence_R5"]


def test_r5_exactly_90_minutes_not_flagged():
    t = run([make_tx(transaction_id="A", transaction_datetime="3/1/2026 12:00"),
             make_tx(transaction_id="B", transaction_datetime="3/1/2026 13:30", geo_area="Bali")])
    assert not t["flag_R5_impossible_travel"].any()


def test_r5_same_geo_area_different_city_not_flagged():
    t = run([make_tx(transaction_id="A", store_city="Jakarta Selatan"),
             make_tx(transaction_id="B", transaction_datetime="3/1/2026 12:30", store_city="Jakarta Utara")])
    assert not t["flag_R5_impossible_travel"].any()


def test_r5_online_and_guest_excluded():
    t = run([make_tx(transaction_id="A"),
             make_tx(transaction_id="B", transaction_datetime="3/1/2026 12:10", channel="Online", geo_area="Online"),
             make_tx(transaction_id="C", member_id="GUEST", member_tier="GUEST"),
             make_tx(transaction_id="D", member_id="GUEST", member_tier="GUEST",
                     transaction_datetime="3/1/2026 12:10", geo_area="Bali")])
    assert not t["flag_R5_impossible_travel"].any()


# ---------- R6 ----------

def test_phone_normalization():
    assert normalize_phone("0812-3456") == normalize_phone("+62 812 3456") == normalize_phone(8123456)
    assert normalize_phone(None) == ""


def test_r6_duplicate_phone_or_email():
    members = members_df([
        {"member_id": "M1", "member_tier": "SILVER", "phone_number": "0811", "email": "A@x.com "},
        {"member_id": "M2", "member_tier": "GOLD", "phone_number": "62811", "email": "b@x.com"},
        {"member_id": "M3", "member_tier": "GOLD", "phone_number": "0899", "email": "a@x.com"},
        {"member_id": "M4", "member_tier": "GOLD", "phone_number": "0877", "email": "d@x.com"},
    ])
    t = run([make_tx(transaction_id=f"T{i}", member_id=f"M{i}", card_last4=f"****{i}") for i in range(1, 5)], members)
    assert t.loc[["T1", "T2", "T3"], "flag_R6_duplicate_account"].all()
    assert not t.loc["T4", "flag_R6_duplicate_account"]
    assert "telepon" in t.loc["T1", "evidence_R6"] and "email" in t.loc["T1", "evidence_R6"]


# ---------- Scope & agregasi ----------

def test_invalid_records_excluded_from_rules_and_reported():
    tx = normalize_transactions(pd.DataFrame([
        make_tx(transaction_id="OK"),
        make_tx(transaction_id="BAD", qty=None, is_valid_record="FALSE", transaction_hour=3,
                transaction_datetime="3/1/2026 3:00"),
    ]))
    res = detect(tx, members_df())
    t = res.transactions.set_index("transaction_id")
    assert not t.loc["BAD", "evaluated"] and not t.loc["BAD", "is_anomaly"]
    assert pd.isna(t.loc["BAD", "flag_R3_outside_hours"])
    assert res.data_quality["exclusion_reason"].iloc[0] == "qty kosong"

    res_all = detect(tx, members_df(), RuleConfig(exclude_invalid_records=False))
    assert res_all.transactions.set_index("transaction_id").loc["BAD", "flag_R3_outside_hours"]


def test_anomaly_count_and_summary():
    t = run([make_tx(item_tier_requirement="GOLD", qty=3, transaction_datetime="3/1/2026 23:00", transaction_hour=23)])
    assert t.loc["TRX1", "anomaly_count"] == 3
    assert t.loc["TRX1", "triggered_rules"] == "R2, R3, R4"
    assert t.loc["TRX1", "evidence_summary"].count("\n") == 2

    tx = normalize_transactions(pd.DataFrame([make_tx(transaction_hour=23, transaction_datetime="3/1/2026 23:00"),
                                              make_tx(transaction_id="TRX2", card_last4="****9")]))
    s = summarize(detect(tx, members_df())).set_index("rule")
    assert s.loc["R3", "jumlah_transaksi"] == 1
    assert s.loc["TOTAL (unik)", "persen_transaksi"] == 50.0
