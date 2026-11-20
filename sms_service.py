"""
sms_service.py - Patient SMS Notification Dispatcher
Constructs official SMS prescription notifications for community health camps.
Supports SMS Gateway API if SMS_API_KEY is configured in .env,
and returns universal mobile one-click 'sms:+91<phone>?body=...' and WhatsApp links.
"""

import os
import urllib.parse
from datetime import datetime


def format_patient_phone_intl(raw_phone: str) -> str:
    """Format phone number to standard international +91<10-digits>."""
    if not raw_phone:
        return ""
    digits = "".join(ch for ch in str(raw_phone) if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    elif len(digits) > 10:
        return f"+{digits}"
    return f"+91{digits}" if digits else ""


def build_consultation_sms_package(
    patient,
    doctor_name: str,
    diagnosis: str,
    prescription: str,
    doctor_notes: str,
    priority: str = "Normal",
    host_url: str = None
) -> dict:
    """
    Build structured SMS notification text and mobile dispatch links for a completed consultation.
    """
    patient_name = getattr(patient, 'display_name', getattr(patient, 'name', 'Beneficiary'))
    patient_uid = getattr(patient, 'patient_uid', getattr(patient, 'patient_id', 'PAT-2026'))
    phone_raw = getattr(patient, 'phone', '')
    phone_intl = format_patient_phone_intl(phone_raw)

    doc_display = doctor_name if doctor_name.startswith('Dr.') or doctor_name.startswith('Dr ') else f"Dr. {doctor_name}"

    base_url = (host_url or os.environ.get('BASE_APP_URL', 'https://health-camp-app.onrender.com')).rstrip('/')
    pass_url = f"{base_url}/verify-pass/{patient_uid}"

    # Build concise, high-impact clinical SMS text
    lines = [
        f"🏥 SMART HEALTH CAMP - CLINICAL ADVICE",
        f"👤 Patient: {patient_name} ({patient_uid})",
        f"👨⚕️ Doctor: {doc_display}",
        f"⚡ Priority: {priority.upper()}",
        f"🩺 Diagnosis: {diagnosis}",
        f"💊 Medicines: {prescription or 'None specified'}",
        f"🥗 Diet & Notes: {doctor_notes or 'Drink boiled water, eat nutritious food, take rest.'}",
        f"🔗 Digital Pass & Report: {pass_url}",
        f"🚨 Emergency: Call 108"
    ]
    sms_text = "\n".join(lines)
    encoded_text = urllib.parse.quote(sms_text)

    # Universal mobile SMS link: sms:+91<phone>?body=... (works on all iOS & Android devices)
    sms_link = f"sms:{phone_intl}?body={encoded_text}" if phone_intl else f"sms:?body={encoded_text}"

    # WhatsApp Link
    clean_digits = "".join(ch for ch in phone_intl if ch.isdigit())
    wa_link = f"https://wa.me/{clean_digits}?text={encoded_text}" if clean_digits else f"https://wa.me/?text={encoded_text}"

    # Try SMS Gateway if SMS_API_KEY is configured
    sms_api_key = os.environ.get('SMS_API_KEY', '').strip()
    api_dispatched = False
    api_message = "SMS link generated for device dispatch."

    if sms_api_key and clean_digits:
        try:
            import requests
            # Support common SMS gateway (e.g. Fast2SMS / Generic Webhook)
            gateway_url = os.environ.get('SMS_GATEWAY_URL', 'https://www.fast2sms.com/dev/bulkV2')
            payload = {
                "route": "q",
                "message": sms_text,
                "numbers": clean_digits[-10:],
                "language": "english"
            }
            headers = {
                "authorization": sms_api_key,
                "Content-Type": "application/json"
            }
            res = requests.post(gateway_url, json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                api_dispatched = True
                api_message = "SMS dispatched successfully via SMS Gateway API."
        except Exception as e:
            api_message = f"SMS Gateway API notice: {str(e)}"

    return {
        'sms_text': sms_text,
        'sms_link': sms_link,
        'wa_link': wa_link,
        'phone_intl': phone_intl,
        'api_dispatched': api_dispatched,
        'api_message': api_message
    }
