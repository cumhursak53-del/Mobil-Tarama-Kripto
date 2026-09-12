"""CLI: python -m engine.crew.daily [--send-email] [--dry-run]"""
from __future__ import annotations

import argparse
import json

from engine.crew.pipeline import run_daily_crew


def main() -> None:
    p = argparse.ArgumentParser(description="Krpito Crew gunluk strateji pipeline")
    p.add_argument("--send-email", action="store_true", help="Raporu SMTP ile gonder")
    p.add_argument("--dry-run", action="store_true", help="State/mail yazma")
    p.add_argument("--no-email", action="store_true", help="Mail gonderme (varsayilan)")
    args = p.parse_args()
    send = args.send_email and not args.no_email
    out = run_daily_crew(send_email=send, dry_run=args.dry_run)
    print(json.dumps({
        "subject": out.get("subject"),
        "email_sent": out.get("email_sent"),
        "summary": out.get("summary"),
        "errors": out.get("errors"),
        "dry_run": out.get("dry_run"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
