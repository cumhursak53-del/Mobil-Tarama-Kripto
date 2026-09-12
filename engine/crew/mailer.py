from __future__ import annotations

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from engine.crew.config import REPORT_TO_EMAIL, SMTP_APP_PASSWORD, SMTP_HOST, SMTP_PORT, SMTP_USER


def send_report_email(
    *,
    subject: str,
    html_body: str,
    csv_bytes: bytes | None = None,
    csv_name: str = "crew_report.csv",
    to_email: str | None = None,
) -> None:
    user = SMTP_USER
    password = SMTP_APP_PASSWORD
    recipient = to_email or REPORT_TO_EMAIL
    if not user or not password:
        raise RuntimeError("SMTP_USER ve SMTP_APP_PASSWORD tanimli olmali")
    if not recipient:
        raise RuntimeError("REPORT_TO_EMAIL tanimli olmali")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if csv_bytes:
        att = MIMEApplication(csv_bytes, Name=csv_name)
        att["Content-Disposition"] = f'attachment; filename="{csv_name}"'
        msg.attach(att)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [recipient], msg.as_string())
