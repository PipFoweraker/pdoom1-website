# p(Doom)1 data contracts

These JSON Schemas are the **enforced contracts** for the data that flows between the
game, pdoom-data, and the website. They are the single source of truth for the *shape* of
each seam — both the producer and the consumer validate against the same file, so a
field rename turns CI red instead of silently shipping a `NaN` / broken page to production.

| Schema | Seam | Producer | Consumer |
|---|---|---|---|
| `events.schema.json` | historical events | pdoom-data → `sync-events.py` | website event pages/timeline |
| `leaderboard-seed.schema.json` | per-seed scores (`entry` = the score-submission contract) | game leaderboard export | website leaderboard |
| `leaderboard-weekly.schema.json` | weekly league `current.json` | game export + `weekly-league-reset.yml` | website league page |

The website validates the projection it *receives* via `scripts/validate_data.py`
(schema + semantic checks: encoding, freshness, version drift, referential integrity).
That's the defensive half — the consumer guarding the boundary it controls.

## Game-side (producer) validation — drop-in for the `pdoom1` repo

Validate your leaderboard export **before** you push it, so bad data never leaves the game.
Copy `leaderboard-seed.schema.json` + `leaderboard-weekly.schema.json` into the game repo
(e.g. `contracts/`) and add a CI step:

```yaml
# .github/workflows/validate-export.yml (game repo)
- name: Validate leaderboard export against contract
  run: |
    pip install --quiet jsonschema==4.26.0
    python - <<'PY'
    import json, sys, glob
    from jsonschema import Draft7Validator
    seed = json.load(open('contracts/leaderboard-seed.schema.json'))
    v = Draft7Validator(seed)
    bad = 0
    for f in glob.glob('exports/seed_leaderboard_*.json'):
        errs = sorted(v.iter_errors(json.load(open(f))), key=lambda e: list(e.path))
        for e in errs:
            print(f"{f}: {'/'.join(map(str,e.path)) or '(root)'}: {e.message}"); bad += 1
    sys.exit(1 if bad else 0)
    PY
```

Keeping the schema files identical across repos is the whole point. When you change the
contract, change it in one place and copy it out — or, better, publish `schemas/` as the
canonical copy and have the game repo fetch it in CI.

## Versioning
Treat a schema change as a breaking API change: bump intentionally, update both sides in
the same PR, and let the failing validation on the other side tell you what you forgot.
