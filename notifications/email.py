from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class SmtpEmailSender:
    def __init__(
        self,
        *,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        recipient: str,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient

    def send(self, subject: str, body: str | None = None, html: str | None = None) -> None:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.username
        msg["To"] = self.recipient
        msg["Subject"] = subject

        # Plain-text fallback
        if body is None and html is not None:
            body = "This message is best viewed as HTML."

        if body:
            part_text = MIMEText(body, "plain", _charset="utf-8")
            msg.attach(part_text)

        if html:
            part_html = MIMEText(html, "html", _charset="utf-8")
            msg.attach(part_html)

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(msg)

