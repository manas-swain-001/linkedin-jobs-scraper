import json
import re
import time

import requests

from jobs_scraper import storage
from jobs_scraper.filters import is_job_seeker_post
from jobs_scraper.profile import load_profile, profile_to_text

# Canonical tech names -> the skill as spelled in the candidate profile (or a known alias).
SKILL_ALIASES = {
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "python": "python",
    "react": "react.js",
    "react.js": "react.js",
    "reactjs": "react.js",
    "react native": "react native",
    "reactnative": "react native",
    "next": "next.js",
    "next.js": "next.js",
    "nextjs": "next.js",
    "node": "node.js",
    "node.js": "node.js",
    "nodejs": "node.js",
    "express": "express.js",
    "express.js": "express.js",
    "expressjs": "express.js",
    "nestjs": "nestjs",
    "nest": "nestjs",
    "rest api": "rest apis",
    "rest apis": "rest apis",
    "restapis": "rest apis",
    "microservices": "microservices",
    "langchain": "langchain",
    "langgraph": "langgraph",
    "ai agents": "ai agents",
    "llm": "llm integration",
    "llm integration": "llm integration",
    "rag": "rag",
    "prompt engineering": "prompt engineering",
    "tool calling": "tool calling",
    "mysql": "mysql",
    "mongodb": "mongodb",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "redis": "redis",
    "vector databases": "vector databases",
    "vector db": "vector databases",
    "aws": "aws",
    "docker": "docker",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "git": "git",
    "github": "github",
    "firebase": "firebase",
}

# Common technologies seen in recruiter posts that the candidate does NOT know.
UNKNOWN_TECH = [
    "java", "spring boot", "spring", "php", "laravel", "codeigniter",
    "go", "golang", "postgresql", "postgres", "kubernetes", "k8s", "gke",
    "angular", "vue", "vue.js", "vuejs", ".net", ".net core", "django", "flask",
    "tensorflow", "pytorch", "elasticsearch", "kafka", "sap", "strapi",
    "opentelemetry", "azure", "gcp", "c#", "ruby", "rails", "rust",
    "swift", "kotlin", "flutter", "graphql", "redux", "tailwind",
    "terraform", "selenium", "cypress", "jenkins", "gitlab", "airflow",
    "rabbitmq", "snowflake", "databricks", "spark", "sql server", "oracle",
    "hibernate", "jsp", "servlet", "jquery", "bootstrap", "webpack", "vite",
    "jest", "mocha", "chai", "jira", "confluence", "bitbucket", "grpc",
    "serverless", "lambda", "s3", "dynamodb", "memcached", "neo4j",
    "cassandra", "tableau", "power bi", "excel", "uipath", "blueprism",
    "opencv", "nlp", "onnx", "mlflow", "kubeflow", "chatgpt", "claude",
    "copilot", "cursor", "antigravity", "openai", "aem", "adobe",
    "splunk", "new relic", "datadog", "prometheus", "grafana", "istio",
    "web3", "solidity", "ethereum", "blockchain", "typescript native",
    "next.js native", "react query", "zustand",
]


def _norm_skills() -> set[str]:
    """Canonical skill names known by the candidate, derived from profile.json."""
    profile = load_profile()
    known = set()
    for name in profile.get("skills", {}):
        known.add(name.lower())
        known.update(a for a, canon in SKILL_ALIASES.items() if canon == name.lower())
    return known


def _techs_in_text(text: str) -> set[str]:
    """Return canonical tech names found in a text (case-insensitive)."""
    low = text.lower()
    found = set()
    for alias, canon in SKILL_ALIASES.items():
        if _word_contains(low, alias):
            found.add(canon)
    for term in UNKNOWN_TECH:
        if _word_contains(low, term):
            found.add(term)
    return found


def _word_contains(low: str, token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    if "." in token or "/" in token or "#" in token:
        escaped = re.escape(token)
        return re.search(r"(?<![a-z0-9])" + escaped, low) is not None
    return re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", low) is not None


OPTIONAL_HINTS = ("good to have", "good-to-have", "nice to have", "nice-to-have", "preferred",
                  "is a plus", "a plus", "desired", "added advantage", "optional", "not mandatory",
                  "familiarity with", "would be great", "bonus", "plus points", "added confidence")


def _required_of_unknown(content: str, unknown: list) -> set:
    """Return the subset of `unknown` technologies the post actually REQUIRES
    (vs. only mentions in optional/preferred context)."""
    low = content.lower()
    required = set(unknown)
    for clause in re.split(r"[.!?;:]\s+|\n+", low):
        if any(h in clause for h in OPTIONAL_HINTS):
            required -= _techs_in_text(clause)
    return required


def _role_from_intro(body: str) -> str:
    m = re.search(r"applying for the\s+(.+?)\s+position\.?", body, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _build_subject(body: str, fallback_role: str = "") -> str:
    """Enforce the exact subject format: Application for [Role] - Manas Kumar Swain - Immediate Joiner."""
    import json as _json

    role = _role_from_intro(body) or fallback_role
    role = re.sub(r"\s{2,}", " ", role).strip(" \t.,;:-")
    if not role:
        role = "the Position"
    return f"Application for {role} - Manas Kumar Swain - Immediate Joiner"


def _fix_layout(body: str) -> str:
    """Normalize a generated body to the exact standard layout (guarantees blank-line structure)."""
    text = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return body

    after_dear = text.split("Dear", 1)[1].strip() if "Dear" in text else ""
    m_name = re.match(r"([^,\n]{1,50})", after_dear)
    greeting = f"Dear {m_name.group(1).strip().rstrip(',')}," if m_name else "Dear Recruiter,"

    m_intro = re.search(r"I am Manas Kumar Swain, and I am applying for the (.+?) position\.?", text, re.DOTALL)
    if not m_intro:
        return ""
    intro = f"I am Manas Kumar Swain, and I am applying for the {m_intro.group(1).strip()} position."

    m_resume = re.search(r"attached my resume for your review", text, re.IGNORECASE)
    mid_end = m_resume.start() if m_resume else len(text)
    if m_resume is None:
        m_best = re.search(r"Best regards", text)
        if m_best:
            mid_end = m_best.start()

    middle = text[m_intro.end():mid_end].strip()
    middle = re.sub(r"\s+", " ", middle).strip(" \t.,;")
    middle = re.sub(r"\s+I have\s*$", "", middle).strip()
    middle = middle.rstrip("I have").strip()
    if middle.endswith("I have"):
        middle = middle[:-len("I have")].strip()
    middle = re.sub(r"\s+", " ", middle).strip(" \t.,;")
    middle = _clean_notice_period(middle)
    if middle and not middle.endswith((".", "!", "?", ":", ";", ",")):
        middle = middle.rstrip(", ") + "."

    lines = [greeting, "", intro]
    if middle:
        lines += ["", middle]
    lines += ["", "I have attached my resume for your review.", "", "Best regards,",
              "Manas Kumar Swain", "+91 9861053987", "manas.swain247@gmail.com",
              "https://linkedin.com/in/manaskumarswain/"]
    return "\n".join(lines)


def _remove_sentences_with(text: str, terms) -> str:
    """Drop whole sentences that mention any of `terms` (used to purge optional fabricated skills)."""
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    keep = [s for s in sents if not any(_word_contains(s.lower(), t) for t in terms)]
    return " ".join(keep).strip()


def _clean_notice_period(text: str) -> str:
    """Redact forbidden notice-period phrasings like 'with 0 days notice period' / '0 days' notice'."""
    text = re.sub(r"\s*(?:with\s+)?\(?\s*[,.]?\s*0[-\s]?days?(?:\s*['’]s?|\s+of)?\s*notice\s*periods?\.?\)*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*(?:with\s+)?\(?\s*[,.]?\s*0[-\s]?day['’]?\s*notice\s*\.?\)*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*,", ",", text)
    text = re.sub(r"\bwith\s+(?=(?:my|i am|i'm|am)\b)", "with ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip().rstrip(",").strip().rstrip("with").strip()


def _is_truncated(body: str) -> bool:
    """Return True if the standard structure (greeting + intro + resume line + middle) is incomplete."""
    if not body:
        return True
    if "Dear" not in body or "I am Manas Kumar Swain" not in body or "resume for your review" not in body:
        return True
    before_resume = body.split("I have attached my resume")[0]
    before_resume = re.sub(r"\n+", " ", before_resume).strip()
    if not before_resume:
        return True
    return False


def _salvage_truncation(body: str) -> str:
    """Cut the body back to the last complete sentence to salvage truncated output."""
    before_resume = body.split("I have attached my resume")[0] if "I have attached my resume" in body else body
    before_resume = re.sub(r"\n+", " ", before_resume).strip()
    matches = list(re.finditer(r".[.!?]", before_resume))
    if not matches:
        return ""
    cut = matches[-1].end()
    return before_resume[:cut]

SYSTEM_PROMPT = """You are an expert recruiter-facing email writer. A candidate wants to apply for jobs a recruiter posted on LinkedIn.

You are given:
1. CANDIDATE_PROFILE: the candidate's real facts (name, CTC, location, notice period, skills, etc.). The candidate's technologies are listed under "Skills:" — those are the EXACT technologies the candidate has.
2. RECRUITER_POST: the text of the recruiter's job post.

Your job: write ONE short, simple, professional email from the candidate to the recruiter, OR decide the post is not worth applying to.

Rules:
- Read the recruiter's post carefully. Identify every detail the post explicitly asks applicants to provide (e.g. current CTC, expected CTC, location, years of experience, notice period, availability to join, skills, day/time of availability, whether night shift is OK, etc.).
- The email must cover ONLY the details the post asks for, using the candidate's real values from CANDIDATE_PROFILE. Do NOT stuff in facts the post did not ask about.
- NEVER invent or guess any number the profile does not contain (CTC, notice period, experience, etc.).

SKILL MATCH RULE (decides whether the email is written):
- Extract the technologies the post requires. Compare each with the candidate's "Skills:" list.
- If at least 50% of the post's required technologies are present in the candidate's Skills list, WRITE THE EMAIL. Mention ONLY the matched technologies in the email. Never mention a technology that is not in the candidate's Skills list.
- If fewer than 50% of the post's required technologies are present in the candidate's Skills list, DO NOT write the email. Set subject and body to empty strings "", and put the technologies the candidate lacks in "missing_skills".
- If the post does NOT strictly require specific technologies, write the email normally.

MISSING REQUIRED FIELDS (only things the candidate simply cannot satisfy that are NOT technologies):
- If the post requires a value the profile does not contain AND the candidate cannot honestly provide it (e.g. minimum years of experience much higher than the profile, a specific degree the candidate does not have, in-office-only work the candidate cannot do, contract-only when the profile says full-time only, mandatory in-person interviews), list it in "missing_required_fields".
- If the profile already contains or can answer a requirement, never put it in "missing_required_fields" — answer it in the email.

Mandatory content rules:
- NEVER mention in-person interviews, in-person discussions, onsite meetings, walk-ins, or any availability to meet in person. The candidate is based in Bhubaneswar and does not attend physical interviews. If a post asks for in-person interaction, do not promise it; simply omit it from the email.
- When saying the candidate can join quickly, write ONLY "immediate joiner". NEVER write "0 days notice period", "0-day notice", "(0 days)", or any parenthesized notice-period note.
- Do NOT mention the notice period wording inside brackets.
- Never call the candidate an intern, fresher, or entry-level. The candidate is an experienced professional.

MANDATORY EMAIL FORMAT (follow exactly when writing an email, in this exact order and layout):
- Line 1: "Dear <Recruiter Name>," then press enter (new line).
- Line 2: "I am Manas Kumar Swain, and I am applying for the <Position Name> position." where <Position Name> is the job title from the recruiter post. End the sentence with a full stop, then press enter (new line).
- Lines 3-4: ONE or TWO short paragraphs (max ~60 words total) whose CONTENT MUST BE WRITTEN FRESH FOR THIS POST. Cover ONLY the specific details this post asked for (e.g. if it asks for current/expected CTC, give the real CTC; if it asks for notice/joining, say immediate joiner; if it asks for location/relocation, state it; if it asks which skills, name the matching skills from the profile; if it asks about shifts/days, state availability). Write different words for every post — NEVER use the same sentence pattern twice. Skip any fact the post did not ask about. Blank line before and after this section.
- Next line: "I have attached my resume for your review."
- Sign-off block, each value on its own line, with a blank line before it:
  Best regards,
  Manas Kumar Swain
  +91 9861053987
  manas.swain247@gmail.com
  https://linkedin.com/in/manaskumarswain/

LAYOUT SKELETON ONLY — do not copy these sentences, write your own fresh words for every post:

Dear <Recruiter>,

I am Manas Kumar Swain, and I am applying for the <Role> position.

<one or two short paragraphs written fresh, answering only what THIS post asks>

I have attached my resume for your review.

Best regards,
Manas Kumar Swain
+91 9861053987
manas.swain247@gmail.com
https://linkedin.com/in/manaskumarswain/

Return ONLY a JSON object with exactly this schema:
{
  "subject": "string in exactly this format: Application for [Role] - Manas Kumar Swain - Immediate Joiner  (replace [Role] with the exact job title from the post)",
  "body": "string",
  "missing_required_fields": ["non-technology requirements the candidate cannot satisfy"],
  "missing_skills": ["post-required technologies NOT in the candidate's Skills list"],
  "notes": "any short note (or empty string)"
}"""


class _FabricatedSkills(Exception):
    pass


def generate_for_post(post: dict, profile_text: str) -> dict:
    import json as _json

    content = post.get("content", "") or ""
    known = _norm_skills()
    all_techs = _techs_in_text(content)
    known_matched = sorted(t for t in all_techs if t in known)
    unknown_mentioned = sorted(t for t in all_techs if t not in known)

    ratio = len(known_matched) / len(all_techs) if all_techs else 1.0
    if ratio < 0.5:
        return {
            "_skip_reason": f"less_than_50%_skill_match ({len(known_matched)}/{len(all_techs)}): "
                            f"{', '.join(unknown_mentioned)}"
        }

    allowed_list = " | ".join(sorted(known))
    banned_list = " | ".join(unknown_mentioned)

    prompt = f"""CANDIDATE_PROFILE:
```
{profile_text}
```

RECRUITER_POST (author: {post['author']}):
```
{content}
```

The candidate knows EXACTLY these technologies and nothing else:
{allowed_list}

The candidate DOES NOT know these technologies and must NEVER mention them in the email:
{banned_list if banned_list else '(none - everything mentioned is fine)'}

Write the email now. Only technologies from the allowed list may appear in the email. Return ONLY JSON matching the schema described in the system prompt."""

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3.1:8b",
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "format": "json",
        "options": {"temperature": 0.3, "num_predict": 1500},
        "stream": False,
    }

    required_unknown = _required_of_unknown(content, unknown_mentioned)
    last_error = ""
    last_optional: dict | None = None
    last_optional_terms: list = []
    last_body_raw: str | None = None
    for attempt in range(4):
        try:
            resp = requests.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("response") or "").strip()
            text = text.removeprefix("```json").removesuffix("```").strip()
            result = _json.loads(text)

            combined = (result.get("subject", "") + " " + result.get("body", "")).lower()
            fabricated = [t for t in unknown_mentioned if _word_contains(combined, t)]
            if fabricated:
                hard_fab = sorted(t for t in fabricated if t in required_unknown)
                if hard_fab:
                    raise _FabricatedSkills(
                        ", ".join(hard_fab) + " [required by post; candidate lacks it]"
                    )
                last_error = f"fabricated_optional_skills: {', '.join(fabricated)}"
                last_optional, last_optional_terms = result, fabricated
                payload["prompt"] = prompt + (
                    "\n\nYou previously mentioned optional skills the candidate does NOT have: "
                    + ", ".join(fabricated)
                    + ". These are NOT in the candidate's skills. Rewrite the email omitting them completely."
                )
                storage.log(f"Ollama attempt {attempt + 1}/4 has optional-skill mention ({', '.join(fabricated)}); retrying to omit them")
                time.sleep(2)
                continue

            laid = _fix_layout(result.get("body", ""))
            if _is_truncated(laid):
                last_body_raw = result.get("body", "")
                last_error = "truncated_body"
                storage.log(f"Ollama attempt {attempt + 1}/4 truncated body; retrying")
                payload["prompt"] = prompt + (
                    "\n\nYour previous email was cut off mid-sentence. Rewrite it completely, making sure every sentence ends with a full stop and the email is complete."
                )
                time.sleep(2)
                continue

            result["subject"] = _build_subject(laid, post.get("title", ""))
            result["body"] = laid
            return result
        except _FabricatedSkills as exc:
            last_error = f"fabricated_skills: {exc}"
            storage.log(f"Ollama attempt {attempt + 1}/4 rejected (fabricated skill: {exc})")
        except Exception as exc:
            last_error = str(exc)
            storage.log(f"Ollama attempt {attempt + 1}/4 failed: {exc}")
        time.sleep(2)

    if last_optional is not None:
        clean_body = _remove_sentences_with(last_optional.get("body", ""), last_optional_terms)
        laid = _fix_layout(clean_body)
        if clean_body.strip() and not _is_truncated(laid):
            last_optional["body"] = laid
            last_optional["subject"] = _build_subject(laid, post.get("title", ""))
            storage.log(f"Stripped optional-skill mentions ({', '.join(last_optional_terms)}) and accepted the mail.")
            return last_optional
        last_error = f"fabricated_optional_skills: {', '.join(last_optional_terms)} (unsalvageable)"

    if last_body_raw:
        salvaged = _fix_layout(_salvage_truncation(last_body_raw))
        if salvaged and not _is_truncated(salvaged):
            result = {"subject": _build_subject(salvaged, post.get("title", "")), "body": salvaged}
            storage.log("Salvaged truncated body to last complete sentence and accepted the mail.")
            return result

    return {"_skip_reason": f"generation_error: {last_error}"}


def is_entry_level(content: str) -> str | None:
    """Return a reason if the post is an entry-level/intern/fresher role (<2 years), else None."""
    import re

    low = content.lower()
    for word in ["intern", "internship", "fresher", "freshers", "entry-level", "entry level", "trainee"]:
        if re.search(r"\b" + re.escape(word) + r"\b", low):
            return f"entry_level_role: mentions {word}"
    m = re.search(r"(?:up\s*to|less\s*than|0\s*to|0\s*-|0\s*–)\s*(\d+)\s*(?:year|\byr)", low)
    if m and int(m.group(1)) <= 1:
        return f"entry_level_role: max {m.group(1)} year experience"
    m = re.search(r"\b0\s*(?:-\s*|\s*to\s*|\s*–\s*)1\s*(?:year|\byr)", low)
    if m:
        return "entry_level_role: 0-1 year experience"
    return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate mails for scraped posts using Ollama.")
    parser.add_argument("--limit", type=int, default=0, help="Max mails to generate (0 = unlimited)")
    args = parser.parse_args()

    storage.log("=== MAIL GENERATION RUN START (Ollama llama3.1:8b) ===")
    profile = load_profile()
    profile_text = profile_to_text(profile)
    posts = storage.load_posts()
    status = storage.load_status()

    pending = [p for p in posts
               if status.get(p["post_id"], {}).get("status") in (None, "SCRAPED", "PENDING")]

    if not pending:
        storage.log("No pending posts to generate mail for.")
        return

    storage.log(f"Pending: {len(pending)} posts | limit: {args.limit or 'unlimited'}")

    outputs_dir = storage.MAIL_DIR
    outputs_dir.mkdir(parents=True, exist_ok=True)

    generated_count = 0
    for post in pending:
        if args.limit and generated_count >= args.limit:
            storage.log(f"Reached limit of {args.limit}. Stopping.")
            break

        pid = post["post_id"]
        record = status.setdefault(pid, {})

        reason = is_entry_level(post.get("content", ""))
        if reason:
            record["status"] = "SKIPPED"
            record["skip_reason"] = reason
            record["post_id"] = pid
            record.pop("mail_file", None)
            storage.log_skip(post, storage.SKIP_CATEGORY_ENTRY, reason,
                             action="intern/fresher role; no action needed")
            storage.log(f"SKIPPED {post['author']} | reason: {reason}")
            continue

        if is_job_seeker_post(post.get("content", "")):
            reason = "job_seeker_post"
            record["status"] = "SKIPPED"
            record["skip_reason"] = reason
            record["post_id"] = pid
            record.pop("mail_file", None)
            storage.log_skip(post, storage.SKIP_CATEGORY_OTHER, reason,
                             action="author posted their own open-to-work profile; do NOT apply back to them")
            storage.log(f"SKIPPED {post['author']} | reason: {reason} (job seeker, not a recruiter)")
            continue

        try:
            result = generate_for_post(post, profile_text)
        except Exception as exc:
            record["status"] = "ERROR"
            record["skip_reason"] = f"generation_error: {exc}"
            storage.log(f"ERROR {pid} {post['author']}: {exc}")
            continue

        if result.get("_skip_reason"):
            reason = result["_skip_reason"]
            record["status"] = "SKIPPED"
            record["skip_reason"] = reason
            record["post_id"] = pid
            record.pop("mail_file", None)
            storage.log_skip(post, storage.SKIP_CATEGORY_OTHER, reason,
                             action="post requires technologies the candidate does not have or generation failed")
            storage.log(f"SKIPPED {post['author']} | reason: {reason}")
            continue

        missing = result.get("missing_required_fields") or []
        missing_skills = result.get("missing_skills") or []
        if missing:
            record["status"] = "SKIPPED"
            record["skip_reason"] = f"missing: {', '.join(missing)}"
            record["post_id"] = pid
            record.pop("mail_file", None)
            storage.log_skip(post, storage.SKIP_CATEGORY_PROFILE,
                             f"post requires: {', '.join(missing)}",
                             action="add these fields to profile.json then reset status to SCRAPED to retry")
            storage.log(f"SKIPPED {post['author']} | reason: {record['skip_reason']}")
            continue

        subject = result.get("subject", "").strip()
        body = result.get("body", "").strip()
        if not subject or not body:
            reason = f"less_than_50%_skill_match: {', '.join(missing_skills)}" if missing_skills else "empty_subject_or_body"
            record["status"] = "SKIPPED"
            record["skip_reason"] = reason
            record["post_id"] = pid
            record.pop("mail_file", None)
            storage.log_skip(post, storage.SKIP_CATEGORY_OTHER, reason,
                             action="post requires technology the candidate does not have")
            storage.log(f"SKIPPED {post['author']} | reason: {reason}")
            continue

        email_target = (post.get("emails") or [""])[0]
        if not email_target:
            record["status"] = "SKIPPED"
            record["skip_reason"] = "missing: email"
            record["post_id"] = pid
            record.pop("mail_file", None)
            storage.log_skip(post, storage.SKIP_CATEGORY_EMAIL,
                             "no email found in post (phone-only)",
                             action="find the email manually (LinkedIn/company site) and add it to the post record to retry")
            storage.log(f"SKIPPED {post['author']}: no email (phone-only listed).")
            continue

        filename = outputs_dir / f"{pid}.txt"
        filename.write_text(f"TO: {email_target}\nSUBJECT: {subject}\n\n{body}\n", encoding="utf-8")

        record["status"] = "GENERATED"
        record["post_id"] = pid
        record["to_email"] = email_target
        record["author"] = post["author"]
        record["mail_file"] = str(filename.relative_to(storage.PROJECT_DIR))
        record["generated_at"] = _now()
        record.pop("skip_reason", None)
        generated_count += 1

        storage.log(f"GENERATED [{generated_count}] {post['author']} -> {email_target}")
        safe_subject = subject.encode("ascii", "ignore").decode("ascii")
        safe_body = body.encode("ascii", "ignore").decode("ascii")
        print(f"\n----- MAIL FOR: {post['author']} <{email_target}> -----")
        print(f"Subject: {safe_subject}")
        print(safe_body)
        print("--------------------------------------------------------------\n")

    storage.save_status(status)
    storage.log(f"MAIL GENERATION SUMMARY: pending={len(pending)} generated={generated_count} "
                f"skipped={len(pending) - generated_count}")
    storage.log("=== MAIL GENERATION RUN END ===")


def _now() -> str:
    import time as _time
    from datetime import datetime as _dt

    return _dt.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    main()