# holder-draw

Snapshot the holders of a Solana token and pick winners with a blockhash as the seed. Three
small scripts, Python 3, no dependencies. Written for the Pincer1 holder draw, usable for any mint.

## the Pincer1 draw

- snapshot: Sunday 2026-11-22 17:00 UTC, finalized slot at that moment
- 250,000 $LAMPORT = one ticket, at most ten tickets per wallet
- pool vaults, bonding curves and other program-owned accounts get no tickets; team and
  treasury wallets are listed in `exclude.txt`
- seed: the blockhash of the first block at or after snapshot slot + 1500 (about ten minutes
  later, unknown to anyone at snapshot time)
- three winners, one unit each; a wallet that already won is skipped
- a winner claims by signing a message from the winning wallet, then keeps at least 250,000
  $LAMPORT in it through delivery on 2026-12-21 (second snapshot, `recheck.py`); otherwise the
  unit goes to the next ticket drawn
- units ship with the first batch, to the destinations the order page lists

Snapshot and result files are published at https://lamportrobotics.com/draw/2026-11-22/.

## run it yourself

```
HELIUS_API_KEY=... ./snapshot.py --mint D4CzGsZgusVj2K8R1its5H8WWdo9mazbDwBc6qvsmfun --out out/2026-11-22
HELIUS_API_KEY=... ./draw.py out/2026-11-22/holders.json --exclude exclude.txt
```

To verify a published draw without an RPC key, pass the seed from `winners.json`:

```
./draw.py holders.json --exclude exclude.txt --seed <seed_blockhash>
```

The output must match `winners.json` byte for byte apart from `seed_slot_used`. The blockhash
itself can be checked on any explorer at the slot named in the file.

`recheck.py winners.json later/holders.json` reports whether every winner still meets the
threshold in a later snapshot.
