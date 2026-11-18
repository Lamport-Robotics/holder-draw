#!/usr/bin/env python3
"""Delivery check: are the winners still at or above the threshold in a later snapshot?

    ./recheck.py out/2026-11-22/winners.json out/2026-12-21/holders.json
"""
import json
import sys
from pathlib import Path

winners = json.loads(Path(sys.argv[1]).read_text())
later = json.loads(Path(sys.argv[2]).read_text())
need = int(round(winners["rules"]["threshold_tokens"] * 10 ** later["decimals"]))
bal = {h["wallet"]: int(h["amount"]) for h in later["holders"]}
ok = True
for w in winners["winners"]:
    have = bal.get(w["wallet"], 0)
    keep = have >= need
    ok &= keep
    print(("keeps" if keep else "LOST "), w["wallet"], f"{have / 10 ** later['decimals']:,.0f} tokens at slot {later['snapshot_slot']}")
sys.exit(0 if ok else 1)
