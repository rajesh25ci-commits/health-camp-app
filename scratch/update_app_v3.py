import sys

with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Imports
import_needle = "from upgraded_features import ("
v3_import = """from upgraded_features_v3 import (
    features_v3_bp,
    universal_health_chatbot,
    get_symptom_based_prescription,
    compute_camp_gamification,
    calculate_patient_wellness_score,
    get_patient_journey_steps
)
from sqlalchemy import case
from upgraded_features import ("""

assert import_needle in code, "import_needle not found"
code = code.replace(import_needle, v3_import, 1)

# 2. Register blueprint
bp_needle = "app.register_blueprint(features_bp)"
bp_replacement = """app.register_blueprint(features_bp)
    app.register_blueprint(features_v3_bp)"""

assert bp_needle in code, "bp_needle not found"
code = code.replace(bp_needle, bp_replacement, 1)

# 3. Update dashboard()
old_dashboard = """        recent_patients = Patient.query.order_by(Patient.created_at.desc()).limit(5).all()
        upcoming_camps = Camp.query.filter(Camp.status == 'Upcoming').order_by(Camp.date.asc()).limit(5).all()
        low_stock_medicines = Medicine.query.filter(Medicine.quantity <= Medicine.reorder_level).all()"""

new_dashboard = """        all_camps = Camp.query.all()
        all_patients = Patient.query.all()
        all_records = HealthRecord.query.all()
        all_doctors = Doctor.query.all()
        all_dispatches = AmbulanceDispatchLog.query.all()
        gamification = compute_camp_gamification(all_camps, all_patients, all_records, all_doctors, all_dispatches)

        urgency_case = case(
            (Patient.urgency_level == 'EMERGENCY', 1),
            (Patient.urgency_level == 'URGENT', 2),
            else_=3
        )
        recent_patients = Patient.query.order_by(urgency_case, Patient.created_at.desc()).limit(8).all()
        upcoming_camps = Camp.query.filter(Camp.status == 'Upcoming').order_by(Camp.date.asc()).limit(5).all()
        low_stock_medicines = Medicine.query.filter(Medicine.quantity <= Medicine.reorder_level).all()"""

if old_dashboard not in code:
    old_dashboard = old_dashboard.replace('\n', '\r\n')
    new_dashboard = new_dashboard.replace('\n', '\r\n')

assert old_dashboard in code, "old_dashboard not found"
code = code.replace(old_dashboard, new_dashboard, 1)

# In dashboard render_template, add gamification
old_dash_render = "med_quantities=med_quantities\n        )"
new_dash_render = "med_quantities=med_quantities,\n            gamification=gamification\n        )"
if old_dash_render not in code:
    old_dash_render = old_dash_render.replace('\n', '\r\n')
    new_dash_render = new_dash_render.replace('\n', '\r\n')

assert old_dash_render in code, "old_dash_render not found"
code = code.replace(old_dash_render, new_dash_render, 1)

# 4. Update patients() ordering
old_pat_order = "patients_list = query.order_by(Patient.created_at.desc()).all()"
new_pat_order = """urgency_case = case(
            (Patient.urgency_level == 'EMERGENCY', 1),
            (Patient.urgency_level == 'URGENT', 2),
            else_=3
        )
        patients_list = query.order_by(urgency_case, Patient.created_at.desc()).all()"""

if old_pat_order not in code:
    old_pat_order = old_pat_order.replace('\n', '\r\n')
    new_pat_order = new_pat_order.replace('\n', '\r\n')

assert old_pat_order in code, "old_pat_order not found"
code = code.replace(old_pat_order, new_pat_order, 1)

# 5. Update patient_add()
old_pat_add_fields = """        name = request.form.get('name', '').strip()
        age_val = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()"""

new_pat_add_fields = """        name = request.form.get('name', '').strip()
        age_val = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        symptoms = request.form.get('symptoms', '').strip()
        urgency_level = request.form.get('urgency_level', 'NORMAL').strip().upper()
        if urgency_level not in ['NORMAL', 'URGENT', 'EMERGENCY']:
            urgency_level = 'NORMAL'"""

if old_pat_add_fields not in code:
    old_pat_add_fields = old_pat_add_fields.replace('\n', '\r\n')
    new_pat_add_fields = new_pat_add_fields.replace('\n', '\r\n')

assert old_pat_add_fields in code, "old_pat_add_fields not found"
code = code.replace(old_pat_add_fields, new_pat_add_fields, 1)

old_pat_save = """        new_patient = Patient(
            patient_uid=patient_uid,
            name=name,
            age=age,
            gender=gender,
            phone=phone if phone else None,
            address=address if address else None,
            photo_filename=photo_filename,
            qr_code_path=qr_code_rel_path
        )"""

new_pat_save = """        new_patient = Patient(
            patient_uid=patient_uid,
            name=name,
            age=age,
            gender=gender,
            phone=phone if phone else None,
            address=address if address else None,
            photo_filename=photo_filename,
            qr_code_path=qr_code_rel_path,
            symptoms=symptoms if symptoms else None,
            urgency_level=urgency_level
        )"""

if old_pat_save not in code:
    old_pat_save = old_pat_save.replace('\n', '\r\n')
    new_pat_save = new_pat_save.replace('\n', '\r\n')

assert old_pat_save in code, "old_pat_save not found"
code = code.replace(old_pat_save, new_pat_save, 1)

old_pat_flash = "flash(f'Patient {new_patient.name} successfully registered with UID {patient_uid}. QR Code generated with profile link!', 'success')"
new_pat_flash = """if urgency_level == 'EMERGENCY':
            flash(f'🚨 EMERGENCY: Patient {name} ({patient_uid}) registered with critical symptoms. Auto-prioritized to #1 in Doctor Queue!', 'danger')
        elif urgency_level == 'URGENT':
            flash(f'⚠️ URGENT: Patient {name} ({patient_uid}) registered with high-priority triage status.', 'warning')
        else:
            flash(f'Patient {new_patient.name} successfully registered with UID {patient_uid}. QR Code generated with profile link!', 'success')"""

if old_pat_flash not in code:
    old_pat_flash = old_pat_flash.replace('\n', '\r\n')
    new_pat_flash = new_pat_flash.replace('\n', '\r\n')

assert old_pat_flash in code, "old_pat_flash not found"
code = code.replace(old_pat_flash, new_pat_flash, 1)

# 6. Update appointments()
old_appt_order = "appointments_list = Appointment.query.order_by(Appointment.date.desc(), Appointment.id.desc()).all()"
new_appt_order = """urgency_case = case(
            (Patient.urgency_level == 'EMERGENCY', 1),
            (Patient.urgency_level == 'URGENT', 2),
            else_=3
        )
        appointments_list = Appointment.query.outerjoin(Patient).order_by(
            urgency_case,
            Appointment.date.desc(),
            Appointment.id.desc()
        ).all()"""

if old_appt_order not in code:
    old_appt_order = old_appt_order.replace('\n', '\r\n')
    new_appt_order = new_appt_order.replace('\n', '\r\n')

assert old_appt_order in code, "old_appt_order not found"
code = code.replace(old_appt_order, new_appt_order, 1)

# 7. Update patient_card() and patient_detail() to add wellness, journey_steps, symptom_schedule
old_card_render = """        return render_template(
            'patient_card.html',
            patient=patient,
            latest_record=latest_record,
            photo_url=photo_url,
            verification_url=verification_url,
            diet_plan=diet_plan,
            med_schedule=med_schedule,
            whatsapp_url=med_schedule['whatsapp_url'],
            ambulance_log=ambulance_log
        )"""

new_card_render = """        wellness = calculate_patient_wellness_score(patient, latest_record)
        journey_steps = get_patient_journey_steps(patient, latest_record)
        symptom_schedule = get_symptom_based_prescription(getattr(patient, 'symptoms', ''), patient.age, getattr(patient, 'urgency_level', 'NORMAL'))

        return render_template(
            'patient_card.html',
            patient=patient,
            latest_record=latest_record,
            photo_url=photo_url,
            verification_url=verification_url,
            diet_plan=diet_plan,
            med_schedule=med_schedule,
            whatsapp_url=med_schedule['whatsapp_url'],
            ambulance_log=ambulance_log,
            wellness=wellness,
            journey_steps=journey_steps,
            symptom_schedule=symptom_schedule
        )"""

if old_card_render not in code:
    old_card_render = old_card_render.replace('\n', '\r\n')
    new_card_render = new_card_render.replace('\n', '\r\n')

assert old_card_render in code, "old_card_render not found"
code = code.replace(old_card_render, new_card_render, 1)

old_detail_render = """        return render_template(
            'patient_detail.html',
            patient=patient,
            profile_url=profile_url,
            latest_record=latest_record,
            diet_plan=diet_plan,
            med_schedule=med_schedule,
            whatsapp_url=med_schedule['whatsapp_url'],
            ambulance_log=ambulance_log
        )"""

new_detail_render = """        wellness = calculate_patient_wellness_score(patient, latest_record)
        journey_steps = get_patient_journey_steps(patient, latest_record)
        symptom_schedule = get_symptom_based_prescription(getattr(patient, 'symptoms', ''), patient.age, getattr(patient, 'urgency_level', 'NORMAL'))

        return render_template(
            'patient_detail.html',
            patient=patient,
            profile_url=profile_url,
            latest_record=latest_record,
            diet_plan=diet_plan,
            med_schedule=med_schedule,
            whatsapp_url=med_schedule['whatsapp_url'],
            ambulance_log=ambulance_log,
            wellness=wellness,
            journey_steps=journey_steps,
            symptom_schedule=symptom_schedule
        )"""

if old_detail_render not in code:
    old_detail_render = old_detail_render.replace('\n', '\r\n')
    new_detail_render = new_detail_render.replace('\n', '\r\n')

assert old_detail_render in code, "old_detail_render not found"
code = code.replace(old_detail_render, new_detail_render, 1)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("app.py successfully upgraded with V3 features, sorting, and gamification!")
