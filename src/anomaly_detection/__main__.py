"""CLI: python -m anomaly_detection --transactions <csv> --members <xlsx> [--output <xlsx>]"""

import argparse
from pathlib import Path

from .config import RuleConfig
from .detector import detect, summarize
from .loader import load_members, load_transactions
from .report import write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Deteksi anomali transaksi penjualan retail (R1-R6).")
    parser.add_argument("--transactions", required=True, help="File transaksi (.csv / .xlsx)")
    parser.add_argument("--members", required=True, help="File master member (.xlsx / .csv)")
    parser.add_argument("--members-sheet", default=0, help="Nama/index sheet master member (default: sheet pertama)")
    parser.add_argument("--output", default="reports/output/anomaly_report.xlsx", help="Path workbook hasil")
    parser.add_argument("--include-invalid", action="store_true",
                        help="Ikut evaluasi record is_valid_record = FALSE")
    args = parser.parse_args(argv)

    tx = load_transactions(args.transactions)
    members = load_members(args.members, sheet_name=args.members_sheet)
    result = detect(tx, members, RuleConfig(exclude_invalid_records=not args.include_invalid))
    out = write_report(result, args.output)

    summary = summarize(result)
    evaluated = int(result.transactions["evaluated"].sum())
    print(f"Transaksi dibaca: {len(tx)} | dievaluasi: {evaluated} | dikecualikan (data quality): {len(result.data_quality)}")
    print(summary[["rule", "deskripsi", "jumlah_transaksi", "persen_transaksi", "jumlah_member"]].to_string(index=False))
    print(f"\nLaporan: {Path(out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
