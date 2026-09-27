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

## Tools & Teknologi

- Python (pandas, numpy, scikit-learn, matplotlib/seaborn)
- Jupyter Notebook
- SQL (opsional)
- Excel / Looker Studio / Power BI / Tableau untuk dashboard

## Catatan Kerahasiaan Data

Data yang memuat informasi sensitif (nama karyawan, ID pelanggan, dan sejenisnya) harus dianonimkan atau dimasking sebelum diunggah ke repository.

## Status Proyek

🚧 Tahap awal: inisialisasi repository.

## Author

**Nathalia Triandini**
