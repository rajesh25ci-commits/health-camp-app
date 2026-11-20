"""
upgraded_features.py - Advanced Healthcare Camp Management Features
Includes:
- Database Models: MedicineInventory, MedicineReminder, AmbulanceDispatchLog
- Blueprint: features_bp
- Critical Vitals Red-Flag Triage & 108 Ambulance Dispatch System
- Automated Medicine Timing SMS & WhatsApp Reminders
- Personalized Indian Food & Diet Recommendations
- Live Pharmacy Inventory Management & Stock Deductions
- Floating Health Camp Doubt-Solving Chatbot API
- Offline-First Local Queue Sync API
- Returning Patient Visit History API
"""

import os
import json
import urllib.parse
from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from models import db, Patient, Doctor, Camp, HealthRecord, Medicine

features_bp = Blueprint('features_bp', __name__)


# ==========================================
# 1. UPGRADED DATABASE MODELS
# ==========================================

class MedicineInventory(db.Model):
    """
    Live Pharmacy Inventory tracking medicine stocks, unit forms, reorder levels,
    expiry dates, and clinical alternatives.
    """
    __tablename__ = 'medicine_inventory'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    batch_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    stock_quantity = db.Column(db.Integer, default=0, nullable=False)
    unit = db.Column(db.String(20), default='Tablets', nullable=False)  # 'Tablets', 'Capsules', 'Syrup', 'Sachets'
    reorder_threshold = db.Column(db.Integer, default=20, nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    category = db.Column(db.String(50), default='General', nullable=False)  # 'Analgesic', 'Antibiotic', 'Antidiabetic', 'Cardiovascular', 'Antiallergic'
    alternative_medicine = db.Column(db.String(120), nullable=True)  # Recommended alternative if stock is depleted
    unit_price = db.Column(db.Float, default=0.0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.stock_quantity <= self.reorder_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.stock_quantity <= 0

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'batch_number': self.batch_number,
            'stock_quantity': self.stock_quantity,
            'unit': self.unit,
            'reorder_threshold': self.reorder_threshold,
            'is_low_stock': self.is_low_stock,
            'is_out_of_stock': self.is_out_of_stock,
            'alternative_medicine': self.alternative_medicine,
            'category': self.category,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else None
        }


class MedicineReminder(db.Model):
    """
    Automated timing reminders for prescribed medications:
    Morning (8:00 AM), Afternoon (1:30 PM), Night (8:30 PM).
    """
    __tablename__ = 'medicine_reminders'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    phone_number = db.Column(db.String(25), nullable=True)
    medicine_name = db.Column(db.String(120), nullable=False)
    dosage = db.Column(db.String(50), default='1 tab', nullable=False)
    timing = db.Column(db.String(50), nullable=False)  # 'Morning', 'Afternoon', 'Night', 'Morning & Night', etc.
    instructions = db.Column(db.String(100), default='After Food / भोजन के बाद', nullable=False)
    scheduled_time = db.Column(db.String(30), default='08:00 AM', nullable=False)
    is_sent = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'phone_number': self.phone_number,
            'medicine_name': self.medicine_name,
            'dosage': self.dosage,
            'timing': self.timing,
            'instructions': self.instructions,
            'scheduled_time': self.scheduled_time,
            'is_sent': self.is_sent,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class AmbulanceDispatchLog(db.Model):
    """
    Audit log of 108 Emergency Ambulance Dispatches and tertiary hospital referrals
    triggered from health camp red-flag vitals triage.
    """
    __tablename__ = 'ambulance_dispatch_logs'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    camp_id = db.Column(db.Integer, db.ForeignKey('camps.id'), nullable=True)
    critical_vitals_summary = db.Column(db.String(255), nullable=False)
    chief_complaint = db.Column(db.Text, nullable=True)
    dispatch_status = db.Column(db.String(50), default='Dispatched', nullable=False)  # 'Dispatched', 'En Route', 'Hospital Admitted', 'Handed Over'
    ambulance_service = db.Column(db.String(100), default='108 Emergency Medical Services', nullable=False)
    destination_hospital = db.Column(db.String(200), default='District Civil Hospital / Trauma Centre', nullable=False)
    dispatched_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    patient = db.relationship('Patient', backref=db.backref('ambulance_dispatches', lazy=True, cascade='all, delete-orphan'))
    doctor = db.relationship('Doctor', backref=db.backref('ambulance_dispatches', lazy=True))
    camp = db.relationship('Camp', backref=db.backref('ambulance_dispatches', lazy=True))

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.name if self.patient else 'Unknown',
            'patient_uid': self.patient.patient_uid if self.patient else 'N/A',
            'critical_vitals_summary': self.critical_vitals_summary,
            'chief_complaint': self.chief_complaint,
            'dispatch_status': self.dispatch_status,
            'ambulance_service': self.ambulance_service,
            'destination_hospital': self.destination_hospital,
            'dispatched_at': self.dispatched_at.strftime('%Y-%m-%d %H:%M:%S'),
            'notes': self.notes
        }


# ==========================================
# 2. CORE CLINICAL & PHARMACY FUNCTIONS
# ==========================================

def evaluate_vitals_triage(systolic_bp=None, diastolic_bp=None, rbs=None, spo2=None, pulse_rate=None) -> dict:
    """
    Evaluate physiological vital signs and determine Emergency Red-Flag Triage Status.
    
    Clinical Thresholds:
    - Hypertensive Crisis: Systolic >= 180 or Diastolic >= 120
    - Severe Hypotension: Systolic < 90
    - Hypoxia (Respiratory Distress): SpO2 < 92%
    - Hyperglycemic Emergency: Blood Sugar (RBS) >= 300 mg/dL
    - Severe Hypoglycemia: Blood Sugar <= 60 mg/dL
    - Tachycardia / Bradycardia: Pulse > 130 bpm or Pulse < 45 bpm
    """
    reasons = []
    is_critical = False
    priority = 'NORMAL_GREEN'
    color = 'success'

    # 1. Blood Pressure Triage
    sys_val = None
    dia_val = None
    try:
        if systolic_bp is not None and str(systolic_bp).strip() != '':
            sys_val = float(systolic_bp)
        if diastolic_bp is not None and str(diastolic_bp).strip() != '':
            dia_val = float(diastolic_bp)
    except (ValueError, TypeError):
        pass

    if sys_val is not None and dia_val is not None:
        if sys_val >= 180 or dia_val >= 120:
            is_critical = True
            reasons.append(f"Hypertensive Crisis (BP: {int(sys_val)}/{int(dia_val)} mmHg - Risk of stroke/infarct)")
        elif sys_val < 90 or dia_val < 55:
            is_critical = True
            reasons.append(f"Severe Hypotension / Shock (BP: {int(sys_val)}/{int(dia_val)} mmHg)")
        elif sys_val >= 140 or dia_val >= 90:
            if not is_critical:
                priority = 'MODERATE_YELLOW'
                color = 'warning'
                reasons.append(f"Stage 2 Hypertension (BP: {int(sys_val)}/{int(dia_val)} mmHg)")

    # 2. Oxygen Saturation (SpO2) Triage
    spo2_val = None
    try:
        if spo2 is not None and str(spo2).strip() != '':
            spo2_val = float(spo2)
    except (ValueError, TypeError):
        pass

    if spo2_val is not None:
        if spo2_val < 92:
            is_critical = True
            reasons.append(f"Severe Hypoxia (SpO2: {spo2_val:.1f}% - Critical Respiratory Distress)")
        elif spo2_val < 95:
            if not is_critical:
                priority = 'MODERATE_YELLOW'
                color = 'warning'
                reasons.append(f"Borderline Hypoxia (SpO2: {spo2_val:.1f}%)")

    # 3. Random Blood Sugar (RBS) Triage
    rbs_val = None
    try:
        if rbs is not None and str(rbs).strip() != '':
            rbs_val = float(rbs)
    except (ValueError, TypeError):
        pass

    if rbs_val is not None:
        if rbs_val >= 300:
            is_critical = True
            reasons.append(f"Severe Hyperglycemia (RBS: {rbs_val:.0f} mg/dL - Risk of DKA/HHS)")
        elif rbs_val <= 60:
            is_critical = True
            reasons.append(f"Severe Hypoglycemia (RBS: {rbs_val:.0f} mg/dL - Immediate glucose needed)")
        elif rbs_val >= 200:
            if not is_critical:
                priority = 'MODERATE_YELLOW'
                color = 'warning'
                reasons.append(f"Elevated Blood Sugar (RBS: {rbs_val:.0f} mg/dL)")

    # 4. Pulse Rate Triage
    pulse_val = None
    try:
        if pulse_rate is not None and str(pulse_rate).strip() != '':
            pulse_val = float(pulse_rate)
    except (ValueError, TypeError):
        pass

    if pulse_val is not None:
        if pulse_val > 130 or pulse_val < 45:
            is_critical = True
            reasons.append(f"Abnormal Heart Rate (Pulse: {int(pulse_val)} bpm)")

    if is_critical:
        priority = 'EMERGENCY_RED'
        color = 'danger'
    elif priority == 'NORMAL_GREEN' and not reasons:
        reasons.append("Vitals within normal physiological range")

    # Summary text
    vitals_parts = []
    if sys_val and dia_val:
        vitals_parts.append(f"BP: {int(sys_val)}/{int(dia_val)} mmHg")
    if spo2_val:
        vitals_parts.append(f"SpO2: {spo2_val:.0f}%")
    if rbs_val:
        vitals_parts.append(f"RBS: {rbs_val:.0f} mg/dL")
    if pulse_val:
        vitals_parts.append(f"Pulse: {int(pulse_val)} bpm")

    summary_str = ", ".join(vitals_parts) if vitals_parts else "No vitals recorded"

    return {
        'is_critical': is_critical,
        'priority': priority,
        'color': color,
        'reasons': reasons,
        'reasons_text': " | ".join(reasons),
        'summary': summary_str,
        'systolic': sys_val,
        'diastolic': dia_val,
        'spo2': spo2_val,
        'rbs': rbs_val,
        'pulse': pulse_val
    }


def build_medicine_schedule_sms(patient, prescription_text: str, save_to_db: bool = True) -> dict:
    """
    Parse free-form or structured prescription text, create distinct Morning, Afternoon,
    and Night reminders, generate a clear bilingual SMS schedule, and create a 1-click
    WhatsApp sharing link.
    """
    lines = [line.strip() for line in (prescription_text or "").split("\n") if line.strip()]
    med_reminders = []

    # Default schedule slots
    schedule = {
        'Morning': {'time': '08:00 AM (सुबह 8:00 बजे)', 'meds': [], 'hindi': 'नाश्ते के बाद'},
        'Afternoon': {'time': '01:30 PM (दोपहर 1:30 बजे)', 'meds': [], 'hindi': 'दोपहर भोजन के बाद'},
        'Night': {'time': '08:30 PM (रात 8:30 बजे)', 'meds': [], 'hindi': 'रात के खाने के बाद'}
    }

    if not lines:
        lines = ["General multivitamins / ORS hydration as instructed by camp physician"]

    for raw_line in lines:
        clean_line = raw_line.lstrip("0123456789.-*•) ").strip()
        lower_line = clean_line.lower()

        # Determine dosage & timing from keywords
        is_morning = any(k in lower_line for k in ['morning', 'breakfast', 'subah', 'am', 'od', 'bd', 'tds'])
        is_afternoon = any(k in lower_line for k in ['afternoon', 'lunch', 'dopahar', 'tds'])
        is_night = any(k in lower_line for k in ['night', 'dinner', 'hs', 'raat', 'bedtime', 'bd', 'tds'])

        # If no specific tag matched, distribute safely (Morning & Night)
        if not (is_morning or is_afternoon or is_night):
            is_morning = True
            is_night = True

        if is_morning:
            schedule['Morning']['meds'].append(clean_line)
        if is_afternoon:
            schedule['Afternoon']['meds'].append(clean_line)
        if is_night:
            schedule['Night']['meds'].append(clean_line)

        # Save to DB if requested
        if save_to_db and patient and hasattr(patient, 'id'):
            timing_label = []
            if is_morning: timing_label.append("Morning")
            if is_afternoon: timing_label.append("Afternoon")
            if is_night: timing_label.append("Night")

            reminder = MedicineReminder(
                patient_id=patient.id,
                phone_number=getattr(patient, 'phone', None),
                medicine_name=clean_line[:120],
                dosage='1 dose',
                timing=" & ".join(timing_label) if timing_label else "Morning",
                instructions='After Food / भोजन के बाद',
                scheduled_time='08:00 AM / 08:30 PM'
            )
            db.session.add(reminder)
            med_reminders.append(reminder)

    if save_to_db and med_reminders:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Build formatted SMS / WhatsApp message string
    patient_name = getattr(patient, 'name', 'Beneficiary')
    patient_uid = getattr(patient, 'patient_uid', getattr(patient, 'patient_id', 'PAT-2026'))

    msg_lines = [
        f"🏥 *SMART HEALTH CAMP - MEDICINE SCHEDULE*",
        f"👤 Patient: *{patient_name}* ({patient_uid})",
        f"📅 Date: {datetime.now().strftime('%d %b %Y')}",
        "--------------------------------------",
        "⏰ *DAILY DOSAGE TIMINGS (दवाइयों का समय):*",
        "",
        "🌅 *MORNING / सुबह (08:00 AM) - नाश्ते के बाद:*"
    ]
    if schedule['Morning']['meds']:
        for m in schedule['Morning']['meds']:
            msg_lines.append(f"  • {m}")
    else:
        msg_lines.append("  • No morning medicines")

    msg_lines.append("")
    msg_lines.append("☀️ *AFTERNOON / दोपहर (01:30 PM) - दोपहर भोजन के बाद:*")
    if schedule['Afternoon']['meds']:
        for m in schedule['Afternoon']['meds']:
            msg_lines.append(f"  • {m}")
    else:
        msg_lines.append("  • No afternoon medicines")

    msg_lines.append("")
    msg_lines.append("🌙 *NIGHT / रात (08:30 PM) - रात के खाने के बाद:*")
    if schedule['Night']['meds']:
        for m in schedule['Night']['meds']:
            msg_lines.append(f"  • {m}")
    else:
        msg_lines.append("  • No night medicines")

    # Dynamic host_url resolution (never hardcoded 127.0.0.1)
    from flask import has_request_context, request
    if has_request_context():
        host_url = request.host_url.rstrip('/')
    else:
        host_url = os.environ.get('BASE_APP_URL', 'https://health-camp-app.onrender.com').rstrip('/')

    msg_lines.append("--------------------------------------")
    msg_lines.append("⚠️ *IMPORTANT INSTRUCTIONS:*")
    msg_lines.append("• Take prescribed doses on time with clean boiled water.")
    msg_lines.append("• Complete full course. In emergency, call 108.")
    msg_lines.append(f"🔗 *View Digital Pass & Report:* {host_url}/verify-pass/{patient_uid}")
    msg_lines.append("🚨 *Emergency Helpline:* 108")

    full_message = "\n".join(msg_lines)

    # WhatsApp link
    raw_phone = str(getattr(patient, 'phone', '') or '')
    clean_digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if len(clean_digits) == 10:
        phone_intl = "91" + clean_digits
    elif len(clean_digits) > 10:
        phone_intl = clean_digits
    else:
        phone_intl = ""

    encoded_text = urllib.parse.quote(full_message)
    whatsapp_url = f"https://wa.me/{phone_intl}?text={encoded_text}" if phone_intl else f"https://wa.me/?text={encoded_text}"
    sms_url = f"sms:{phone_intl}?body={encoded_text}" if phone_intl else f"sms:?body={encoded_text}"

    return {
        'message_text': full_message,
        'whatsapp_url': whatsapp_url,
        'sms_url': sms_url,
        'schedule': schedule,
        'phone': phone_intl
    }


def recommend_diet_plan(diagnosis_text: str = "", vitals_summary: str = "", systolic: int = None, rbs: float = None) -> dict:
    """
    Generate personalized Indian food & diet recommendations based on clinical diagnosis
    and patient vitals (e.g. Hypertension, Diabetes, Anemia, Respiratory, Fever, General).
    """
    diag_lower = (diagnosis_text or "").lower()
    vitals_lower = (vitals_summary or "").lower()

    plans = []

    # 1. Hypertension / Blood Pressure Plan
    is_htn = any(k in diag_lower for k in ['hypertens', 'bp', 'pressure', 'cardio']) or (systolic and systolic >= 140)
    if is_htn:
        plans.append({
            'category': 'Hypertension & Heart Health (उच्च रक्तचाप)',
            'foods_to_eat': [
                'Lauki (Bottle Gourd), Ridge Gourd (Turai), and Cucumber salad',
                'Fresh Garlic cloves (1-2 cloves in morning with warm water)',
                'Oats, Dalia, Brown Rice, and Jowar / Ragi Rotis',
                'Potassium-rich fruits: Banana, Papaya, Sweet Lime, and Coconut Water',
                'Unsalted buttermilk (Chhachh) with roasted cumin powder'
            ],
            'foods_to_avoid': [
                'Pickles (Aachar), Papad, Chutneys, and Salted Namkeen',
                'Extra table salt on salads, curd, or cooked food',
                'Deep-fried snacks: Samosa, Pakoda, Puri, Bhujia',
                'Processed and canned foods containing sodium preservatives',
                'Excessive tea, coffee, and tobacco products'
            ],
            'lifestyle_tip': 'Practice 30 minutes of brisk walking daily and reduce dietary sodium to under 5g/day.'
        })

    # 2. Diabetes / High Blood Sugar Plan
    is_dm = any(k in diag_lower for k in ['diabet', 'sugar', 'glucose', 'rbs', 'hba1c']) or (rbs and rbs >= 180)
    if is_dm:
        plans.append({
            'category': 'Diabetes Care & Glycemic Control (मधुमेह नियंत्रण)',
            'foods_to_eat': [
                'Methi (Fenugreek) seeds soaked in water overnight',
                'Bitter Gourd (Karela), Jamun fruit, and Amla (Indian Gooseberry)',
                'Whole pulses & sprouts: Green Moong, Kala Chana, Rajma',
                'High-fiber grains: Multigrain atta (Chana + Wheat), Barley (Jau), Bajra',
                'Green leafy vegetables: Palak, Methi, Bathua, Cabbage'
            ],
            'foods_to_avoid': [
                'White refined sugar, Jaggery (Gud), Honey, and Indian Sweets (Mithai)',
                'White bread, Maida, polished white rice, and noodles',
                'High glycemic fruits: Mango, Chiku, Grapes, and Bananas in excess',
                'Packaged fruit juices, cold drinks, and sweetened sodas',
                'Full cream milk, condensed milk, and bakery biscuits'
            ],
            'lifestyle_tip': 'Eat small frequent meals every 3-4 hours; avoid prolonged fasting and check blood sugar periodically.'
        })

    # 3. Anemia / Iron Deficiency / Weakness
    is_anemia = any(k in diag_lower for k in ['anemia', 'anaemia', 'hemoglobin', 'weakness', 'fatigue', 'pallor', 'iron'])
    if is_anemia:
        plans.append({
            'category': 'Anemia & Iron Enrichment (खून की कमी / हीमोग्लोबिन)',
            'foods_to_eat': [
                'Drumstick (Moringa / Sahjan) pods and leaves in dal/curry',
                'Beetroot and Carrot salad with lemon juice (Vitamin C enhances iron absorption)',
                'Spinach (Palak), Fenugreek leaves, and Sarson Saag',
                'Jaggery (Gud) paired with roasted chana (Chana-Gud snack)',
                'Dates (Khajoor), Pomegranate (Anaar), Raisins (Kishmish), and boiled eggs'
            ],
            'foods_to_avoid': [
                'Drinking strong tea or coffee immediately before or after meals (inhibits iron uptake)',
                'Calcium tablets taken together with iron tablets (take 2 hours apart)',
                'Excessive processed junk food lacking nutritional value'
            ],
            'lifestyle_tip': 'Cook food in cast iron utensils (Kadhai) to naturally enrich daily food with dietary iron.'
        })

    # 4. Respiratory / Cough / Cold / Low Oxygen
    is_resp = any(k in diag_lower for k in ['cough', 'cold', 'bronch', 'asthma', 'respirat', 'fever', 'rhinitis', 'pneumon'])
    if is_resp:
        plans.append({
            'category': 'Respiratory Relief & Immunity (श्वसन व रोग प्रतिरोधक क्षमता)',
            'foods_to_eat': [
                'Warm turmeric milk (Haldi Doodh) with a pinch of black pepper at bedtime',
                'Kadha / Decoction: Tulsi, Ginger, Black Pepper, and Cloves with warm water',
                'Warm vegetable soups (Tomato, Garlic, Lentil rasam)',
                'Steamed fresh vegetables and light khichdi with desi cow ghee'
            ],
            'foods_to_avoid': [
                'Refrigerated cold drinks, ice creams, and chilled water',
                'Heavy, excessively oily gravies and stale food',
                'Smoking, dust exposure, and chilled air conditioning'
            ],
            'lifestyle_tip': 'Inhale steam twice daily and practice deep breathing (Pranayama) in fresh morning air.'
        })

    # Default Balanced Plan if no specific disease was identified
    if not plans:
        plans.append({
            'category': 'Balanced Community Wellness Diet (स्वस्थ एवं पौष्टिक आहार)',
            'foods_to_eat': [
                'Seasonal locally grown fruits and fresh green vegetables',
                'Mixed grain rotis (Wheat + Chana / Jowar) and whole lentils (Dal)',
                'Fresh homemade curd (Dahi) or Buttermilk during daytime',
                'Soaked nuts (Almonds, Walnuts) and roasted seeds',
                'Adequate safe boiled/filtered water throughout the day'
            ],
            'foods_to_avoid': [
                'Street junk food with reused cooking oil',
                'Excessive refined sugar, salt, and maida products',
                'Uncovered roadside cut fruits and artificial colored drinks'
            ],
            'lifestyle_tip': 'Maintain regular meal timings, sleep 7-8 hours, and undergo annual health camp screening.'
        })

    primary = plans[0]
    return {
        'plans': plans,
        'primary_plan': primary,
        'category': primary['category'],
        'foods_to_eat': primary['foods_to_eat'],
        'foods_to_avoid': primary['foods_to_avoid'],
        'lifestyle_tip': primary['lifestyle_tip']
    }


def deduct_medicine_inventory(prescription_text: str) -> list:
    """
    Automatically deduct medicine quantities from MedicineInventory (and legacy Medicine)
    based on prescribed lines. Returns a list of inventory transaction logs and warnings.
    """
    if not prescription_text:
        return []

    results = []
    lines = [line.strip() for line in prescription_text.split("\n") if line.strip()]

    for line in lines:
        clean = line.lower()
        # Find matching medicine in MedicineInventory
        med_items = MedicineInventory.query.all()
        matched_item = None
        for item in med_items:
            # Check if medicine name appears in prescription line
            if item.name.lower() in clean or clean.startswith(item.name.lower().split()[0]):
                matched_item = item
                break

        if not matched_item:
            # Check legacy Medicine model
            legacy_items = Medicine.query.all()
            for l_item in legacy_items:
                if l_item.name.lower() in clean or clean.startswith(l_item.name.lower().split()[0]):
                    # Sync into MedicineInventory if missing
                    matched_item = MedicineInventory.query.filter_by(name=l_item.name).first()
                    if not matched_item:
                        matched_item = MedicineInventory(
                            name=l_item.name,
                            batch_number=l_item.batch_number,
                            stock_quantity=l_item.quantity,
                            reorder_threshold=l_item.reorder_level,
                            unit='Tablets',
                            unit_price=l_item.unit_price,
                            expiry_date=l_item.expiry_date
                        )
                        db.session.add(matched_item)
                        db.session.commit()
                    break

        if matched_item:
            # Estimate tablets prescribed: default 10 tablets for camp course
            qty_to_deduct = 10
            # Check if specific quantity mentioned (e.g., "x 5 days", "10 tabs", "30 days")
            words = clean.split()
            for idx, w in enumerate(words):
                if w.isdigit():
                    val = int(w)
                    if 1 <= val <= 60:
                        qty_to_deduct = val
                        break

            previous_qty = matched_item.stock_quantity
            new_qty = max(0, previous_qty - qty_to_deduct)
            matched_item.stock_quantity = new_qty
            matched_item.updated_at = datetime.utcnow()

            # Also update legacy Medicine record if present
            leg_med = Medicine.query.filter_by(name=matched_item.name).first()
            if leg_med:
                leg_med.quantity = new_qty

            status_msg = f"Deducted {qty_to_deduct} {matched_item.unit} of {matched_item.name} (Remaining: {new_qty})"
            warning = None

            if new_qty == 0:
                warning = f"OUT OF STOCK: {matched_item.name}. Suggested alternative: {matched_item.alternative_medicine or 'Consult clinical lead'}"
            elif new_qty <= matched_item.reorder_threshold:
                warning = f"LOW STOCK ALERT: {matched_item.name} has only {new_qty} {matched_item.unit} left (Threshold: {matched_item.reorder_threshold})"

            results.append({
                'medicine_name': matched_item.name,
                'deducted': qty_to_deduct,
                'remaining': new_qty,
                'status': status_msg,
                'warning': warning,
                'alternative': matched_item.alternative_medicine
            })

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    return results


# ==========================================
# 3. BLUEPRINT API & ROUTE ENDPOINTS
# ==========================================

@features_bp.route('/dispatch-ambulance/<patient_id>', methods=['POST', 'GET'])
@login_required
def dispatch_ambulance(patient_id):
    """
    Emergency 108 Ambulance Dispatch Route.
    Triggered when critical red-flag vitals (Hypertensive crisis, severe hypoxia, glycemic coma)
    are detected during camp triage/consultation.
    """
    cleaned_id = str(patient_id).strip()
    patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_id)).first()
    if not patient and cleaned_id.isdigit():
        patient = db.session.get(Patient, int(cleaned_id))

    if not patient:
        flash(f"Beneficiary record {patient_id} not found for emergency dispatch.", "danger")
        return redirect(url_for('records'))

    # Extract referral details
    complaint = request.form.get('chief_complaint', 'Critical Vitals Red-Flag Triage Referral').strip()
    vitals_summary = request.form.get('vitals_summary', 'BP / SpO2 / Blood Sugar Critical Breach').strip()
    hospital = request.form.get('destination_hospital', 'District Trauma Hospital / Government Medical College').strip()
    service = request.form.get('ambulance_service', '108 National Emergency Ambulance Service').strip()
    doctor_id = request.form.get('doctor_id', type=int)
    camp_id = request.form.get('camp_id', type=int)

    log_entry = AmbulanceDispatchLog(
        patient_id=patient.id,
        doctor_id=doctor_id,
        camp_id=camp_id,
        critical_vitals_summary=vitals_summary,
        chief_complaint=complaint,
        destination_hospital=hospital,
        ambulance_service=service,
        dispatch_status='Dispatched',
        notes=f"Emergency dispatch logged by {current_user.username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    db.session.add(log_entry)
    db.session.commit()

    flash(
        f"🚨 EMERGENCY 108 AMBULANCE DISPATCHED! Patient {patient.name} ({patient.patient_uid}) referred to {hospital}. Dispatch Log ID: #{log_entry.id}.",
        "danger"
    )

    if request.is_json:
        return jsonify({
            'success': True,
            'message': 'Ambulance referral logged successfully',
            'log': log_entry.to_dict()
        })

    # Redirect back to patient detail or records
    return redirect(url_for('patient_detail', patient_id=patient.patient_uid))


@features_bp.route('/ambulance-logs')
@login_required
def ambulance_logs():
    """List of all emergency ambulance dispatches and referrals."""
    logs = AmbulanceDispatchLog.query.order_by(AmbulanceDispatchLog.dispatched_at.desc()).all()
    return render_template('ambulance_logs.html', logs=logs)


@features_bp.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """
    Universal Multilingual AI Health Camp Chatbot API (v3 Upgraded).
    Answers clinical inquiries, emergency triage (108), symptoms (Fever, Cough, Sugar, BP),
    and tablet timings in English, Hindi, Kannada, and Hinglish.
    """
    from upgraded_features_v3 import universal_health_chatbot
    data = request.get_json(silent=True) or {}
    query = (data.get('message') or request.form.get('message') or "").strip()

    res = universal_health_chatbot(query)
    return jsonify({
        'reply': res['reply'],
        'language': res['language'],
        'source': res['source'],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    })


@features_bp.route('/api/offline-sync', methods=['POST'])
@login_required
def api_offline_sync():
    """
    Offline-First Local Queue Synchronization Endpoint.
    Accepts JSON array of patient registrations captured locally in browser localStorage
    when mobile network drops, and bulk-inserts them with valid UIDs and QR codes.
    """
    data = request.get_json(silent=True) or {}
    offline_patients = data.get('patients', [])

    if not offline_patients:
        return jsonify({'success': False, 'message': 'No offline records provided for sync.'}), 400

    from utils import generate_qr_code

    synced_records = []
    year_str = datetime.utcnow().strftime('%Y')

    for item in offline_patients:
        name = (item.get('name') or '').strip()
        age = int(item.get('age') or 30)
        gender = item.get('gender') or 'Other'
        phone = (item.get('phone') or '').strip() or None
        address = (item.get('address') or '').strip() or None

        if not name:
            continue

        # Generate unique UID
        count_existing = Patient.query.count() + 1
        patient_uid = f"PAT-{year_str}-{count_existing:04d}"
        while Patient.query.filter_by(patient_uid=patient_uid).first():
            count_existing += 1
            patient_uid = f"PAT-{year_str}-{count_existing:04d}"

        # Generate QR code
        qr_path = generate_qr_code(patient_uid, current_app.config['QRCODE_FOLDER'])

        new_pat = Patient(
            patient_uid=patient_uid,
            name=name,
            age=age,
            gender=gender,
            phone=phone,
            address=address,
            qr_code_path=qr_path
        )
        db.session.add(new_pat)
        synced_records.append({
            'name': name,
            'patient_uid': patient_uid,
            'offline_id': item.get('offline_id')
        })

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'synced_count': len(synced_records),
            'records': synced_records,
            'message': f"Successfully synchronized {len(synced_records)} offline patient registrations!"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@features_bp.route('/api/inventory/check')
@login_required
def api_inventory_check():
    """Returns real-time stock levels and alternative medicines for doctor prescription dropdown."""
    items = MedicineInventory.query.order_by(MedicineInventory.name.asc()).all()
    return jsonify({
        'items': [item.to_dict() for item in items],
        'low_stock_items': [item.to_dict() for item in items if item.is_low_stock],
        'out_of_stock_items': [item.to_dict() for item in items if item.is_out_of_stock]
    })


@features_bp.route('/api/patient-history/<patient_uid_or_phone>')
@login_required
def api_patient_history(patient_uid_or_phone):
    """
    Returns previous health camp visits timeline whenever a returning patient
    is scanned via QR or searched by phone number.
    """
    cleaned = str(patient_uid_or_phone).strip()
    patient = Patient.query.filter(
        (Patient.patient_uid.ilike(cleaned)) | (Patient.phone == cleaned)
    ).first()

    if not patient and cleaned.isdigit():
        patient = db.session.get(Patient, int(cleaned))

    if not patient:
        return jsonify({'success': False, 'message': 'Patient not found'}), 404

    records = HealthRecord.query.filter_by(patient_id=patient.id).order_by(HealthRecord.created_at.desc()).all()
    timeline = []

    for r in records:
        timeline.append({
            'id': r.id,
            'date': r.created_at.strftime('%d %B %Y'),
            'time': r.created_at.strftime('%I:%M %p'),
            'doctor_name': r.doctor.name if r.doctor else 'Medical Officer',
            'specialization': r.doctor.specialization if r.doctor else 'General Medicine',
            'camp_title': r.camp.title if r.camp else 'Community Outreach',
            'camp_location': r.camp.location_name if r.camp else 'Camp Venue',
            'diagnosis': r.diagnosis,
            'prescription': r.prescription or 'None recorded',
            'doctor_notes': r.doctor_notes or ''
        })

    return jsonify({
        'success': True,
        'patient': {
            'id': patient.id,
            'name': patient.name,
            'patient_uid': patient.patient_uid,
            'age': patient.age,
            'gender': patient.gender,
            'phone': patient.phone,
            'total_visits': len(timeline)
        },
        'timeline': timeline
    })


def init_medicine_inventory_seed(app, force=False):
    if not force:
        return
    """
    Seed initial MedicineInventory records from existing Medicine catalog if empty.
    """
    with app.app_context():
        if MedicineInventory.query.count() == 0:
            defaults = [
                ("Paracetamol 500mg", "PCM-2026-A1", 450, "Tablets", 100, "Analgesic", "Tab Ibuprofen 400mg", 1.50),
                ("Amoxicillin 250mg", "AMX-2026-B2", 35, "Capsules", 50, "Antibiotic", "Tab Azithromycin 250mg", 3.20),
                ("Cetirizine 10mg", "CTZ-2026-C3", 180, "Tablets", 40, "Antiallergic", "Tab Levocetirizine 5mg", 1.10),
                ("Metformin 500mg", "MTF-2026-M4", 320, "Tablets", 60, "Antidiabetic", "Tab Glimepiride 1mg", 2.00),
                ("Amlodipine 5mg", "AML-2026-K5", 15, "Tablets", 40, "Cardiovascular", "Tab Telmisartan 40mg", 1.80),
                ("ORS Hydration Sachets", "ORS-2026-P6", 600, "Sachets", 100, "Hydration", "Electral Electrolyte Sachet", 5.00),
                ("Pantoprazole 40mg", "PAN-2026-D7", 220, "Tablets", 50, "Antacid", "Tab Omeprazole 20mg", 2.50),
                ("Iron & Folic Acid", "IFA-2026-F8", 12, "Tablets", 50, "Supplement", "Syrup Ferrous Ascorbate", 1.20)
            ]

            for name, batch, qty, unit, thresh, cat, alt, price in defaults:
                inv = MedicineInventory(
                    name=name,
                    batch_number=batch,
                    stock_quantity=qty,
                    unit=unit,
                    reorder_threshold=thresh,
                    category=cat,
                    alternative_medicine=alt,
                    unit_price=price,
                    expiry_date=date(2027, 12, 31)
                )
                db.session.add(inv)

            try:
                db.session.commit()
                print("[INFO] Initialized and seeded MedicineInventory batches.")
            except Exception as e:
                db.session.rollback()
                print(f"[WARN] MedicineInventory seeding skipped: {e}")
