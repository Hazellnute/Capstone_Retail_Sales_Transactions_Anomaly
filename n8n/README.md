# n8n: Retail Anomaly Agentic Workflow

| File | Isi |
|------|-----|
| `retail_anomaly_workflow_v3.json` | Workflow v3 asli (Risk Classifier + Alert Drafting), sebagai baseline |
| `retail_anomaly_workflow_v4.sdk.ts` | Source v4 dalam format n8n Workflow SDK (sumber utama) |
| `retail_anomaly_workflow_v4.json` | Hasil ekspor v4, bisa di-import langsung ke n8n |

## Alur v4

```
Jadwal bulanan (tgl 1, 07:00)
 ├─ Ambil transaksi ─┐
 └─ Ambil member ────┴─ Gabungkan → Candidate Signal Prep (R1–R6)
                                      ├─ Tulis ke spreadsheet verifikasi (upsert, semua transaksi)
                                      └─ Filter is_anomaly → Cek belum pernah di-alert
                                           → Prioritaskan kandidat (Top 3)
                                           → Risk Classifier Agent → Gabungkan prioritas
                                           → Alert Drafting Agent → Gabungkan draft
                                           → HIGH? ── ya → Email + minta approval (maks 24 jam) ─┐
                                                   └─ tidak → Email alert ──────────────────────┴→ Log ke Data Table
```

## Rule anomali

| Kode | Indikator | Kriteria |
|------|-----------|----------|
| R1 | Card sharing | `card_key` (atau `card_last4` + bank) yang sama dipakai >1 member |
| R2 | Tier mismatch | Tier item (Silver ke atas) lebih tinggi dari tier member |
| R3 | Di luar jam operasional | Jam transaksi < 09 atau > 21 |
| R4 | Pembelian massal item terbatas | Platinum > 1 pcs, Gold > 2 pcs |
| R5 | Impossible travel | Member sama bertransaksi di 2 kota fisik berbeda dalam < 90 menit |
| R6 | Akun duplikat | Nomor telepon atau email sama dengan member lain |

Parameter rule ada di bagian atas Code node `Candidate Signal Prep (R1-R6)`.

## Perubahan v3 → v4

| # | Area | Masalah di v3 | Perbaikan di v4 |
|---|------|---------------|-----------------|
| 1 | R1 | Transaksi tanpa `card_last4` membentuk kunci `"\|BANK"`, sehingga semua member dengan bank yang sama dianggap berbagi kartu (false positive) | R1 hanya dihitung bila `card_key` atau `card_last4` terisi; nama bank dinormalisasi |
| 2 | R2 | Member dengan tier kosong atau non-member yang membeli item Regular ter-flag (rank 0 > -1) | Hanya item Silver ke atas yang dievaluasi |
| 3 | R3 | Jam diambil dari `getHours()` yang mengikuti timezone server n8n | Jam dibaca langsung dari teks `transaction_datetime`, tidak bergeser karena timezone |
| 4 | R5/R6 | Pencocokan kota case-sensitive; nomor telepon `0812-345` dan `0812345` tidak dianggap sama; ID member bisa tercatat ganda | Perbandingan kota case-insensitive, telepon dinormalisasi ke digit, ID dedup |
| 5 | Alur | Filter anomali membaca output node Google Sheets (nilai boolean bisa berubah jadi teks) dan seluruh alur berhenti bila penulisan ke Sheets gagal | Penulisan ke spreadsheet verifikasi dijadikan cabang paralel dengan `continueRegularOutput`; filter membaca langsung dari Code node |
| 6 | Sheets | Operasi `update` hanya meng-update baris yang sudah ada; transaksi baru tidak tertulis | Diganti `appendOrUpdate` (upsert berdasarkan `transaction_id`) |
| 7 | Seleksi | `Limit` mengambil 3 item **terakhir**, bukan yang paling berisiko | Kandidat diurutkan menurut jumlah rule terpicu lalu nilai transaksi, baru diambil Top 3 |
| 8 | AI | Prioritas bebas-teks; kalau model menjawab "HIGH " atau "Tinggi", alur approval terlewat | Schema pakai `enum` High/Medium/Low + normalisasi di node penggabung (fallback Medium) |
| 9 | Log | Kolom `anomaly_rules` diisi prioritas, bukan daftar rule | `anomaly_rules` = daftar rule (mis. `R2, R4`), `priority` masuk ke kolom sendiri |
| 10 | Konteks AI | Classifier dan drafter hanya menerima daftar rule, drafter tidak menerima evidence | Keduanya menerima `evidence_summary` lengkap; temperature diturunkan (0.1 / 0.3) |

## Catatan

- Workflow di n8n: **Retail Anomaly Agentic Workflow - v4 (Rebuilt)**, status **inactive**. Aktifkan setelah uji manual.
- v3 di n8n tidak diubah.
- Kedua workflow memakai Data Table `agentic_sent_anomaly_alerts` yang sama. Transaksi yang sudah pernah di-alert oleh v3 tidak akan dikirim ulang oleh v4.
