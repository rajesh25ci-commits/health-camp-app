"""
email_service.py - Hybrid Email Dispatcher (Brevo HTTPS API + Gmail SMTP)
Uses Brevo REST API (port 443) when BREVO_API_KEY is set (bypasses Render SMTP port blocks),
and falls back to Gmail SMTP (smtp.gmail.com:587) for local development.
"""

import os
import json
import urllib.request
import urllib.error

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_otp_email(to_email: str, otp: str, patient_name: str = "Valued Patient") -> tuple[bool, str]:
    """
    Send a 6-digit email verification OTP to any recipient email address.
    Uses Brevo HTTP API on cloud (Render) or Gmail SMTP locally.
    """
    brevo_api_key = os.environ.get('BREVO_API_KEY', '').strip()
    mail_user = os.environ.get('MAIL_USERNAME', '').strip()
    mail_pass = os.environ.get('MAIL_APP_PASSWORD', '').strip() or os.environ.get('MAIL_PASSWORD', '').strip()
    mail_sender = os.environ.get('MAIL_DEFAULT_SENDER', mail_user).strip() or mail_user

    subject = f"Smart Health Camp - Your 6-Digit Verification Code: {otp}"

    text_content = f"""Hello {patient_name},

Thank you for registering on the Smart Community Health Camp Portal.

Your 6-digit email verification OTP code is:
{otp}

This code is valid for 15 minutes. Enter this code on the verification screen to activate your account and unlock your scannable Digital Health Pass.

Never share this code with anyone. If you did not request this, please disregard this email.

Warm regards,
Smart Community Health Camp Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
    .card {{ max-width: 520px; margin: 0 auto; background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 16px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    .logo {{ color: #06b6d4; font-size: 24px; font-weight: bold; margin-bottom: 8px; }}
    .title {{ font-size: 20px; font-weight: 600; color: #ffffff; margin-bottom: 16px; }}
    .otp-box {{ background: linear-gradient(135deg, #06b6d4, #2563eb); border-radius: 12px; padding: 18px; text-align: center; font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #ffffff; margin: 24px 0; }}
    .note {{ font-size: 13px; color: #94a3b8; line-height: 1.5; }}
    .footer {{ margin-top: 24px; font-size: 11px; color: #64748b; text-align: center; border-top: 1px solid #334155; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🏥 Smart Health Camp</div>
    <div class="title">Verify Your Patient Email Address</div>
    <p>Hello <b>{patient_name}</b>,</p>
    <p>Thank you for registering on our Community Health Camp Portal. Use the following 6-digit one-time password (OTP) to activate your account and access your smartphone-scannable <b>Digital Health Pass</b>:</p>
    <div class="otp-box">{otp}</div>
    <p class="note">This verification code is valid for 15 minutes. Never share this code with anyone.</p>
    <div class="footer">
      Smart Community Health Camp Portal &bull; Healthcare Outreach Initiative
    </div>
  </div>
</body>
</html>
"""

    # 1. Primary Cloud Dispatcher: Brevo HTTPS API (Port 443 - Never blocked on Render)
    if brevo_api_key:
        if not mail_sender:
            return False, "Sender email (MAIL_USERNAME) is missing in environment variables."
        try:
            payload = {
                "sender": {
                    "name": "Smart Community Health Camp",
                    "email": mail_sender
                },
                "to": [
                    {
                        "email": to_email,
                        "name": patient_name
                    }
                ],
                "subject": subject,
                "htmlContent": html_content,
                "textContent": text_content
            }
            req = urllib.request.Request(
                "https://api.brevo.com/v3/smtp/email",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "accept": "application/json",
                    "api-key": brevo_api_key,
                    "content-type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status in (200, 201, 202):
                    return True, "Verification email dispatched successfully."
                return False, f"Email API returned unexpected status: {response.status}"

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"[BREVO API ERROR] HTTP {e.code}: {err_body}")
            return False, f"Email API error ({e.code}): Check BREVO_API_KEY and verified sender email."
        except Exception as e:
            print(f"[BREVO API EXCEPTION] {e}")
            return False, f"Could not reach email service: {str(e)}"

    # 2. Local Development Fallback: Gmail SMTP
    mail_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com').strip() or 'smtp.gmail.com'
    try:
        mail_port = int(os.environ.get('MAIL_PORT', 587))
    except (ValueError, TypeError):
        mail_port = 587
    mail_tls = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't', 'yes')

    if not mail_user or not mail_pass:
        error_msg = "Email credentials missing. Configure BREVO_API_KEY or MAIL_USERNAME/MAIL_APP_PASSWORD."
        print(f"[EMAIL SERVICE ERROR] {error_msg}")
        return False, error_msg

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Smart Community Health Camp <{mail_sender}>"
        msg['To'] = to_email
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(mail_server, mail_port, timeout=12)
        if mail_tls:
            server.starttls()
        server.login(mail_user, mail_pass)
        server.sendmail(mail_sender, [to_email], msg.as_string())
        server.quit()
        return True, "Verification email dispatched successfully."

    except Exception as e:
        err_str = str(e)
        print(f"[EMAIL SERVICE EXCEPTION] Failed to dispatch email to {to_email}: {err_str}")
        return False, f"Could not connect to Gmail SMTP: {err_str}."