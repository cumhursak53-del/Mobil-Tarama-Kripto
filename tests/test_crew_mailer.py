from unittest.mock import MagicMock, patch

from engine.crew.mailer import send_report_email


def test_send_report_email_mock():
    with patch("engine.crew.mailer.SMTP_USER", "user@test.com"):
        with patch("engine.crew.mailer.SMTP_APP_PASSWORD", "secret"):
            with patch("engine.crew.mailer.smtplib.SMTP") as smtp_cls:
                server = MagicMock()
                smtp_cls.return_value.__enter__.return_value = server
                send_report_email(
                    subject="Test",
                    html_body="<p>hi</p>",
                    to_email="a@b.com",
                )
                server.starttls.assert_called_once()
                server.login.assert_called_once()
                server.sendmail.assert_called_once()
