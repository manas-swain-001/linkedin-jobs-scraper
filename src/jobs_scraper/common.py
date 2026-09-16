import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

LOGIN_URL = "https://www.linkedin.com/login"
JOBS_URL = "https://www.linkedin.com/jobs/"
SEARCH_QUERY = "Full Stack Developer, ReactJS Developer, NodeJS Developer"
POLL_INTERVAL_SECONDS = 5
PROJECT_DIR = Path(__file__).resolve().parents[2]
PROFILE_DIR = PROJECT_DIR / ".browser_profile"
LOG_FILE = PROJECT_DIR / "login_log.txt"
SCREENSHOT_DIR = PROJECT_DIR / "screenshots"
OUTPUT_DIR = PROJECT_DIR


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def screenshot(page, name: str) -> None:
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    try:
        page.screenshot(path=str(path), timeout=8000)
        log(f"Screenshot saved: {path}")
    except PlaywrightTimeoutError:
        log(f"Screenshot {name} timed out, skipping.")


def wait_for_url_contains(page, substring: str, timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if substring in page.url:
            return True
        page.wait_for_timeout(1000)
    return False


def open_linkedin_session(p):
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
    )
    page = context.pages[0] if context.pages else context.new_page()

    log("Opening LinkedIn...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")

    log("Waiting for you to sign in (checking every 5 seconds)...")
    while True:
        feed_url = None
        for tab in context.pages:
            log(f"Tab URL: {tab.url}")
            if "feed" in tab.url:
                feed_url = tab.url
                break
        if feed_url:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    log("Navigating to the Jobs page...")
    page.goto(JOBS_URL, wait_until="domcontentloaded")
    return context, page


def type_search_and_enter(page) -> None:
    log("Looking for the jobs search input...")
    search_input = page.locator('input[data-testid="typeahead-input"]').first
    search_input.wait_for(state="visible", timeout=15000)
    search_input.click()
    search_input.fill(SEARCH_QUERY)
    log(f"Typed query: {SEARCH_QUERY}")
    search_input.press("Enter")
    if wait_for_url_contains(page, "/jobs/search", timeout_s=45):
        log("On the Jobs search results page.")
    else:
        log(f"WARNING: expected /jobs/search in URL, got: {page.url}")


def click_jobs_filter(page) -> None:
    log("Clicking the first filter chip (Jobs)...")
    jobs_filter = page.locator('div[role="radio"][aria-label="Filter by Jobs"]').first
    jobs_filter.wait_for(state="visible", timeout=15000)
    jobs_filter.click()
    page.wait_for_timeout(2000)
    log("Clicked Jobs filter, dropdown should be open.")


def click_posts_option(page) -> None:
    log("Looking for the 'Posts' option in the dropdown...")

    selectors = [
        'div[role="option"]:has-text("Posts")',
        'li[role="option"]:has-text("Posts")',
        'a[role="option"]:has-text("Posts")',
        'ul[role="listbox"] li:has-text("Posts")',
    ]
    clicked = False
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=3000)
            loc.click()
            log(f"Clicked Posts via selector: {sel}")
            clicked = True
            break
        except PlaywrightTimeoutError:
            continue

    if not clicked:
        log("Selector route failed; trying text-scoped clicking...")
        candidates = page.get_by_text("Posts", exact=True)
        count = candidates.count()
        log(f"Found {count} element(s) with exact text 'Posts'.")
        for i in reversed(range(count)):
            el = candidates.nth(i)
            try:
                el.wait_for(state="visible", timeout=1500)
                el.click()
                clicked = True
                log("Clicked the visible 'Posts' element.")
                break
            except PlaywrightTimeoutError:
                continue

    if not clicked:
        log("ERROR: could not click the Posts option.")

    page.wait_for_timeout(3000)


def run_search_to_posts(page) -> None:
    log("Searching for developer posts...")
    type_search_and_enter(page)
    click_jobs_filter(page)
    click_posts_option(page)
    if wait_for_url_contains(page, "/search/results/content", timeout_s=45):
        log("On the Posts search results page.")
    else:
        log(f"WARNING: expected /search/results/content in URL, got: {page.url}")