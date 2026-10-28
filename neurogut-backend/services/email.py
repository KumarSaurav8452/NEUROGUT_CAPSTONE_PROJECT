"""
NEUROGUT -- Email Service (v4.0)
==================================
Sends invitation emails with magic-link tokens.
Falls back to console logging when SMTP is not configured (dev mode).
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@neurogut.app")
APP_DOMAIN = os.getenv("APP_DOMAIN", "http://localhost:3000")


def send_invite_email(
    to_email: str,
    to_name: str,
    inviter_name: str,
    hospital_name: str,
    role: str,
    raw_token: str,
    welcome_message: str = "",
) -> bool:
    """
    Send an invitation email to a new user.
    Returns True on success, False on failure.
    If SMTP_HOST is not configured, logs the invite link to the console (dev mode).
    """
    invite_url = f"{APP_DOMAIN}/accept-invite?token={raw_token}"
    subject = f"You have been invited to NEUROGUT — {hospital_name}"

    # Build HTML email body
    welcome_block = (
        f'<div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:12px 16px;margin:16px 0;border-radius:4px;">'
        f'<p style="margin:0;color:#166534;">{welcome_message}</p></div>'
        if welcome_message
        else ""
    )

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:'Segoe UI',Arial,sans-serif;max-width:560px;margin:0 auto;padding:32px 16px;color:#1e293b;">
  <div style="text-align:center;margin-bottom:32px;">
    <h1 style="color:#006D77;font-size:28px;margin:0;">NEUROGUT</h1>
    <p style="color:#64748b;margin:4px 0 0;">Gut-Brain Axis Diagnostic Platform</p>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:32px;">
    <h2 style="font-size:20px;margin:0 0 8px;">Hi {to_name},</h2>
    <p style="color:#475569;line-height:1.6;">
      <strong>{inviter_name}</strong> from <strong>{hospital_name}</strong> has added you to
      NEUROGUT as a <strong style="text-transform:capitalize;">{role}</strong>.
    </p>
    {welcome_block}
    <p style="color:#475569;line-height:1.6;">
      Click the button below to accept your invitation and set your password.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{invite_url}"
         style="background:#006D77;color:white;padding:14px 28px;border-radius:8px;
                text-decoration:none;font-weight:600;font-size:15px;display:inline-block;">
        Accept Invitation &amp; Set Password
      </a>
    </div>
    <p style="color:#94a3b8;font-size:13px;text-align:center;">
      This invitation expires in <strong>72 hours</strong>.
    </p>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#94a3b8;font-size:12px;">
      If you did not expect this invitation, please ignore this email or contact your administrator.
    </p>
  </div>
</body>
</html>"""

    plain_body = (
        f"Hi {to_name},\n\n"
        f"{inviter_name} from {hospital_name} has invited you to NEUROGUT as a {role}.\n\n"
        f"Accept your invitation here:\n{invite_url}\n\n"
        f"This invitation expires in 72 hours.\n\n"
        f"If you did not expect this email, please ignore it."
    )

    # Dev mode: no SMTP configured — log to console
    if not SMTP_HOST:
        logger.warning(
            "\n"
            "=" * 60 + "\n"
            "[DEV MODE] NEUROGUT Invite Email (not sent — SMTP not configured)\n"
            f"  To:      {to_email}\n"
            f"  Subject: {subject}\n"
            f"  Link:    {invite_url}\n"
            "=" * 60
        )
        print(f"\n[NEUROGUT INVITE] {invite_url}\n")
        return True

    # Send via SMTP
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            if SMTP_PORT != 25:
                server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, [to_email], msg.as_string())

        logger.info(f"Invite email sent to {to_email}")
        return True

    except Exception as exc:
        logger.error(f"Failed to send invite email to {to_email}: {exc}")
        return False
