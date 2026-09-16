import json, glob, os

posts = json.load(open("data/posts.json", "r", encoding="utf-8"))
posts_by_id = {p["post_id"]: p for p in posts}
status = {}

for f in glob.glob("data/emails/*.txt"):
    pid = os.path.splitext(os.path.basename(f))[0]
    text = open(f, "r", encoding="utf-8").read()
    to_line = text.split("\n")[0]
    to_email = to_line.replace("TO: ", "").strip()
    p = posts_by_id.get(pid, {})
    status[pid] = {
        "status": "GENERATED",
        "post_id": pid,
        "to_email": to_email,
        "author": p.get("author", ""),
        "mail_file": f"data/emails/{pid}.txt",
    }

json.dump(status, open("data/status.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Status.json: {len(status)} GENERATED records")
for pid, rec in status.items():
    print(f"  {rec['author']:30s} -> {rec['to_email']}")
