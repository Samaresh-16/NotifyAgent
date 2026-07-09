from __future__ import annotations

import smtplib
from email.message import EmailMessage


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

    def send(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.username
        message["To"] = self.recipient
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.username, self.password)
            smtp.send_message(message)

