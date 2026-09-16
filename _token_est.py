import json, re

from jobs_scraper.profile import load_profile, profile_to_text

profile_text = profile_to_text(load_profile())

posts = json.load(open("data/posts.json", "r", encoding="utf-8"))
contents = [p["content"] for p in posts if p["content"]]
avg_chars = sum(len(c) for c in contents) / len(contents)
max_chars = max(len(c) for c in contents)
min_chars = min(len(c) for c in contents)

from jobs_scraper.generate_mails import SYSTEM_PROMPT

def toks(chars):
    return int(chars / 4)

schema_len = len('Return ONLY a JSON object with exactly this schema:\n{"subject":"string","body":"string","missing_required_fields":["array"],"notes":"string"}')

print("=== INPUT (request) ===")
print(f"SYSTEM_PROMPT:      {len(SYSTEM_PROMPT)} chars  ~ {toks(len(SYSTEM_PROMPT))} tokens")
print(f"PROFILE text:       {len(profile_text)} chars  ~ {toks(len(profile_text))} tokens")
print(f"POST content avg:   {int(avg_chars)} chars  ~ {toks(avg_chars)} tokens")
print(f"POST content range: {min_chars}-{max_chars} chars ({toks(min_chars)}-{toks(max_chars)} tokens)")
print(f"Prompt wrapper:     ~{schema_len} chars  ~ {toks(schema_len)} tokens")
print()

total_input_avg = toks(len(SYSTEM_PROMPT) + len(profile_text) + avg_chars + schema_len)
total_input_min = toks(len(SYSTEM_PROMPT) + len(profile_text) + min_chars + schema_len)
total_input_max = toks(len(SYSTEM_PROMPT) + len(profile_text) + max_chars + schema_len)
print(f"TOTAL INPUT avg:    ~{total_input_avg} tokens")
print(f"TOTAL INPUT range:  {total_input_min}-{total_input_max} tokens")
print()
print("=== OUTPUT ===")
print(f"Expected output:    ~200-400 tokens (subject + body ~120 words + JSON overhead)")
print()
print("=== COST SUMMARY ===")
print(f"Input + Output avg: ~{total_input_avg + 300} tokens per mail")
print(f"For 106 remaining:  ~{int((total_input_avg + 300) * 106 / 1000)}k tokens total")