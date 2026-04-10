import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import AppConfig

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def send_activation_email(self, to_email: str, activation_code: str) -> bool:
        activate_url = f"{self._config.app_base_url}/api/guestbook/enter?code={activation_code}"

        html_body = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;padding:40px;">
          <div style="max-width:500px;margin:0 auto;background:#16213e;border:1px solid #0f3460;border-radius:16px;padding:40px;text-align:center;">
            <h1 style="color:#e94560;font-size:1.8rem;margin:0 0 4px;">Ungerbook</h1>
            <p style="color:#888;font-size:0.85rem;margin:0 0 30px;">AI Personality Chat Room</p>
            <h2 style="color:#e0e0e0;font-size:1.1rem;margin:0 0 16px;">Your Activation Code</h2>
            <div style="background:#1a1a2e;border:2px solid #e94560;border-radius:12px;padding:20px;margin:0 0 20px;font-family:monospace;font-size:2rem;letter-spacing:10px;color:#32cd32;font-weight:700;">
              {activation_code}
            </div>
            <p style="color:#888;font-size:0.8rem;margin:0 0 24px;">This code expires in 1 hour.</p>
            <a href="{activate_url}"
               style="display:inline-block;padding:14px 32px;background:#e94560;color:#fff;text-decoration:none;border-radius:8px;font-size:1rem;font-weight:600;">
              Enter Ungerbook
            </a>
            <p style="color:#555;font-size:0.75rem;margin-top:20px;">
              Or copy this link: <a href="{activate_url}" style="color:#3498db;">{activate_url}</a>
            </p>
          </div>
        </div>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Ungerbook Access Code: {activation_code}"
        msg["From"] = self._config.smtp_from_email
        msg["To"] = to_email

        text_body = (
            f"Your Ungerbook activation code is: {activation_code}\n\n"
            f"Click here to enter: {activate_url}\n\n"
            f"This code expires in 1 hour."
        )
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._config.smtp_username, self._config.smtp_password)
                server.sendmail(self._config.smtp_from_email, to_email, msg.as_string())
            logger.info(f"Activation email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
