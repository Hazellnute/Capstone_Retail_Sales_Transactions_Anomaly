"""Parameter rule anomali. Ubah di sini bila SOP berubah."""

from dataclasses import dataclass, field

# Urutan tier. NONE = item tanpa syarat tier, GUEST = non-member.
TIER_RANK = {"NONE": 0, "GUEST": 0, "SILVER": 1, "GOLD": 2, "PLATINUM": 3}

GUEST_ID = "GUEST"


@dataclass(frozen=True)
class RuleConfig:
    # R3: jam operasional. Transaksi pukul 21:xx masih dianggap dalam jam operasional.
    operating_hour_start: int = 9
    operating_hour_end: int = 21
    # R4: batas qty per transaksi untuk item bertier.
    tier_qty_limit: dict = field(default_factory=lambda: {"PLATINUM": 1, "GOLD": 2})
    # R5: selisih waktu minimum (menit) antar transaksi offline di area berbeda.
    impossible_travel_minutes: int = 90
    # R5: kolom lokasi yang dibandingkan. geo_area menganggap Jakarta Selatan/Utara/Pusat satu area.
    travel_location_column: str = "geo_area"
    # Record dengan is_valid_record = FALSE tidak dievaluasi rule.
    exclude_invalid_records: bool = True


RULES = {
    "R1": ("flag_R1_card_sharing", "Kartu sama dipakai >1 member"),
    "R2": ("flag_R2_tier_mismatch", "Tier item > tier member"),
    "R3": ("flag_R3_outside_hours", "Di luar jam operasional"),
    "R4": ("flag_R4_bulk_limited", "Qty item Platinum/Gold melebihi batas"),
    "R5": ("flag_R5_impossible_travel", "Impossible travel antar area (offline)"),
    "R6": ("flag_R6_duplicate_account", "Telepon/email sama dengan member lain"),
}
