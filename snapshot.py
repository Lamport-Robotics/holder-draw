#!/usr/bin/env python3
"""Snapshot every holder of an SPL / Token-2022 mint through Helius DAS.

Writes <out>/holders.json: the finalized slot the walk started at, every owner's balance summed
over its token accounts, and what kind of account the owner is (a wallet, a program-owned
account such as a pool vault, or an address with no account on chain). No dependencies.

    HELIUS_API_KEY=... ./snapshot.py --mint <mint> --out out/2026-11-22
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

SYSTEM_PROGRAM = "11111111111111111111111111111111"


def rpc(key: str, method: str, params, retries: int = 5):
    body = json.dumps({"jsonrpc": "2.0", "id": "snapshot", "method": method, "params": params}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://mainnet.helius-rpc.com/?api-key=" + key, data=body,
                headers={"content-type": "application/json"},
            )
            res = json.load(urllib.request.urlopen(req, timeout=60))
            if "error" in res:
                raise RuntimeError(res["error"])
            return res["result"]
        except Exception as exc:  # noqa: BLE001 - retry anything, report the last error
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
            print(f"retry {method}: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mint", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    key = os.environ.get("HELIUS_API_KEY")
    if not key:
        sys.exit("HELIUS_API_KEY is not set")

    mint_info = rpc(key, "getAccountInfo", [args.mint, {"encoding": "jsonParsed"}])["value"]
    decimals = int(mint_info["data"]["parsed"]["info"]["decimals"])
    slot0 = rpc(key, "getSlot", [{"commitment": "finalized"}])
    taken_at = rpc(key, "getBlockTime", [slot0])

    accounts, cursor = [], None
    while True:
        params = {"mint": args.mint, "limit": 1000, "options": {"showZeroBalance": False}}
        if cursor:
            params["cursor"] = cursor
        page = rpc(key, "getTokenAccounts", params)
        accounts += page.get("token_accounts", [])
        cursor = page.get("cursor")
        if not cursor:
            break
    slot1 = rpc(key, "getSlot", [{"commitment": "finalized"}])

    balances: dict[str, int] = {}
    for acc in accounts:
        if acc.get("frozen"):
            continue
        balances[acc["owner"]] = balances.get(acc["owner"], 0) + int(acc["amount"])

    owners = sorted(balances)
    kinds: dict[str, str] = {}
    for i in range(0, len(owners), 100):
        chunk = owners[i : i + 100]
        infos = rpc(key, "getMultipleAccounts", [chunk, {"encoding": "base64"}])["value"]
        for owner, info in zip(chunk, infos):
            if info is None:
                kinds[owner] = "no-account"
            elif info["owner"] == SYSTEM_PROGRAM:
                kinds[owner] = "wallet"
            else:
                kinds[owner] = "program:" + info["owner"]

    holders = [
        {"wallet": o, "amount": str(balances[o]), "tokens": balances[o] / 10**decimals, "kind": kinds[o]}
        for o in owners
    ]
    out = {
        "mint": args.mint,
        "decimals": decimals,
        "snapshot_slot": slot0,
        "snapshot_time_unix": taken_at,
        "snapshot_time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(taken_at)),
        "finished_slot": slot1,
        "token_accounts": len(accounts),
        "holders": holders,
    }
    path = Path(args.out)
    path.mkdir(parents=True, exist_ok=True)
    data = json.dumps(out, indent=1, sort_keys=True).encode()
    (path / "holders.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (path / "holders.sha256").write_text(digest + "  holders.json\n")
    print(f"slot {slot0} ({out['snapshot_time_utc']} UTC), {len(accounts)} token accounts, {len(holders)} holders")
    print("sha256", digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
