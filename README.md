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

## Fitur Deteksi Anomali (Rule-Based R1–R6)

Modul Python di `src/anomaly_detection/` menguji **seluruh populasi transaksi** terhadap enam rule berikut:

| Kode | Indikator | Kriteria | Catatan implementasi |
|------|-----------|----------|----------------------|
| R1 | Card sharing | Kartu yang sama dipakai >1 member | Kartu = `card_last4` + `issuing_bank`. `card_key` tidak dipakai karena ikut memuat tipe pembayaran. Transaksi tanpa bank dan GUEST dikecualikan. |
| R2 | Tier mismatch | Tier item > tier member | Tier diambil dari master member (fallback ke transaksi). GUEST = tier terendah. |
| R3 | Di luar jam operasional | Di luar 09:00–21:59 | Pukul 21:xx masih dianggap dalam jam operasional. |
| R4 | Pembelian massal item terbatas | Qty Platinum > 1 / Gold > 2 | Per transaksi. |
| R5 | Impossible travel | Transaksi offline member yang sama di dua area berbeda dalam < 90 menit | Dibandingkan per `geo_area`, sehingga perpindahan antar-mal di Jakarta tidak dianggap. Online dan GUEST dikecualikan. |
| R6 | Akun duplikat | Telepon atau email sama dengan member lain | Telepon dinormalisasi (`0812…` = `62812…`), email di-lowercase. |

Record dengan `is_valid_record = FALSE` **tidak dievaluasi** rule, tetapi dilaporkan beserta alasannya (qty kosong, harga ≤ 0, diskon di luar 0–100%). Gunakan `--include-invalid` untuk ikut mengevaluasinya. Semua parameter ada di `src/anomaly_detection/config.py`.

### Cara menjalankan

```bash
pip install -r requirements.txt

# Letakkan data di data/raw/ (folder ini di-gitignore karena berisi PII)
PYTHONPATH=src python -m anomaly_detection \
  --transactions data/raw/retail_sales_transactions_clean.csv \
  --members data/raw/member_master_analyze.xlsx \
  --output reports/output/anomaly_report.xlsx

# Unit test
python -m pytest
```

### Isi laporan (`anomaly_report.xlsx`)

| Sheet | Isi |
|-------|-----|
| `Ringkasan` | Jumlah dan persen transaksi, member, toko, serta nilai net per rule |
| `Transaksi_Anomali` | Transaksi ber-flag, diurutkan dari jumlah rule terpicu lalu nilai transaksi, lengkap dengan evidence |
| `Member_Kontak_Duplikat` | Detail kelompok member yang berbagi telepon/email (R6) |
| `Data_Quality` | Record yang dikecualikan dan alasannya |
| `Semua_Transaksi` | Seluruh transaksi dengan flag dan evidence per rule |
| `Parameter` | Parameter rule yang dipakai saat laporan dibuat (untuk jejak audit) |

## Tools & Teknologi

- Python (pandas, numpy, scikit-learn, matplotlib/seaborn)
- Jupyter Notebook
- SQL (opsional)
- Excel / Looker Studio / Power BI / Tableau untuk dashboard

## Catatan Kerahasiaan Data

Data yang memuat informasi sensitif (nama karyawan, ID pelanggan, dan sejenisnya) harus dianonimkan atau dimasking sebelum diunggah ke repository.

## Status Proyek

- ✅ Deteksi rule-based R1–R6 (Python) beserta laporan Excel dan unit test
- ✅ Workflow n8n agentic (risk classifier + alert drafting). Lihat [`n8n/`](n8n/README.md)
- 🚧 Dashboard monitoring dan model anomali statistik/ML

## Author

**Nathalia Triandini**
