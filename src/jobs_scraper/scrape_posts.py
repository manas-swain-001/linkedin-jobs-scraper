import difflib
import hashlib
import json
import re
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from jobs_scraper.common import (
    log,
    open_linkedin_session,
    run_search_to_posts,
)
from jobs_scraper import storage
from jobs_scraper.filters import is_job_seeker_post

POST_CARD = 'div[role="listitem"][componentkey*="FLAGSHIP_SEARCH"]'
MAX_SCROLLS = 400  # hard safety cap; the 30-min timer is the real limit
RUN_DURATION_MINUTES = 30
MAX_POSTS = 100  # cap: never collect more than this many posts per run
REPOST_SIM_MIN = 0.88  # if new post content is ~>=88% similar to an already-collected post for the same contact, treat as repost
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?:(?:\+|00\s?)91[-\s.]?)?(?:[6-9]\d{9}|\(?\d{3,5}\)?[-\s.]\d{3,5}[-\s.]\d{3,5})"
)
TIME_RE = re.compile(r"(Just now|\d+\s*(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)?\s*ago|\b\d+[wdhmy]\b)")


def post_id(author_url: str, content: str) -> str:
    return hashlib.sha256(f"{author_url}||{content}".encode()).hexdigest()[:20]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def extract_card(card) -> dict | None:
    content_span = card.locator('span[data-testid="expandable-text-box"]')
    content = ""
    if content_span.count():
        content = content_span.first.evaluate("el => el.textContent") or ""
    content = re.sub(r"\s*[….]+\s*more\s*$", "", content, flags=re.IGNORECASE).strip()
    if not content:
        return None

    emails = []
    mailto_links = card.locator('a[href^="mailto:"]')
    for i in range(mailto_links.count()):
        href = mailto_links.nth(i).get_attribute("href") or ""
        addr = href.replace("mailto:", "").split("?")[0].strip()
        if EMAIL_RE.fullmatch(addr):
            emails.append(addr)
    for m in EMAIL_RE.finditer(content):
        if m.group(0) not in emails:
            emails.append(m.group(0))

    phones = []
    for m in PHONE_RE.finditer(content):
        candidate = m.group(0)
        candidate = re.sub(r"[^0-9+]", "", candidate)
        if candidate not in phones:
            phones.append(candidate)

    if not emails and not phones:
        return None

    author_name = ""
    author_url = ""
    in_links = card.locator('a[href*="/in/"]').evaluate_all(
        "els => els.map(e => ({ href: e.href, text: e.textContent || '' }))"
    )
    for link in in_links:
        name = re.sub(r"\s+", " ", link["text"]).strip()
        if name:
            author_name = name.split("\n")[0].strip() or name
            author_url = link["href"]
            break

    card_text = card.inner_text()
    ts = ""
    tm = TIME_RE.search(card_text)
    if tm:
        ts = tm.group(0).strip()

    return {
        "author": author_name,
        "author_url": author_url,
        "time_posted": ts,
        "content": content,
        "emails": emails,
        "phones": phones,
    }


def main() -> None:
    deadline = time.time() + RUN_DURATION_MINUTES * 60
    storage.log("=== SCRAPE RUN START ===")

    existing = storage.load_posts()
    existing_ids = {p["post_id"] for p in existing}
    # content corpus per contact for repost detection (same recruiter, near-identical text)
    repost_corpus: dict[str, list[str]] = {}
    for p in existing:
        contents = [_norm(p.get("content", ""))]
        for key in (p.get("emails") or []) + (p.get("phones") or []):
            repost_corpus.setdefault(key, []).extend(contents)

    with sync_playwright() as p:
        context, page = open_linkedin_session(p)
        run_search_to_posts(page)

        seen_keys = set()
        seen_fps = set()
        new_posts = []
        seen_unknown_posts = 0
        scroll_attempts = 0

        while time.time() < deadline and scroll_attempts < MAX_SCROLLS:
            cards = page.locator(POST_CARD)
            count = cards.count()
            storage.log(f"cards={count} new={len(new_posts)} scroll={scroll_attempts}")

            for i in range(count):
                card = cards.nth(i)
                key = card.get_attribute("componentkey") or ""
                if key and key in seen_keys:
                    continue
                if key:
                    seen_keys.add(key)

                data = None
                try:
                    data = extract_card(card)
                except Exception as exc:
                    storage.log(f"extract error card {i}: {exc}")
                    continue
                if not data:
                    continue

                if is_job_seeker_post(data["content"]):
                    storage.log(f"SKIP job-seeker post by {data['author']} (open-to-work profile, not a recruiter)")
                    continue

                fp = f"{data['author_url']}||{data['content'][:150]}"
                if fp in seen_fps:
                    continue

                pid = post_id(data["author_url"], data["content"])
                if pid in existing_ids or pid in seen_fps:
                    continue  # exact same post already collected in this or a past run

                # repost guard: a NEW post from the SAME recruiter is allowed, but skip if
                # the text is ~identical to something we already have from that contact
                norm_content = _norm(data["content"])
                is_repost = False
                for key in set((data["emails"] or []) + (data["phones"] or [])):
                    for old in repost_corpus.get(key, []):
                        if _similar(norm_content, old) >= REPOST_SIM_MIN:
                            storage.log(
                                f"SKIP repost by {data['author']} ({key}): text ~{_similar(norm_content, old):.0%} similar "
                                f"to an existing post"
                            )
                            is_repost = True
                            break
                    if is_repost:
                        break
                if is_repost:
                    continue

                seen_fps.add(fp)
                seen_keys.add(key)
                for key in set((data["emails"] or []) + (data["phones"] or [])):
                    repost_corpus.setdefault(key, []).append(norm_content)

                new_posts.append({
                    "post_id": pid,
                    "author": data["author"],
                    "author_url": data["author_url"],
                    "time_posted": data["time_posted"],
                    "content": data["content"],
                    "emails": data["emails"],
                    "phones": data["phones"],
                    "scraped_at": datetime.now().isoformat(timespec="seconds"),
                    "status": "SCRAPED",
                    "skip_reason": "",
                })
                storage.log(f"NEW [{len(new_posts)}] {data['author']} | {data['emails'] or data['phones']}")
                if len(new_posts) >= MAX_POSTS:
                    storage.log(f"Reached max posts ({MAX_POSTS}). Stopping scrape.")
                    break

            if time.time() >= deadline or len(new_posts) >= MAX_POSTS:
                break

            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(2500)
            scroll_attempts += 1

        storage.log(f"Scrape run finished. New posts collected: {len(new_posts)}")

        fresh = [p for p in new_posts if p["post_id"] not in existing_ids]
        storage.save_posts(existing + fresh)
        storage.log(f"Saved {len(fresh)} new posts to data/posts.json (total {len(existing) + len(fresh)}).")

        context.close()
    storage.log("=== SCRAPE RUN END ===")


if __name__ == "__main__":
    main()