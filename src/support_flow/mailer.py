"""Mail delivery. ``Outbox`` records messages (demo/tests); ``SmtpMailer`` is the production shape (NOT executed here)."""
from __future__ import annotations
import smtplib
from email.message import EmailMessage


class Outbox:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


class SmtpMailer:
    def __init__(self, host: str, port: int, sender: str, user: str | None = None, password: str | None = None):
        self.host, self.port, self.sender, self.user, self.password = host, port, sender, user, password

    def send(self, to: str, subject: str, body: str) -> None:
        m = EmailMessage(); m["From"], m["To"], m["Subject"] = self.sender, to, subject; m.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=15) as s:
            s.starttls()
            if self.user:
                s.login(self.user, self.password or "")
            s.send_message(m)
