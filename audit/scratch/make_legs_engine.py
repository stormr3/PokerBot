from pathlib import Path
src = Path("c:/VSC_Projects/PokerBots/engine.py").read_text(encoding="utf-8")
old = '    1: {"hands": 400, "time_bank_ms": 60_000, "wallclock_s": 180, "cap": 400},'
new = '    1: {"hands": 200, "time_bank_ms": 30_000, "wallclock_s": 90, "cap": 200},'
assert old in src, "Expected stage 1 line not found in engine.py"
out = Path("c:/VSC_Projects/PokerBots/audit/engine_legs.py")
out.write_text(src.replace(old, new, 1), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size} bytes)")
