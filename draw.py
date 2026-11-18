#!/usr/bin/env python3
"""Pick winners from a holders.json snapshot with a Solana blockhash as the seed.

Rules (all of them are arguments, the defaults are the Pincer1 draw):
  * a wallet needs at least --threshold whole tokens; every full threshold is one ticket,
    at most --cap tickets per wallet
  * program-owned accounts (pool vaults, bonding curves) and wallets in --exclude get no tickets
  * the seed is the blockhash of the first block at or after --seed-slot
    (default: snapshot slot + 1500, about ten minutes after the snapshot)
  * ticket i of the draw is sha256("<blockhash>:<i>") mod total tickets, wallets are laid out in
    sorted order; a wallet that already won is skipped

Anyone can rerun it:  ./draw.py out/2026-11-22/holders.json --seed <blockhash>
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path


def rpc(key: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": "draw", "method": method, "params": params}).encode()
    req = urllib.request.Request(
        "https://mainnet.helius-rpc.com/?api-key=" + key, data=body,
        headers={"content-type": "application/json"},
    )
    res = json.load(urllib.request.urlopen(req, timeout=60))
    if "error" in res:
        raise RuntimeError(res["error"])
    return res["result"]


def blockhash_at_or_after(key: str, slot: int) -> tuple[int, str]:
    for s in range(slot, slot + 200):
        try:
            block = rpc(key, "getBlock", [s, {"transactionDetails": "none", "rewards": False, "maxSupportedTransactionVersion": 0}])
        except RuntimeError as exc:
            if "skipped" in str(exc).lower() or "not available" in str(exc).lower() or "-32007" in str(exc) or "-32009" in str(exc):
                continue
            raise
        if block and block.get("blockhash"):
            return s, block["blockhash"]
    raise SystemExit(f"no block found in 200 slots after {slot}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("holders")
    ap.add_argument("--threshold", type=float, default=250_000)
    ap.add_argument("--cap", type=int, default=10)
    ap.add_argument("--winners", type=int, default=3)
    ap.add_argument("--seed-slot", type=int, help="default: snapshot slot + 1500")
    ap.add_argument("--seed", help="blockhash to use instead of fetching the seed slot (offline verification)")
    ap.add_argument("--exclude", help="file with one wallet per line (team, treasury, exchanges)")
    ap.add_argument("--out", help="write winners.json here (default: next to holders.json)")
    args = ap.parse_args()

    snap = json.loads(Path(args.holders).read_text())
    threshold_raw = int(round(args.threshold * 10 ** snap["decimals"]))
    excluded = set()
    if args.exclude and Path(args.exclude).exists():
        excluded = {l.strip() for l in Path(args.exclude).read_text().splitlines() if l.strip() and not l.startswith("#")}

    tickets = []  # (wallet, count) in sorted wallet order
    for h in sorted(snap["holders"], key=lambda h: h["wallet"]):
        if h["kind"].startswith("program:") or h["wallet"] in excluded:
            continue
        n = min(args.cap, int(h["amount"]) // threshold_raw)
        if n > 0:
            tickets.append((h["wallet"], n))
    total = sum(n for _, n in tickets)
    if total == 0:
        sys.exit("no tickets")

    seed_slot = args.seed_slot or snap["snapshot_slot"] + 1500
    if args.seed:
        used_slot, seed = None, args.seed
    else:
        key = os.environ.get("HELIUS_API_KEY")
        if not key:
            sys.exit("HELIUS_API_KEY is not set (or pass --seed <blockhash>)")
        used_slot, seed = blockhash_at_or_after(key, seed_slot)

    winners, i = [], 0
    while len(winners) < min(args.winners, len(tickets)):
        pick = int.from_bytes(hashlib.sha256(f"{seed}:{i}".encode()).digest(), "big") % total
        i += 1
        acc = 0
        for wallet, n in tickets:
            acc += n
            if pick < acc:
                if wallet not in [w["wallet"] for w in winners]:
                    winners.append({"wallet": wallet, "tickets": n, "ticket_index": pick, "draw_index": i - 1})
                break

    out = {
        "mint": snap["mint"],
        "snapshot_slot": snap["snapshot_slot"],
        "snapshot_time_utc": snap["snapshot_time_utc"],
        "holders_sha256": hashlib.sha256(Path(args.holders).read_bytes()).hexdigest(),
        "rules": {"threshold_tokens": args.threshold, "cap_per_wallet": args.cap, "winners": args.winners,
                  "seed_slot_requested": seed_slot, "seed_slot_used": used_slot, "excluded": sorted(excluded)},
        "seed_blockhash": seed,
        "eligible_wallets": len(tickets),
        "total_tickets": total,
        "tickets": [{"wallet": w, "tickets": n} for w, n in tickets],
        "winners": winners,
    }
    dest = Path(args.out) if args.out else Path(args.holders).with_name("winners.json")
    dest.write_text(json.dumps(out, indent=1))
    print(f"{len(tickets)} eligible wallets, {total} tickets, seed {seed} (slot {used_slot or 'given'})")
    for w in winners:
        print("winner", w["wallet"], f"({w['tickets']} tickets)")
    print("wrote", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
