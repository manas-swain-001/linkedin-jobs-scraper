import json

status = json.load(open("data/status.json", "r", encoding="utf-8"))
changed = 0
for pid, rec in status.items():
    if rec.get("status") == "SKIPPED":
        rec["status"] = "SCRAPED"
        rec.pop("skip_reason", None)
        changed += 1
json.dump(status, open("data/status.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Reset {changed} SKIPPED -> SCRAPED")