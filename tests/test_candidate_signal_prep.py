import json, shutil, subprocess, unittest
from pathlib import Path
from candidate_signal_prep import candidate_signal_prep, card_key_of
from fixtures import TRANSACTIONS, MEMBERS

WORKFLOW_V3 = Path(__file__).resolve().parents[1] / "n8n" / "retail_anomaly_workflow_v3.json"

def run():
    return {r["transaction_id"]: r for r in candidate_signal_prep(TRANSACTIONS, MEMBERS)}

class RuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r = run()

    # parity with real n8n execution #515837
    def test_clean_row_TRX20859(self):
        self.assertEqual(self.r["TRX20859"]["anomaly_count"], 0)
    def test_R4_platinum_TRX20038(self):
        row = self.r["TRX20038"]
        self.assertTrue(row["flag_R4_bulk_limited"]); self.assertEqual(row["anomaly_count"], 1)
        self.assertEqual(row["evidence_R4"], "Item Platinum dibeli 3 pcs, melebihi batas 1")
        self.assertIn("R1 tidak dinilai", row["evidence_R1"])  # debit, bank kosong
    def test_R2_tier_TRX20638(self):
        self.assertEqual(self.r["TRX20638"]["evidence_R2"], "Item membutuhkan tier GOLD namun member bertier SILVER")
    def test_R6_duplicate_TRX20237(self):
        self.assertEqual(self.r["TRX20237"]["evidence_R6"],
            "nomor telepon sama dengan member MBR10170, MBR10188; email sama dengan member MBR10170")
    def test_R5_travel_TRX20755(self):
        self.assertEqual(self.r["TRX20755"]["evidence_R5"],
            "Jakarta Pusat pada 4/28/26 16:12 lalu Bali pada 4/28/26 17:06 (selisih 54 menit)")
    # synthetic coverage
    def test_R1_card_sharing(self):
        self.assertTrue(self.r["TRX90001"]["flag_R1_card_sharing"])
        self.assertIn("MBR10201", self.r["TRX90001"]["evidence_R1"])
    def test_R3_and_R4_gold(self):
        row = self.r["TRX90003"]
        self.assertTrue(row["flag_R3_outside_hours"]); self.assertTrue(row["flag_R4_bulk_limited"])
        self.assertEqual(row["anomaly_count"], 2)
    def test_online_excluded_from_R5(self):
        self.assertFalse(self.r["TRX90005"]["flag_R5_impossible_travel"])

@unittest.skipUnless(shutil.which("node") and WORKFLOW_V3.exists(), "butuh Node.js dan n8n/retail_anomaly_workflow_v3.json")
class ParityWithN8nJs(unittest.TestCase):
    """Runs the ORIGINAL n8n jsCode in Node on the same fixtures and compares every flag.

    Satu deviasi disengaja pada R1: JS v3 memberi key "|" ke semua transaksi non-kartu
    (card_last4 & bank kosong), sehingga seluruh transaksi non-kartu dianggap memakai
    satu kartu yang sama (false positive). Python tidak menilai R1 bila data kartu tidak
    lengkap, dan teks evidence R1 dibuat lebih informatif. Rule lain harus identik.
    """
    @classmethod
    def setUpClass(cls):
        wf = json.loads(WORKFLOW_V3.read_text())
        js = next(n for n in wf["nodes"] if n["name"] == "Candidate Signal Prep")["parameters"]["jsCode"]
        items = [{"json": t} for t in TRANSACTIONS] + [{"json": {**m, "member_name": "x"}} for m in MEMBERS]
        harness = ("const $input={all:()=>" + json.dumps(items) + "};\n"
                   "const out=(function(){" + js + "})();\n"
                   "console.log(JSON.stringify(out.map(o=>o.json)));")
        cls.js_rows = json.loads(subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True).stdout)
        cls.py = run()

    def test_R2_to_R6_identical_to_original_js(self):
        keys = [k for k in self.js_rows[0]
                if k.startswith(("flag_", "evidence_")) and "R1" not in k]
        mism = [(j["transaction_id"], k, j[k], self.py[j["transaction_id"]][k])
                for j in self.js_rows for k in keys if j[k] != self.py[j["transaction_id"]][k]]
        self.assertEqual(mism, [], mism)
        print(f"\n  parity R2-R6: {len(self.js_rows)} rows x {len(keys)} fields identical to n8n JS")

    def test_R1_differs_only_on_incomplete_card_data(self):
        for j in self.js_rows:
            p = self.py[j["transaction_id"]]
            if card_key_of(p):
                self.assertEqual(j["flag_R1_card_sharing"], p["flag_R1_card_sharing"], j["transaction_id"])
            else:
                self.assertFalse(p["flag_R1_card_sharing"], j["transaction_id"])

    def test_anomaly_count_differs_only_by_R1(self):
        for j in self.js_rows:
            p = self.py[j["transaction_id"]]
            self.assertEqual(j["anomaly_count"] - j["flag_R1_card_sharing"],
                             p["anomaly_count"] - p["flag_R1_card_sharing"], j["transaction_id"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
