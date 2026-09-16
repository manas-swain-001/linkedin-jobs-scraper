import jobs_scraper.storage as s


def main():
    status = s.load_status()
    changed = 0
    for pid, rec in status.items():
        if rec.get("status") in ("ERROR", "GENERATED"):
            rec["status"] = "SCRAPED"
            rec.pop("skip_reason", None)
            rec.pop("dry_run_ok", None)
            changed += 1
    s.save_status(status)
    print(f"reset {changed} records to SCRAPED")
    print({k: v.get("status") for k, v in status.items()})


if __name__ == "__main__":
    main()