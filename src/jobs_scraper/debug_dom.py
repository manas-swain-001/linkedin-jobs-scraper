import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parents[2] / ".browser_profile"
OUT = Path(__file__).resolve().parents[2] / "dom_dump.txt"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(user_data_dir=str(PROFILE_DIR), headless=False)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
    time.sleep(6)

    lines = ["=== INPUTS ==="]
    inputs = page.locator("input")
    for i in range(inputs.count()):
        el = inputs.nth(i)
        lines.append(
            f"#{i} tag={el.evaluate('e=>e.tagName')} type={el.get_attribute('type')} "
            f"aria={el.get_attribute('aria-label')} placeholder={el.get_attribute('placeholder')} "
            f"id={el.get_attribute('id')} role={el.get_attribute('role')} "
            f"class={el.get_attribute('class')} name={el.get_attribute('name')}"
        )

    lines.append("=== ROLE=SEARCHBOX / COMBOBOX ===")
    for role in ("searchbox", "combobox"):
        loc = page.locator(f'[role="{role}"]')
        for i in range(loc.count()):
            el = loc.nth(i)
            lines.append(
                f"[{role}] #{i} aria={el.get_attribute('aria-label')} placeholder={el.get_attribute('placeholder')} "
                f"tag={el.evaluate('e=>e.tagName')} class={el.get_attribute('class')}"
            )

    lines.append("=== TOP NAV LINKS QUIET ===")
    nav = page.locator("nav")
    for i in range(nav.count()):
        aria = nav.nth(i).get_attribute("aria-label")
        lines.append(f"nav#{i} aria-label={aria}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    context.close()