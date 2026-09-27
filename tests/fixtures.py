"""Test fixtures — rows mirror the real n8n execution #515837 (27 Sep 2026)
plus synthetic rows for rules not visible in that run (R1, R3, Gold R4)."""
def trx(tid, dt, hour, city, member, tier, item_tier, qty, amount, card=True,
        last4="****0000", bank="BCA", channel="Store", store="Store X", geo=None):
    return {"transaction_id": tid, "transaction_datetime": dt, "transaction_hour": hour,
            "store_name": store, "store_city": city, "geo_area": geo or city, "channel": channel,
            "member_id": member, "member_tier": tier, "item_tier_requirement": item_tier,
            "qty": qty, "net_amount_idr": amount, "is_card_payment": card,
            "card_last4": last4, "issuing_bank": bank}

TRANSACTIONS = [
    # --- real rows from execution #515837 ---
    trx("TRX20859", "4/1/26 14:32", 14, "Jakarta Utara", "MBR10034", "SILVER", "NONE", 1, 3200000, last4="****0501", bank="BRI", store="Kelapa Gading Mall"),
    trx("TRX20038", "5/19/26 10:39", 10, "Jakarta Utara", "MBR10003", "PLATINUM", "PLATINUM", 3, 105000000, last4="****8497", bank="", store="Kelapa Gading Mall"),
    trx("TRX20638", "4/10/26 13:00", 13, "Bandung", "MBR10117", "SILVER", "GOLD", 1, 6480000, last4="****1111", bank="MANDIRI", store="Paris Van Java"),
    trx("TRX20237", "4/12/26 15:00", 15, "Jakarta Selatan", "MBR10106", "SILVER", "NONE", 1, 2380000, card=False, store="Plaza Senayan"),
    trx("TRX20755", "4/28/26 16:12", 16, "Jakarta Pusat", "GUEST", "GUEST", "NONE", 1, 4275000, last4="****5464", bank="OCBC", store="Grand Indonesia"),
    trx("TRX20756", "4/28/26 17:06", 17, "Bali", "GUEST", "GUEST", "NONE", 1, 1500000, card=False, store="Beachwalk"),
    # --- synthetic rows ---
    trx("TRX90001", "4/5/26 11:00", 11, "Surabaya", "MBR10200", "GOLD", "NONE", 1, 900000, last4="****7777", bank="BNI"),
    trx("TRX90002", "4/6/26 12:00", 12, "Surabaya", "MBR10201", "GOLD", "NONE", 1, 950000, last4="****7777", bank="BNI"),
    trx("TRX90003", "4/7/26 23:15", 23, "Surabaya", "MBR10202", "GOLD", "GOLD", 3, 12000000, card=False),
    trx("TRX90004", "4/8/26 12:00", 12, "Online", "MBR10203", "GOLD", "NONE", 1, 500000, card=False, channel="Online"),
    trx("TRX90005", "4/8/26 12:30", 12, "Medan", "MBR10203", "GOLD", "NONE", 1, 500000, card=False),
    # R5: member Jakarta -> Bali 45 menit (flag) dan antar-mal dalam area Jakarta 30 menit (bukan flag)
    trx("TRX90006", "4/9/26 10:00", 10, "Jakarta Selatan", "MBR10204", "GOLD", "NONE", 1, 700000, card=False, geo="Jakarta"),
    trx("TRX90007", "4/9/26 10:45", 10, "Bali", "MBR10204", "GOLD", "NONE", 1, 700000, card=False),
    trx("TRX90008", "4/10/26 14:00", 14, "Jakarta Selatan", "MBR10205", "GOLD", "NONE", 1, 700000, card=False, geo="Jakarta"),
    trx("TRX90009", "4/10/26 14:30", 14, "Jakarta Utara", "MBR10205", "GOLD", "NONE", 1, 700000, card=False, geo="Jakarta"),
]

MEMBERS = [
    {"member_id": "MBR10034", "member_tier": "SILVER", "phone_number": "8550000001", "email": "a@x.com"},
    {"member_id": "MBR10003", "member_tier": "PLATINUM", "phone_number": "8550000002", "email": "b@x.com"},
    {"member_id": "MBR10117", "member_tier": "SILVER", "phone_number": "8550000003", "email": "c@x.com"},
    {"member_id": "MBR10106", "member_tier": "SILVER", "phone_number": "8559999999", "email": "dup@x.com"},
    {"member_id": "MBR10170", "member_tier": "GOLD", "phone_number": "8559999999", "email": "DUP@x.com"},
    {"member_id": "MBR10188", "member_tier": "GOLD", "phone_number": "8559999999", "email": "e@x.com"},
    {"member_id": "MBR10200", "member_tier": "GOLD", "phone_number": "8550000010", "email": "f@x.com"},
    {"member_id": "MBR10201", "member_tier": "GOLD", "phone_number": "8550000011", "email": "g@x.com"},
    {"member_id": "MBR10202", "member_tier": "GOLD", "phone_number": "8550000012", "email": "h@x.com"},
    {"member_id": "MBR10203", "member_tier": "GOLD", "phone_number": "8550000013", "email": "i@x.com"},
    {"member_id": "MBR10204", "member_tier": "GOLD", "phone_number": "8550000014", "email": "j@x.com"},
    {"member_id": "MBR10205", "member_tier": "GOLD", "phone_number": "8550000015", "email": "k@x.com"},
]
