# Capstone: Retail Sales Transactions Anomaly Detection

Proyek capstone untuk mendeteksi **anomali pada transaksi penjualan retail**. Sudut pandangnya adalah **internal audit**: memakai data analytics untuk menemukan pola tidak wajar, pelanggaran kebijakan (SOP), dan indikasi fraud pada transaksi di toko.

## Latar Belakang

Volume transaksi retail sangat besar, sehingga pengujian manual berbasis sampel sering melewatkan penyimpangan. Proyek ini mencoba menerapkan **full-population testing** dengan analitik data. Tujuannya agar auditor bisa memusatkan perhatian pada transaksi yang paling berisiko.

## Tujuan

1. Mengidentifikasi transaksi yang menyimpang dari pola normal (outlier dan anomali).
2. Mendeteksi red flag yang umum pada operasional toko, misalnya:
   - Void, refund, atau retur yang berlebihan per kasir/toko
   - Diskon manual di atas batas kewenangan
   - Transaksi di luar jam operasional
   - Nilai transaksi atau kuantitas yang tidak wajar
   - Item yang tidak cocok (unmatched) dengan master data
   - Transaksi berulang atau duplikat
3. Membuat risk scoring untuk memprioritaskan transaksi yang perlu ditindaklanjuti.
4. Menyajikan temuan dalam dashboard dan laporan yang siap direview manajemen.

## Ruang Lingkup

| Area | Keterangan |
|------|------------|
| Data | Transaksi penjualan retail (header dan detail), master produk, master toko/kasir |
| Analisis | Exploratory Data Analysis, rule-based testing, statistical outlier detection, machine learning (unsupervised) |
| Output | Daftar exception, risk score, dashboard monitoring, rekomendasi pengendalian |

## Metodologi

1. **Data Understanding & Cleaning**: memeriksa kelengkapan, akurasi, dan konsistensi data.
2. **Exploratory Data Analysis (EDA)**: memetakan pola penjualan per waktu, toko, kasir, dan produk.
3. **Rule-Based Audit Tests**: pengujian berdasarkan SOP dan kebijakan perusahaan.
4. **Anomaly Detection Model**: misalnya Z-score/IQR, Isolation Forest, atau Local Outlier Factor.
5. **Risk Scoring & Prioritization**: menggabungkan hasil rule dan model menjadi skor risiko.
6. **Reporting**: visualisasi, audit observations, root cause, dan rekomendasi.

## Struktur Repository (Rencana)

```
.
├── data/
│   ├── raw/            # Data mentah (tidak di-commit jika sensitif)
│   └── processed/      # Data hasil cleaning
├── notebooks/          # Jupyter notebook untuk EDA & modelling
├── src/                # Script/fungsi reusable
├── reports/
│   └── figures/        # Grafik & visualisasi
├── dashboard/          # File dashboard
└── README.md
```

## Fitur Deteksi Anomali: Candidate Signal Prep (R1–R6)

`src/candidate_signal_prep.py` adalah versi Python dari Code node **Candidate Signal Prep** di workflow n8n v3. Nama kolom output sama dengan versi n8n, jadi hasilnya bisa ditulis kembali ke spreadsheet verifikasi. Modul inti hanya memakai standard library; `openpyxl` baru diperlukan kalau master member berupa `.xlsx`.

| Kode | Indikator | Kriteria |
|------|-----------|----------|
| R1 | Card sharing | Kartu yang sama (`card_last4` + `issuing_bank`, tanpa tipe pembayaran) dipakai >1 member. Tidak dinilai bila data kartu tidak lengkap. |
| R2 | Tier mismatch | Tier item lebih tinggi dari tier member (tier di master member lebih diutamakan) |
| R3 | Di luar jam operasional | Jam transaksi < 09 atau > 21 (jadi 09:00–21:59 dianggap normal) |
| R4 | Pembelian massal item terbatas | Qty item Platinum > 1 atau Gold > 2 |
| R5 | Impossible travel | Member yang sama bertransaksi di dua toko fisik di kota berbeda dalam < 90 menit (online dikecualikan) |
| R6 | Akun duplikat | Telepon atau email member sama dengan member lain |

### Cara menjalankan

```bash
pip install -r requirements.txt

# Letakkan data di data/raw/ (folder ini di-gitignore karena berisi PII)
python src/candidate_signal_prep.py \
  data/raw/retail_sales_transactions_clean.csv \
  data/raw/member_master_analyze.xlsx \
  reports/output/candidate_signal_prep_output.csv

python -m pytest
```

Output berisi satu baris per transaksi: semua kolom sumber, ditambah `card_identity_key`, `flag_R1…R6`, `evidence_R1…R6`, `anomaly_count`, `is_anomaly`, `is_anomaly_num`, dan `verified_at`.

### Pengujian

- `tests/fixtures.py` berisi baris-baris dari eksekusi n8n #515837 ditambah baris sintetis untuk R1, R3, dan R4 Gold.
- Uji parity menjalankan jsCode **asli** dari `n8n/retail_anomaly_workflow_v3.json` di Node.js, lalu membandingkan hasilnya dengan versi Python:
  - **R2–R6:** hasil flag dan evidence harus identik.
  - **R1:** satu-satunya deviasi yang disengaja. JS v3 memberi key `"|"` ke semua transaksi non-kartu, sehingga semuanya dianggap satu kartu (false positive). Python tidak menilai R1 bila data kartu tidak lengkap.

## Tools & Teknologi

- Python (pandas, numpy, scikit-learn, matplotlib/seaborn)
- Jupyter Notebook
- SQL (opsional)
- Excel / Looker Studio / Power BI / Tableau untuk dashboard

## Catatan Kerahasiaan Data

Data yang memuat informasi sensitif (nama karyawan, ID pelanggan, dan sejenisnya) harus dianonimkan atau dimasking sebelum diunggah ke repository.

## Status Proyek

- ✅ Candidate Signal Prep R1–R6 (Python) dengan uji parity terhadap n8n JS v3
- ✅ Workflow n8n agentic (risk classifier + alert drafting). Lihat [`n8n/`](n8n/README.md)
- 🚧 Dashboard monitoring dan model anomali statistik/ML

## Author

**Nathalia Triandini**
