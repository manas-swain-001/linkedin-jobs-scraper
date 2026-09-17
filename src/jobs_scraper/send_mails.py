import argparse
import json
import smtplib
import time
from datetime import datetime
from pathlib import Path

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from jobs_scraper import storage

SEND_INTERVAL_SECONDS = 60  # 1 minute between live/dry-run sends
RESUME_PATTERNS = ["Resume*.pdf", "resume*.pdf", "CV*.pdf", "cv*.pdf"]


def load_secrets() -> dict:
    secrets_file = Path(__file__).resolve().parents[2] / "secrets.json"
    with secrets_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_resume() -> Path | None:
    for pattern in RESUME_PATTERNS:
        matches = list(Path(__file__).resolve().parents[2].glob(pattern))
        if matches:
            return matches[0]
    return None


def parse_mail_file(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8")
    to_line, rest = text.split("\n", 1)
    subj_line, _, body = rest.partition("\n\n")
    to_email = to_line.replace("TO: ", "").strip()
    subject = subj_line.replace("SUBJECT: ", "").strip()
    return to_email, subject, body.strip()


def send_one(smtp: dict, to_email: str, subject: str, body: str, resume: Path | None) -> bool:
    msg = MIMEMultipart()
    msg["From"] = smtp["SMTP_USER"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if resume:
        with resume.open("rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=resume.name)
        msg.attach(part)

    with smtplib.SMTP(smtp["SMTP_HOST"], int(smtp["SMTP_PORT"])) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp["SMTP_USER"], smtp["SMTP_PASSWORD"])
        server.send_message(msg)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preview", "dry-run", "live"], default="preview")
    parser.add_argument("--to", default="", help="Override recipient (for dry-run testing only)")
    parser.add_argument("--interval", type=int, default=SEND_INTERVAL_SECONDS,
                        help="Seconds between mails (default 60)")
    args = parser.parse_args()

    secrets = load_secrets()
    smtp = secrets
    resume = find_resume()
    status = storage.load_status()

    generated = {
        pid: rec for pid, rec in status.items()
        if rec.get("status") == "GENERATED" and rec.get("to_email")
    }

    if not generated:
        storage.log("No GENERATED mails to send.")
        return

    storage.log(f"Mode={args.mode} | mails={len(generated)} | resume={resume}")

    for i, (pid, rec) in enumerate(generated.items()):
        mail_file = Path(storage.PROJECT_DIR) / rec.get("mail_file", "")
        if not mail_file.exists():
            storage.log(f"MISSING mail file for {rec.get('author')}: {mail_file}")
            continue

        to_email, subject, body = parse_mail_file(mail_file)
        author = rec.get("author", "unknown")

        if args.mode == "preview":
            safe_subject = subject.encode("ascii", "ignore").decode("ascii")
            safe_body = body.encode("ascii", "ignore").decode("ascii")
            print(f"\n----- PREVIEW {i + 1}: {author} -> {to_email} -----")
            print(f"Subject: {safe_subject}")
            print(safe_body)
            storage.log(f"PREVIEW {author} -> {to_email}")
            continue

        target = to_email
        if args.mode == "dry-run":
            target = args.to or smtp["SENDER_EMAIL"]
            storage.log(f"DRY-RUN {author}: would send to {to_email}, sending to {target} instead")
            print(f"DRY-RUN to {target}: {subject.encode('ascii', 'ignore').decode('ascii')}")

        try:
            send_one(smtp, target, subject, body, resume)
            if args.mode == "dry-run":
                rec["status"] = "GENERATED"  # keep as-is so a later LIVE run still sends to recruiter
                rec["dry_run_ok"] = True
                storage.log(f"DRY-OK [{i + 1}/{len(generated)}] {author} -> {target} (real target: {to_email})")
            else:
                rec["status"] = "SENT"
                rec["sent_at"] = datetime.now().isoformat(timespec="seconds")
                rec["sent_to"] = to_email
                storage.log(f"SENT [{i + 1}/{len(generated)}] {author} -> {to_email}")
        except Exception as exc:
            rec["status"] = "ERROR"
            rec["skip_reason"] = f"send_error: {exc}"
            storage.log(f"ERROR sending {author} -> {to_email}: {exc}")

        storage.save_status(status)

        if args.mode != "preview" and i < len(generated) - 1:
            storage.log(f"Waiting {args.interval}s before next mail...")
            time.sleep(args.interval)

    sent = [pid for pid, rec in status.items()
            if rec.get("to_email") and rec.get("status") == "SENT"]
    storage.log(f"SEND SUMMARY: mode={args.mode} sent={len(sent)}")
    for pid in sent:
        rec = status[pid]
        storage.log(f"  SENT-> {rec.get('to_email', '?')} | {rec.get('author', '?')}")
    storage.log("=== SEND RUN END ===")


if __name__ == "__main__":
    main()