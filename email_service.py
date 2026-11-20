"""
email_service.py - Real Gmail SMTP Email Dispatcher for Smart Community Health Camp
Strictly sends 6-digit verification OTPs to registered patient email addresses using
Gmail SMTP (smtp.gmail.com:587 with TLS) and MAIL_USERNAME / MAIL_APP_PASSWORD from .env.
Never leaks OTPs on screen or in flash messages.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_otp_email(to_email: str, otp: str, patient_name: str = "Valued Patient") -> tuple[bool, str]:
    """
    Send a 6-digit email verification OTP strictly to the patient's entered email address
    via Gmail SMTP (smtp.gmail.com:587) using MAIL_USERNAME and MAIL_APP_PASSWORD from .env.

    :param to_email: Recipient email address.
    :param otp: 6-digit numeric OTP string.
    :param patient_name: Name of the patient.
    :return: (success: bool, message: str)
    """
    mail_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com').strip() or 'smtp.gmail.com'
    try:
        mail_port = int(os.environ.get('MAIL_PORT', 587))
    except (ValueError, TypeError):
        mail_port = 587

    mail_user = os.environ.get('MAIL_USERNAME', '').strip()
    mail_pass = os.environ.get('MAIL_APP_PASSWORD', '').strip() or os.environ.get('MAIL_PASSWORD', '').strip()
    mail_tls = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't', 'yes')
    mail_sender = os.environ.get('MAIL_DEFAULT_SENDER', mail_user).strip() or mail_user

    # If SMTP credentials are missing, do NOT simulate or leak OTP
    if not mail_user or not mail_pass:
        error_msg = "Gmail SMTP credentials missing. Please configure MAIL_USERNAME and MAIL_APP_PASSWORD in your .env file."
        print(f"[EMAIL SERVICE ERROR] {error_msg}")
        return False, error_msg

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Smart Health Camp - Your 6-Digit Verification Code: {otp}"
        msg['From'] = f"Smart Community Health Camp <{mail_sender}>"
        msg['To'] = to_email

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
        return False, f"Could not connect to Gmail SMTP: {err_str}. Please verify MAIL_USERNAME and MAIL_APP_PASSWORD in .env."
