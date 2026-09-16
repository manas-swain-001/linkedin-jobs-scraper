import argparse
import subprocess
import sys

from jobs_scraper import storage


def _run(module: str, extra: list | None = None) -> None:
    cmd = [sys.executable, "-m", module] + (extra or [])
    storage.log(f"step: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def run_cycle(send_mode: str, send_interval: int, send_to: str = "") -> None:
    storage.log(f"=== AUTO PIPELINE STARTED (send={send_mode}, interval={send_interval}s) ===")

    status = storage.load_status()
    posts = storage.load_posts()
    pending = [p for p in posts
               if status.get(p["post_id"], {}).get("status") in (None, "SCRAPED", "PENDING")]
    storage.log(f"Found {len(posts)} total posts, {len(pending)} pending (scraped but not generated/sent).")

    if pending:
        _run("jobs_scraper.generate_mails")
    else:
        storage.log("No pending posts. Scraping LinkedIn (max 30 min OR 100 jobs, whichever comes first)...")
        _run("jobs_scraper.scrape_posts")
        _run("jobs_scraper.generate_mails")

    if send_mode != "skip":
        cmd = [sys.executable, "-m", "jobs_scraper.send_mails", "--mode", send_mode,
               "--interval", str(send_interval)]
        if send_to:
            cmd += ["--to", send_to]
        storage.log(f"step: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    storage.log("=== AUTO PIPELINE ENDED ===")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto pipeline: process pending scraped mails first; if none, scrape "
                    "(30 min or 100 jobs), then generate + send."
    )
    parser.add_argument(
        "--mode",
        choices=["preview", "dry-run", "live", "skip"],
        default="live",
        help="How to send generated mails (skip = generate only, no sending). Default: live",
    )
    parser.add_argument("--to", default="", help="Override recipient (dry-run testing only)")
    parser.add_argument(
        "--interval",
        type=int,
        default=120,
        help="Seconds between sent mails (default 120)",
    )
    args = parser.parse_args()

    run_cycle(args.mode, args.interval, args.to)


if __name__ == "__main__":
    main()