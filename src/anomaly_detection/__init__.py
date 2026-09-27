"""Deteksi anomali transaksi penjualan retail berbasis rule R1-R6."""

from .config import RULES, RuleConfig
from .detector import DetectionResult, detect, summarize
from .loader import load_members, load_transactions

__all__ = ["RULES", "RuleConfig", "DetectionResult", "detect", "summarize", "load_members", "load_transactions"]
