import time

from playwright.sync_api import sync_playwright

from jobs_scraper.common import (
    log,
    open_linkedin_session,
    run_search_to_posts,
    screenshot,
)

POST_CARD = 'div[role="listitem"][componentkey*="FLAGSHIP_SEARCH"]'


def main() -> None:
    with sync_playwright() as p:
        context, page = open_linkedin_session(p)
        run_search_to_posts(page)
        page.wait_for_timeout(3000)

        cards = page.locator(POST_CARD)
        log(f"Total cards: {cards.count()}")

        tested = 0
        for i in range(cards.count()):
            card = cards.nth(i)
            box = card.locator('span[data-testid="expandable-text-box"]')
            btn = card.locator('button[data-testid="expandable-text-button"]')
            if box.count() == 0:
                continue
            tested += 1
            before = box.first.evaluate("el => el.textContent") or ""
            log(f"--- Card {i}: text length BEFORE click = {len(before)}; 'more' button visible = {btn.count() > 0}")

            if btn.count():
                try:
                    btn.first.click()
                    page.wait_for_timeout(1500)
                except Exception as exc:
                    log(f"Click failed: {exc}")
                after = box.first.evaluate("el => el.textContent") or ""
                log(f"Card {i}: text length AFTER click = {len(after)}")
                log(f"Card {i}: text changed after click = {before != after}")
                tag = "full" if len(after) >= len(before) else "shortened"
                log(f"Card {i}: same? tail-before: ...{before[-60:]!r}")
                log(f"Card {i}: same? tail-after : ...{after[-60:]!r}")

            if tested >= 3:
                break

        screenshot(page, "08_expand_test")
        log("Done. Closing in 8 seconds...")
        time.sleep(8)
        context.close()


if __name__ == "__main__":
    main()