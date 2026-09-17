import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
MAIL_DIR = DATA_DIR / "emails"
LOG_DIR = PROJECT_DIR / "logs"

CONTACTS_FILE = DATA_DIR / "contacts.json"
POSTS_FILE = DATA_DIR / "posts.json"
STATUS_FILE = DATA_DIR / "status.json"
SKIPPED_FILE = DATA_DIR / "skipped.json"


def _load(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def _save(path: Path, data) -> None:
    for d in (DATA_DIR, MAIL_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ---------------------------------------------------------------- emails
_EMAIL_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+"
_EMAIL_DOMAIN = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_STRICT_EMAIL_RE = re.compile(
    rf"^{_EMAIL_LOCAL}@(?:(?:{_EMAIL_DOMAIN})\.)+(?P<tld>[a-z]{{2,6}})$"
)
_FIND_CAND_RE = re.compile(rf"{_EMAIL_LOCAL}@[A-Za-z0-9.\-]+")
_STRICT_EMAIL_TLD_RE = re.compile(
    rf"^{_EMAIL_LOCAL}@(?:(?:{_EMAIL_DOMAIN})\.)+(?:com|org|net|in|io|co|ai|dev|app|tech|"
    rf"me|info|biz|edu|uk|us|ca|au|de|fr|xyz|online)$"
)
# phone numbers glued to the front of an address (e.g. "+919024226200john@x.com")
_PHONE_LOCAL_RE = re.compile(r"^\+\d{10,}")


def clean_email(raw: str) -> str:
    """Normalize/validate one email; returns '' when it is unusable.

    Fixes OCR/mailto artifacts such as trailing words glued to the address
    ('x@gmail.comKnow') and rejects non-ASCII junk (mojibake, phone glue).
    """
    if not raw:
        return ""
    s = str(raw).strip()
    if not _STRICT_EMAIL_RE.match(s):
        lower = s.lower()
        if _STRICT_EMAIL_RE.match(lower):
            s = lower
        else:
            m = _FIND_CAND_RE.search(s)
            if not m:
                return ""
            cand = m.group(0)
            hit = ""
            for j in range(len(cand), 0, -1):
                p = cand[:j]
                if _STRICT_EMAIL_RE.fullmatch(p):
                    hit = p
                    break
            if not hit:
                for j in range(len(cand), 0, -1):
                    p = cand[:j].lower()
                    if _STRICT_EMAIL_TLD_RE.fullmatch(p):
                        hit = p
                        break
            if not hit:
                return ""
            s = hit
    if _PHONE_LOCAL_RE.match(s.split("@")[0]):
        return ""
    return s


def clean_emails(emails) -> list:
    out = []
    for e in emails or []:
        c = clean_email(e or "")
        if c and c not in out:
            out.append(c)
    return out


# ---------------------------------------------------------------- contacts
def load_contacts() -> dict:
    return _load(CONTACTS_FILE, {"emails": [], "phones": []})


def register_contacts(emails: list, phones: list) -> dict:
    """Add newly-seen contacts; returns (new_emails, new_phones)."""
    contacts = load_contacts()
    known_emails = set(contacts["emails"])
    known_phones = set(contacts["phones"])

    new_emails = [e for e in emails if e not in known_emails]
    new_phones = [p for p in phones if p not in known_phones]

    contacts["emails"] = sorted(known_emails | set(emails))
    contacts["phones"] = sorted(known_phones | set(phones))
    _save(CONTACTS_FILE, contacts)
    return {"emails": new_emails, "phones": new_phones}


def is_known(emails: list, phones: list) -> bool:
    contacts = load_contacts()
    known_emails = set(contacts["emails"])
    known_phones = set(contacts["phones"])
    return any(e in known_emails for e in emails) or any(p in known_phones for p in phones)


# ---------------------------------------------------------------- posts
def load_posts() -> list:
    return _load(POSTS_FILE, [])


def save_posts(posts: list) -> None:
    _save(POSTS_FILE, posts)


# ---------------------------------------------------------------- status
def load_status() -> dict:
    return _load(STATUS_FILE, {})


def save_status(status: dict) -> None:
    _save(STATUS_FILE, status)


# --------------------------------------------------------------- skipped
SKIP_CATEGORY_EMAIL = "missing_email"          # post had no email at all
SKIP_CATEGORY_ENTRY = "entry_level"            # intern/fresher/<=1yr role
SKIP_CATEGORY_PROFILE = "profile_missing"      # post needs info profile lacks
SKIP_CATEGORY_OTHER = "other"


def load_skipped() -> list:
    return _load(SKIPPED_FILE, [])


def save_skipped(skipped: list) -> None:
    _save(SKIPPED_FILE, skipped)


def log_skip(post: dict, category: str, reason: str, action: str = "") -> dict:
    """Append one skip record. If the same post_id+category already exists, updat it instead."""
    skipped = load_skipped()
    stamp = datetime.now().isoformat(timespec="seconds")
    record = {
        "timestamp": stamp,
        "post_id": post.get("post_id", ""),
        "author": post.get("author", ""),
        "emails": list(post.get("emails", []) or []),
        "phones": list(post.get("phones", []) or []),
        "category": category,
        "reason": reason,
        "action": action,
    }
    replaced = False
    for i, r in enumerate(skipped):
        if r.get("post_id") == record["post_id"] and r.get("category") == category:
            skipped[i] = record
            replaced = True
            break
    if not replaced:
        skipped.append(record)
    save_skipped(skipped)
    return record


def log(msg: str, scope: str = "app") -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    logfile = LOG_DIR / f"{scope}.log"
    with logfile.open("a", encoding="utf-8") as f:
        f.write(line + "\n")