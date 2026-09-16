import time

from playwright.sync_api import sync_playwright

from jobs_scraper.common import (
    log,
    open_linkedin_session,
    run_search_to_posts,
    screenshot,
)

page: ... = None  # bound in main, referenced by helpers


def main() -> None:
    global page
    with sync_playwright() as p:
        context, page = open_linkedin_session(p)
        screenshot(page, "01_jobs_page")

        run_search_to_posts(page)
        screenshot(page, "04_posts_results")

        log(f"Final URL: {page.url}")
        log(f"Final page title: {page.title()}")
        log("Done. Closing in 20 seconds...")
        time.sleep(20)
        context.close()


if __name__ == "__main__":
    main()