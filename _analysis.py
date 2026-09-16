from collections import Counter

lines = open("logs/app.log", "r", encoding="utf-8", errors="replace").readlines()
today = [l.strip() for l in lines if "[2026-09-15" in l]

generated = [l for l in today if "[GENERATED]" in l]
skipped = [l for l in today if "SKIPPED" in l]
errors = [l for l in today if "ERROR" in l and "MAIL GENERATION" not in l]

print("=== TODAY (Sep 15) - 134 posts scraped ===")
print(f"Generated mail:     {len(generated)}")
print(f"Skipped:            {len(skipped)}")
print(f"Error:              {len(errors)}")
print(f"Never attempted:    {134 - len(generated) - len(skipped) - len(errors)}")
print()
print("--- SKIPPED reasons ---")
for l in skipped:
    parts = l.split("| reason:")
    if len(parts) == 2:
        name = parts[0].split("]")[-1].strip()
        print(f"  {name}")
        print(f"    reason: {parts[1].strip()}")
print()
print("--- ERRORS ---")
for l in errors:
    short = l[:150]
    print(f"  {short}")
