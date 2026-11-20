"""
Smart Community Health Camp Management System - Core Application Entry Point
Enterprise Full-Stack Architecture with:
- Authentication & RBAC (Flask-Login, Werkzeug)
- Patient demographic management & photo uploads
- Dynamic QR code generation & ReportLab clinical PDF export
- Interactive GIS health camp mapping (Leaflet.js)
- Visual epidemiology & inventory analytics (Chart.js)
- Clinical records, appointments queue & pharmacy stock management
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)

import json
import uuid
from datetime import date, datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from werkzeug.utils import secure_filename

from config import Config
from models import (
    db, User, Patient, Doctor, Camp, Appointment, HealthRecord, Medicine,
    ConsultationRequest, SymptomReport, generate_10_digit_patient_id
)
from functools import wraps
import random
from email_service import send_otp_email
from flask import session

from utils import (
    allowed_file,
    generate_qr_code,
    generate_patient_pdf,
    regenerate_patient_qr_codes,
    generate_camp_pdf,
    ensure_default_qr,
    ensure_default_avatar,
    generate_official_prescription_package
)
from upgraded_features_v3 import (
    features_v3_bp,
    universal_health_chatbot,
    get_symptom_based_prescription,
    compute_camp_gamification,
    calculate_patient_wellness_score,
    get_patient_journey_steps
)
from sqlalchemy import case, func
from upgraded_features import (
    features_bp,
    MedicineInventory,
    MedicineReminder,
    AmbulanceDispatchLog,
    evaluate_vitals_triage,
    build_medicine_schedule_sms,
    recommend_diet_plan,
    deduct_medicine_inventory,
    init_medicine_inventory_seed
)


def create_app(config_class=Config) -> Flask:
    """Application Factory to configure and initialize the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. Ensure required static asset directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['QRCODE_FOLDER'], exist_ok=True)
    ensure_default_qr(app.config['QRCODE_FOLDER'])
    ensure_default_avatar(app.config['UPLOAD_FOLDER'])

    # 2. Initialize database
    db.init_app(app)

    # 2.1 Register Upgraded Features Blueprint
    app.register_blueprint(features_bp)
    app.register_blueprint(features_v3_bp)

    with app.app_context():
        try:
            db.create_all()
            # Database starts 100% clean - zero preloaded/dummy data
        except Exception as e:
            print(f"[WARN] Database initialization notice: {e}")

    # 3. Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Transparent parameter routing helper: allows 'id' and 'patient_id' to be used interchangeably in url_for
    @app.url_defaults
    def add_patient_id(endpoint, values):
        if endpoint in ('patient_detail', 'patient_card', 'patient_pdf', 'patient_update_photo', 'patient_delete', 'download_report', 'export_patient_pdf') and 'id' in values and 'patient_id' not in values:
            values['patient_id'] = values.pop('id')

    # ==========================================
    # Authentication & Root Routes
    # ==========================================


    # ==========================================
    # Role-Based Access Control (RBAC) Decorators
    # ==========================================

    def staff_only(f):
        """Restricts route access to Doctors, Staff, Volunteers, Coordinators, and Admins."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login', portal='doctor', tab='signin'))
            if current_user.is_patient():
                flash('Access restricted to healthcare providers and camp staff.', 'warning')
                return redirect(url_for('my_health_portal'))
            return f(*args, **kwargs)
        return decorated_function

    def patient_only(f):
        """Restricts route access exclusively to authenticated Patients."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login', portal='patient', tab='signin'))
            if not current_user.is_patient():
                flash('Clinical and administrative staff should use the Clinical Dashboard.', 'info')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function

    # ==========================================
    # Dual-Portal Authentication & Root Routes
    # ==========================================

    @app.route('/')
    def index():
        """Root landing route: redirects authenticated patients to /my-health-portal, staff to /dashboard, else login."""
        if current_user.is_authenticated:
            if current_user.is_patient():
                return redirect(url_for('my_health_portal'))
            return redirect(url_for('dashboard'))
        return redirect(url_for('login', portal='patient', tab='signin'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """
        Dual-Portal Unified Authentication Gateway.
        Supports Patient Portal and Doctor Portal navigation tabs.
        """
        if current_user.is_authenticated:
            if current_user.is_patient():
                return redirect(url_for('my_health_portal'))
            return redirect(url_for('dashboard'))

        portal = request.args.get('portal', 'patient').strip().lower()
        tab = request.args.get('tab', 'signin').strip().lower()

        if request.method == 'POST':
            # Support backwards compatible direct login POST
            portal_hint = request.form.get('portal', portal).strip().lower()
            if portal_hint == 'doctor':
                return doctor_login()
            else:
                return patient_login()

        return render_template('login.html', portal=portal, tab=tab)

    # -------------------------------------------------------------
    # PATIENT PORTAL ROUTES
    # -------------------------------------------------------------

    @app.route('/patient/signup', methods=['POST'])
    def patient_signup():
        """
        Patient Registration with Calendar DOB, cascading location, blood group, allergies,
        and mandatory 6-digit Gmail OTP verification.
        """
        if current_user.is_authenticated:
            return redirect(url_for('my_health_portal'))

        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_raw = request.form.get('dob', '').strip()
        age_raw = request.form.get('age', '').strip()
        gender = request.form.get('gender', 'Other').strip()
        blood_group = request.form.get('blood_group', '').strip()
        allergies = request.form.get('allergies', 'None').strip() or 'None'
        phone = request.form.get('phone', '').strip()
        country = request.form.get('country', 'India').strip()
        state = request.form.get('state', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not first_name or not email or not password:
            flash('First Name, Email, and Password are required fields.', 'danger')
            return redirect(url_for('login', portal='patient', tab='signup'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('login', portal='patient', tab='signup'))

        if password != confirm_password:
            flash('Passwords do not match. Please verify and re-enter.', 'danger')
            return redirect(url_for('login', portal='patient', tab='signup'))

        # Calculate Age from Date of Birth
        calculated_age = 25
        dob_date = None
        if dob_raw:
            try:
                dob_date = datetime.strptime(dob_raw, '%Y-%m-%d').date()
                today = date.today()
                calculated_age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
            except Exception:
                calculated_age = int(age_raw) if age_raw.isdigit() else 25
        elif age_raw.isdigit():
            calculated_age = int(age_raw)

        # Check existing user
        existing_user = User.query.filter(
            (func.lower(User.email) == email) | (func.lower(User.username) == email)
        ).first()

        if existing_user:
            if not existing_user.is_email_verified:
                session['pending_verification_email'] = email
                flash('An account with this email already exists but is unverified. Please enter your verification OTP.', 'warning')
                return redirect(url_for('verify_email', email=email))
            flash('An account with this email address already exists. Please sign in.', 'info')
            return redirect(url_for('login', portal='patient', tab='signin'))

        # Generate unique 10-digit Patient numeric ID
        ten_digit_id = generate_10_digit_patient_id()

        # Handle Beneficiary Photo Upload
        photo = request.files.get('photo')
        photo_filename = None
        if photo and photo.filename and allowed_file(photo.filename):
            try:
                import time
                from werkzeug.utils import secure_filename
                ext = os.path.splitext(secure_filename(photo.filename))[1]
                photo_filename = f"pt_{ten_digit_id}_{int(time.time())}{ext}"
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
            except Exception as e:
                print(f"[WARN] Beneficiary photo save notice: {e}")

        # Create Patient Demographic Record
        patient = Patient(
            patient_uid=ten_digit_id,
            first_name=first_name,
            last_name=last_name,
            name=f"{first_name} {last_name}".strip(),
            dob=dob_date,
            age=calculated_age,
            gender=gender,
            blood_group=blood_group,
            allergies=allergies,
            phone=phone,
            country=country or 'India',
            state=state,
            city=city,
            address=address,
            email=email,
            photo_filename=photo_filename,
            urgency_level='NORMAL'
        )
        db.session.add(patient)
        db.session.flush()

        # Generate rich smartphone-scannable QR pass encoding
        try:
            generate_qr_code(patient.patient_uid, app.config['QRCODE_FOLDER'], patient=patient)
        except Exception as e:
            print(f"[WARN] QR Generation notice: {e}")

        # Generate 6-digit OTP
        otp_code = f"{random.randint(100000, 999999)}"

        new_user = User(
            username=email,
            email=email,
            full_name=f"{first_name} {last_name}".strip(),
            role='Patient',
            phone=phone,
            patient_id=patient.id,
            is_email_verified=False,
            verification_otp=otp_code,
            otp_created_at=datetime.utcnow()
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        # Dispatch OTP strictly via Gmail SMTP
        email_sent, sent_msg = send_otp_email(email, otp_code, new_user.full_name)
        session['pending_verification_email'] = email

        if email_sent:
            flash(f'Verification code sent to {email}. Please check your Gmail inbox and enter the 6-digit OTP below to activate your account.', 'success')
        else:
            flash(f'Could not dispatch verification email: {sent_msg}. Please configure MAIL_USERNAME and MAIL_APP_PASSWORD in .env.', 'danger')

        return redirect(url_for('verify_email', email=email))

    @app.route('/verify-email', methods=['GET', 'POST'])
    def verify_email():
        """
        Email OTP Verification Route.
        Verifies 6-digit code sent to user Gmail and activates patient account.
        """
        target_email = request.args.get('email', '').strip().lower() or session.get('pending_verification_email', '').strip().lower()

        user = None
        if target_email:
            user = User.query.filter(func.lower(User.email) == target_email).first()

        if request.method == 'POST':
            submitted_email = request.form.get('email', '').strip().lower()
            submitted_otp = request.form.get('otp', '').strip()

            if not submitted_email or not submitted_otp:
                flash('Please provide both your registered email and the 6-digit OTP.', 'danger')
                return render_template('verify_email.html', email=submitted_email)

            v_user = User.query.filter(func.lower(User.email) == submitted_email).first()
            if not v_user:
                flash('Account not found with this email. Please sign up first.', 'danger')
                return redirect(url_for('login', portal='patient', tab='signup'))

            if v_user.is_email_verified:
                flash('Your email is already verified! Please sign in.', 'success')
                return redirect(url_for('login', portal='patient', tab='signin'))

            if not v_user.verification_otp or v_user.verification_otp.strip() != submitted_otp:
                flash('Invalid or expired verification code. Please check your Gmail and try again.', 'danger')
                return render_template('verify_email.html', email=submitted_email)

            # Verification successful
            v_user.is_email_verified = True
            v_user.verification_otp = None
            db.session.commit()

            session.pop('pending_verification_email', None)
            flash(f'Email verified successfully! Welcome, {v_user.full_name or "Patient"}. Please sign in to access your digital health portal.', 'success')
            return redirect(url_for('login', portal='patient', tab='signin'))

        return render_template('verify_email.html', email=target_email)

    @app.route('/resend-otp')
    def resend_otp():
        """Regenerate and resend 6-digit verification OTP."""
        target_email = request.args.get('email', '').strip().lower() or session.get('pending_verification_email', '').strip().lower()
        if not target_email:
            flash('No pending verification email found. Please register or sign in.', 'warning')
            return redirect(url_for('login', portal='patient', tab='signup'))

        user = User.query.filter(func.lower(User.email) == target_email).first()
        if not user:
            flash('Account not found with this email.', 'danger')
            return redirect(url_for('login', portal='patient', tab='signup'))

        if user.is_email_verified:
            flash('This account is already verified! Please sign in.', 'info')
            return redirect(url_for('login', portal='patient', tab='signin'))

        new_otp = f"{random.randint(100000, 999999)}"
        user.verification_otp = new_otp
        user.otp_created_at = datetime.utcnow()
        db.session.commit()

        email_sent, sent_msg = send_otp_email(user.email, new_otp, user.full_name)
        session['pending_verification_email'] = user.email

        if email_sent:
            flash(f'A fresh verification code has been dispatched to {user.email}. Please check your inbox.', 'success')
        else:
            flash(f'Could not dispatch email: {sent_msg}. Please configure MAIL_USERNAME and MAIL_APP_PASSWORD in .env.', 'danger')

        return redirect(url_for('verify_email', email=user.email))

    @app.route('/patient/login', methods=['POST'])
    def patient_login():
        """
        Patient Sign In Handler.
        Enforces email verification, guarantees unique 10-digit ID and smartphone-scannable QR pass,
        and securely routes to /my-health-portal.
        """
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False

        if not email or not password:
            flash('Please enter both your Email and Password.', 'danger')
            return redirect(url_for('login', portal='patient', tab='signin'))

        user = User.query.filter(
            (func.lower(User.email) == email) | (func.lower(User.username) == email)
        ).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password. Please verify credentials.', 'danger')
            return redirect(url_for('login', portal='patient', tab='signin'))

        if user.role != 'Patient':
            flash(f'This account is registered as {user.role}. Please sign in via the Doctor & Staff Portal.', 'info')
            return redirect(url_for('login', portal='doctor', tab='signin'))

        if not user.is_email_verified:
            session['pending_verification_email'] = user.email
            flash('Please verify your email address with the 6-digit OTP before signing in.', 'warning')
            return redirect(url_for('verify_email', email=user.email))

        # Ensure linked Patient record exists
        patient = user.patient_record
        if not patient and user.patient_id:
            patient = db.session.get(Patient, user.patient_id)

        if not patient:
            # Auto-create patient record if missing
            ten_digit_id = generate_10_digit_patient_id()
            patient = Patient(
                patient_uid=ten_digit_id,
                name=user.full_name or user.username,
                email=user.email,
                phone=user.phone or '',
                urgency_level='NORMAL'
            )
            db.session.add(patient)
            db.session.flush()
            user.patient_id = patient.id
            db.session.commit()

        # Guarantee unique 10-digit numeric ID & smartphone QR pass
        if not patient.patient_uid or not (len(str(patient.patient_uid)) == 10 and str(patient.patient_uid).isdigit()):
            patient.patient_uid = generate_10_digit_patient_id()
            db.session.commit()

        try:
            generate_qr_code(patient.patient_uid, app.config['QRCODE_FOLDER'], patient=patient)
        except Exception as e:
            print(f"[WARN] QR Generation error: {e}")

        login_user(user, remember=remember)
        display_name = patient.display_name or user.full_name or "Beneficiary"
        flash(f'Welcome back, {display_name}! Your Digital Health Portal is active.', 'success')
        return redirect(url_for('my_health_portal'))

    # -------------------------------------------------------------
    # DOCTOR & STAFF PORTAL ROUTES (NO PIN REQUIRED)
    # -------------------------------------------------------------

    @app.route('/doctor/signup', methods=['POST'])
    def doctor_signup():
        """
        Doctor / Clinical Staff Registration.
        Captures full credentials with NO PIN requirement. Automatically activates account.
        """
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        full_name = request.form.get('full_name', '').strip()
        license_number = request.form.get('license_number', '').strip()
        specialization = request.form.get('specialization', 'General Medicine').strip()
        qualification = request.form.get('qualification', 'MBBS').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not full_name or not email or not password:
            flash('Doctor Full Name, Email, and Password are required.', 'danger')
            return redirect(url_for('login', portal='doctor', tab='signup'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('login', portal='doctor', tab='signup'))

        if password != confirm_password:
            flash('Passwords do not match. Please verify and re-enter.', 'danger')
            return redirect(url_for('login', portal='doctor', tab='signup'))

        existing_user = User.query.filter(
            (func.lower(User.email) == email) | (func.lower(User.username) == email)
        ).first()

        if existing_user:
            flash('An account with this email address already exists. Please sign in.', 'warning')
            return redirect(url_for('login', portal='doctor', tab='signin'))

        # Create Doctor Record
        doc = Doctor(
            name=full_name,
            specialization=specialization or 'General Medicine',
            phone=phone,
            email=email,
            qualification=qualification,
            license_number=license_number,
            availability='Available'
        )
        db.session.add(doc)
        db.session.flush()

        # Create Doctor User (Verified by default)
        new_doc_user = User(
            username=email,
            email=email,
            full_name=full_name,
            role='Doctor',
            phone=phone,
            specialization=specialization,
            qualification=qualification,
            license_number=license_number,
            is_email_verified=True
        )
        new_doc_user.set_password(password)

        db.session.add(new_doc_user)
        db.session.commit()

        login_user(new_doc_user, remember=True)
        flash(f'Welcome, Dr. {full_name}! Your Doctor account is now active with full clinical access.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/doctor/login', methods=['POST'])
    def doctor_login():
        """
        Doctor & Healthcare Staff Sign In Handler.
        Opens full clinical dashboard with patient search, triage, prescriptions, and analytics.
        """
        username_or_email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False

        if not username_or_email or not password:
            flash('Please enter your Medical Email/Username and Password.', 'danger')
            return redirect(url_for('login', portal='doctor', tab='signin'))

        user = User.query.filter(
            (func.lower(User.username) == username_or_email) | (func.lower(User.email) == username_or_email)
        ).first()

        if not user or not user.check_password(password):
            flash('Invalid doctor credentials. Please check your credentials and try again.', 'danger')
            return redirect(url_for('login', portal='doctor', tab='signin'))

        if user.is_patient():
            flash('This is the Doctor & Staff Portal. Please sign in through the Patient Portal.', 'warning')
            return redirect(url_for('login', portal='patient', tab='signin'))

        login_user(user, remember=remember)
        display_name = user.full_name or user.username
        flash(f'Welcome back, Dr. {display_name}! Clinical Dashboard active.', 'success')
        return redirect(url_for('dashboard'))

    # -------------------------------------------------------------
    # PATIENT HEALTH PORTAL & EMERGENCY DIGITAL PASS
    # -------------------------------------------------------------

    @app.route('/my-health-portal')
    @login_required
    @patient_only
    def my_health_portal():
        """
        Dedicated Single-User Patient Health Portal with strict data isolation.
        Patients can ONLY view their own records, 10-digit ID, scannable QR pass,
        vitals, prescriptions, Indian diet plans, and AI assistant.
        """
        patient = current_user.patient_record
        if not patient and current_user.patient_id:
            patient = db.session.get(Patient, current_user.patient_id)

        if not patient:
            flash('Patient demographic profile not found. Please contact camp coordinator.', 'danger')
            return redirect(url_for('logout'))

        # Ensure guaranteed unique 10-digit numeric ID & smartphone QR pass
        if not patient.patient_uid or not (len(str(patient.patient_uid)) == 10 and str(patient.patient_uid).isdigit()):
            patient.patient_uid = generate_10_digit_patient_id()
            db.session.commit()

        qr_path = os.path.join(app.config['QRCODE_FOLDER'], f"patient_{patient.patient_uid}.png")
        if not os.path.exists(qr_path):
            generate_qr_code(patient.patient_uid, app.config['QRCODE_FOLDER'], patient=patient)

        # Strictly fetch this patient's records and remote consultation requests
        records = HealthRecord.query.filter_by(patient_id=patient.id).order_by(HealthRecord.created_at.desc()).all()
        latest_record = records[0] if records else None
        consultation_requests = ConsultationRequest.query.filter_by(patient_id=patient.id).order_by(ConsultationRequest.created_at.desc()).all()
        latest_consultation = consultation_requests[0] if consultation_requests else None
        ambulance_log = AmbulanceDispatchLog.query.filter_by(patient_id=patient.id).order_by(AmbulanceDispatchLog.dispatched_at.desc()).first()

        # Clinical aids
        prescription_text = getattr(latest_record, 'prescription', '') or ''
        diag_text = getattr(latest_record, 'diagnosis', '') or ''
        vitals_text = f"BP: {getattr(latest_record, 'systolic_bp', '')}/{getattr(latest_record, 'diastolic_bp', '')}, SpO2: {getattr(latest_record, 'spo2', '')}%" if latest_record and getattr(latest_record, 'systolic_bp', None) else ""

        diet_plan = recommend_diet_plan(diag_text, vitals_text, systolic=getattr(latest_record, 'systolic_bp', None), rbs=getattr(latest_record, 'blood_sugar', None))
        med_schedule = build_medicine_schedule_sms(patient, prescription_text, save_to_db=False)
        wellness = calculate_patient_wellness_score(patient, latest_record)
        journey_steps = get_patient_journey_steps(patient, latest_record)
        symptom_schedule = get_symptom_based_prescription(getattr(patient, 'symptoms', ''), patient.age or 30, getattr(patient, 'urgency_level', 'NORMAL'))

        # Dynamic official WhatsApp & SMS prescription package
        official_pkg = generate_official_prescription_package(
            patient,
            consultation_request=latest_consultation,
            health_record=latest_record
        )
        whatsapp_url = official_pkg['whatsapp_url']
        sms_url = official_pkg['sms_url']

        # Photo URL
        photo_url = None
        if patient.photo_filename:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], patient.photo_filename)
            if os.path.exists(full_path):
                photo_url = url_for('static', filename=f'uploads/{patient.photo_filename}')
        if not photo_url:
            photo_url = url_for('static', filename='uploads/default_avatar.png')

        verification_url = url_for('verify_pass', patient_uid=patient.patient_uid, _external=True)

        return render_template(
            'my_health_portal.html',
            patient=patient,
            records=records,
            latest_record=latest_record,
            consultation_requests=consultation_requests,
            latest_consultation=latest_consultation,
            official_pkg=official_pkg,
            photo_url=photo_url,
            verification_url=verification_url,
            diet_plan=diet_plan,
            med_schedule=med_schedule,
            whatsapp_url=whatsapp_url,
            sms_url=sms_url,
            ambulance_log=ambulance_log,
            wellness=wellness,
            journey_steps=journey_steps,
            symptom_schedule=symptom_schedule
        )

    @app.route('/patient/submit-symptoms', methods=['POST'])
    @login_required
    @patient_only
    def patient_submit_symptoms():
        """
        Allows authenticated patient to submit remote symptoms, allergies, duration,
        and select consultation preference: 'Sirf Advice Chahiye (Online Advice Only)'
        vs 'Camp Ko Aana Hai (Physical Camp Visit)'.
        """
        patient = current_user.patient_record
        if not patient and current_user.patient_id:
            patient = db.session.get(Patient, current_user.patient_id)

        if not patient:
            flash('Beneficiary profile not found. Please contact support.', 'danger')
            return redirect(url_for('my_health_portal'))

        symptoms = request.form.get('symptoms', '').strip()
        allergies = request.form.get('allergies', '').strip()
        duration = request.form.get('duration', '1-2 days').strip()
        preference = request.form.get('consultation_preference', 'Sirf Advice Chahiye (Online Advice Only)').strip()

        if not symptoms:
            flash('Please describe your symptoms and concerns before submitting.', 'warning')
            return redirect(url_for('my_health_portal'))

        # Update patient demographic symptoms and allergies
        patient.symptoms = symptoms
        if allergies:
            patient.allergies = allergies

        new_req = ConsultationRequest(
            patient_id=patient.id,
            symptoms=symptoms,
            duration=duration,
            allergies=allergies or patient.allergies or 'None',
            consultation_preference=preference,
            status='Pending Review'
        )
        db.session.add(new_req)
        db.session.commit()

        flash('Your health report has been submitted to camp doctors! Clinical tele-advice and tablet dosage will appear here in real time once reviewed.', 'success')
        return redirect(url_for('my_health_portal'))

    @app.route('/consult/<int:patient_id>', methods=['GET', 'POST'])
    @login_required
    @staff_only
    def doctor_consult_patient(patient_id):
        """
        Direct Doctor Consultation Action pre-bound to exact patient.
        Streamlined for Online Advice and in-person consultations:
        - Automatically binds current doctor (current_user)
        - Automatically assigns active camp venue
        - Removes camp, doctor, and vitals selection overhead
        - Directly captures Priority (Normal/Urgent), Primary Diagnosis,
          Prescription & Dosage (with pharmacy deduction), and Clinical Notes/Diet
        - Synchronizes Patient Portal in real time and triggers phone SMS notification
        """
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('Patient beneficiary record not found.', 'danger')
            return redirect(url_for('dashboard'))

        consultation_request = ConsultationRequest.query.filter_by(
            patient_id=patient.id
        ).order_by(ConsultationRequest.created_at.desc()).first()

        active_camp = Camp.query.filter(Camp.status != 'Completed').order_by(Camp.date.desc()).first()
        if not active_camp:
            active_camp = Camp.query.order_by(Camp.date.desc()).first()

        if request.method == 'POST':
            priority = request.form.get('priority', 'Normal').strip()
            diagnosis = request.form.get('diagnosis', '').strip()
            prescription = request.form.get('prescription', '').strip()
            doctor_notes = request.form.get('doctor_notes', '').strip()

            if not diagnosis:
                flash('Primary Diagnosis is a mandatory clinical field.', 'danger')
                return render_template(
                    'consult.html',
                    patient=patient,
                    consultation_request=consultation_request,
                    active_camp=active_camp
                )

            # Resolve Doctor entity for current_user
            doctor = Doctor.query.filter(
                (Doctor.email == current_user.email) | (Doctor.name == current_user.full_name)
            ).first()
            if not doctor:
                doctor = Doctor(
                    name=current_user.full_name or current_user.username,
                    specialization=getattr(current_user, 'specialization', 'Camp Medical Officer') or 'Camp Medical Officer',
                    qualification=getattr(current_user, 'qualification', 'MBBS') or 'MBBS',
                    license_number=getattr(current_user, 'license_number', 'REG-2026') or 'REG-2026',
                    email=current_user.email,
                    phone=current_user.phone
                )
                db.session.add(doctor)
                db.session.flush()

            # Resolve Camp
            camp = active_camp
            if not camp:
                camp = Camp(
                    title="Smart Community Health Camp",
                    location_name=patient.location_display or "Central Outreach Camp",
                    date=date.today(),
                    status="Ongoing"
                )
                db.session.add(camp)
                db.session.flush()

            # Priority & Urgency Update
            is_urgent = (priority.upper() == 'URGENT')
            patient.urgency_level = 'URGENT' if is_urgent else 'NORMAL'

            # 1. Create HealthRecord
            new_record = HealthRecord(
                patient_id=patient.id,
                doctor_id=doctor.id,
                camp_id=camp.id,
                diagnosis=diagnosis,
                prescription=prescription if prescription else None,
                doctor_notes=doctor_notes if doctor_notes else None,
                is_critical=is_urgent,
                triage_priority='URGENT_YELLOW' if is_urgent else 'NORMAL_GREEN'
            )
            db.session.add(new_record)
            db.session.flush()

            # 2. Update ConsultationRequest if present
            target_req = consultation_request
            if target_req:
                target_req.doctor_id = doctor.id
                target_req.camp_id = camp.id
                target_req.clinical_advice = diagnosis
                target_req.diet_recommendations = doctor_notes
                target_req.visit_decision = f"{target_req.consultation_preference} (Flagged {priority})"
                target_req.health_record_id = new_record.id
                target_req.status = 'Reviewed / Advice Sent'
                target_req.reviewed_at = datetime.utcnow()

            # 3. Deduct pharmacy inventory
            if prescription:
                deduct_medicine_inventory(prescription)

            db.session.commit()

            # 4. Generate dynamic SMS & WhatsApp notification package
            from sms_service import build_consultation_sms_package
            sms_pkg = build_consultation_sms_package(
                patient=patient,
                doctor_name=doctor.name,
                diagnosis=diagnosis,
                prescription=prescription,
                doctor_notes=doctor_notes,
                priority=priority,
                host_url=request.host_url
            )
            session['last_consult_sms'] = {
                'patient_name': patient.name,
                'phone': patient.phone,
                'phone_intl': sms_pkg['phone_intl'],
                'sms_link': sms_pkg['sms_link'],
                'wa_link': sms_pkg['wa_link'],
                'api_dispatched': sms_pkg['api_dispatched'],
                'api_message': sms_pkg['api_message']
            }

            flash(f"Clinical consultation saved successfully for {patient.name}! Updated on their Patient Portal instantaneously.", "success")
            return redirect(url_for('dashboard'))

        return render_template(
            'consult.html',
            patient=patient,
            consultation_request=consultation_request,
            active_camp=active_camp
        )

    @app.route('/doctor/respond-consultation/<int:request_id>', methods=['POST'])
    @login_required
    @staff_only
    def doctor_respond_consultation(request_id):
        """
        Doctor reviews remote patient symptom report, determines visit decision
        (Online Advice vs Physical Camp Visit), enters diagnosis, specifies tablets
        with Morning / Afternoon / Night dosage, and custom food/diet advice.
        Pushes updates to the patient portal in real-time.
        """
        req = db.session.get(ConsultationRequest, request_id)
        if not req:
            flash('Consultation request record not found.', 'danger')
            return redirect(request.referrer or url_for('dashboard'))

        doctor_id = request.form.get('doctor_id', type=int)
        camp_id = request.form.get('camp_id', type=int)
        visit_decision = request.form.get('visit_decision', 'Online Advice: Rest at home & take online medicines').strip()
        clinical_advice = request.form.get('clinical_advice', '').strip()
        morning_tablets = request.form.get('morning_tablets', '').strip()
        afternoon_tablets = request.form.get('afternoon_tablets', '').strip()
        night_tablets = request.form.get('night_tablets', '').strip()
        diet_recommendations = request.form.get('diet_recommendations', '').strip()

        if not clinical_advice or not camp_id or not doctor_id:
            flash('Please select Camp Venue, Attending Doctor, and enter Clinical Advice.', 'danger')
            return redirect(request.referrer or url_for('dashboard'))

        req.doctor_id = doctor_id
        req.camp_id = camp_id
        req.visit_decision = visit_decision
        req.clinical_advice = clinical_advice
        req.morning_tablets = morning_tablets if morning_tablets else None
        req.afternoon_tablets = afternoon_tablets if afternoon_tablets else None
        req.night_tablets = night_tablets if night_tablets else None
        req.diet_recommendations = diet_recommendations if diet_recommendations else None
        req.status = 'Reviewed / Advice Sent'
        req.reviewed_at = datetime.utcnow()

        # Build structured prescription summary
        rx_lines = []
        if morning_tablets: rx_lines.append(f"Morning (08:00 AM): {morning_tablets}")
        if afternoon_tablets: rx_lines.append(f"Afternoon (01:30 PM): {afternoon_tablets}")
        if night_tablets: rx_lines.append(f"Night (08:30 PM): {night_tablets}")
        full_prescription = "\n".join(rx_lines) if rx_lines else "Rest and hydration as instructed by camp physician."

        is_crit = ('emergency' in visit_decision.lower())

        # Create linked HealthRecord
        health_rec = HealthRecord(
            patient_id=req.patient_id,
            doctor_id=doctor_id,
            camp_id=camp_id,
            diagnosis=clinical_advice,
            prescription=full_prescription,
            doctor_notes=f"Visit Decision: {visit_decision}\nDiet: {diet_recommendations}",
            is_critical=is_crit,
            triage_priority='EMERGENCY_RED' if is_crit else 'NORMAL_GREEN'
        )
        db.session.add(health_rec)
        db.session.flush()
        req.health_record_id = health_rec.id

        # Deduct pharmacy inventory if applicable
        deduct_medicine_inventory(full_prescription)

        db.session.commit()

        # Generate dynamic official prescription package
        pkg = generate_official_prescription_package(
            req.patient,
            doctor=db.session.get(Doctor, doctor_id),
            camp=db.session.get(Camp, camp_id),
            consultation_request=req,
            health_record=health_rec
        )

        flash(f"Clinical advice & prescription successfully sent to {req.patient.name}! Updated on their Patient Portal in real time.", 'success')
        return redirect(request.referrer or url_for('dashboard'))

    @app.route('/verify-pass/<patient_uid>')
    def verify_pass(patient_uid):
        """
        Public Emergency Digital Health Pass Verification View.
        Scanned via smartphone cameras: shows verified badge, 10-digit ID, patient identity,
        blood group, allergies warning, and emergency contacts while keeping clinical notes private.
        """
        cleaned_uid = str(patient_uid).strip()
        patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_uid)).first()

        if not patient and cleaned_uid.isdigit():
            patient = db.session.get(Patient, int(cleaned_uid))

        if not patient:
            flash('Invalid or unrecognized Health Pass QR Code.', 'danger')
            return render_template('patient_not_found.html', patient_id=patient_uid), 404

        photo_url = None
        if patient.photo_filename:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], patient.photo_filename)
            if os.path.exists(full_path):
                photo_url = url_for('static', filename=f'uploads/{patient.photo_filename}')
        if not photo_url:
            photo_url = url_for('static', filename='uploads/default_avatar.png')

        return render_template(
            'verify_pass.html',
            patient=patient,
            photo_url=photo_url
        )


    @app.route('/logout')
    @login_required
    def logout():
        """Sign out the currently authenticated user."""
        is_pt = current_user.is_patient()
        logout_user()
        flash('You have been successfully logged out.', 'info')
        if is_pt:
            return redirect(url_for('login', portal='patient', tab='signin'))
        return redirect(url_for('login', portal='doctor', tab='signin'))


    # ==========================================
    # Dashboard & Visual Analytics (Chart.js)
    # ==========================================

    @app.route('/dashboard')
    @login_required
    @staff_only
    def dashboard():
        """
        Executive overview dashboard with top metric cards, stock alerts,
        recent patients, and two Chart.js visual charts.
        """
        total_patients = Patient.query.count()
        total_doctors = Doctor.query.count()
        total_camps = Camp.query.count()
        total_appointments = Appointment.query.count()

        all_camps = Camp.query.all()
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
        low_stock_medicines = Medicine.query.filter(Medicine.quantity <= Medicine.reorder_level).all()

        # Chart 1 Data: Beneficiaries registered by Age Group (Bar chart)
        age_labels = ['0-18 yrs', '19-35 yrs', '36-50 yrs', '51-65 yrs', '65+ yrs']
        c_0_18 = Patient.query.filter(Patient.age <= 18).count()
        c_19_35 = Patient.query.filter(Patient.age > 18, Patient.age <= 35).count()
        c_36_50 = Patient.query.filter(Patient.age > 35, Patient.age <= 50).count()
        c_51_65 = Patient.query.filter(Patient.age > 50, Patient.age <= 65).count()
        c_65_plus = Patient.query.filter(Patient.age > 65).count()
        age_data = [c_0_18, c_19_35, c_36_50, c_51_65, c_65_plus]

        # Chart 2 Data: Top medicines inventory stock status (Doughnut chart)
        all_medicines = Medicine.query.order_by(Medicine.quantity.desc()).limit(7).all()
        med_labels = [m.name for m in all_medicines]
        med_quantities = [m.quantity for m in all_medicines]

        # Incoming Remote Symptom Reports & Consultation Requests
        consultation_requests = ConsultationRequest.query.order_by(
            case((ConsultationRequest.status == 'Pending Review', 1), else_=2),
            ConsultationRequest.created_at.desc()
        ).all()
        pending_requests_count = len([r for r in consultation_requests if r.status == 'Pending Review'])

        return render_template(
            'dashboard.html',
            total_patients=total_patients,
            total_doctors=total_doctors,
            total_camps=total_camps,
            total_appointments=total_appointments,
            recent_patients=recent_patients,
            upcoming_camps=upcoming_camps,
            low_stock_medicines=low_stock_medicines,
            age_labels=age_labels,
            age_data=age_data,
            med_labels=med_labels,
            med_quantities=med_quantities,
            gamification=gamification,
            consultation_requests=consultation_requests,
            pending_requests_count=pending_requests_count,
            all_doctors=all_doctors,
            all_camps=all_camps
        )

    # ==========================================
    # Patient Management, Photo Upload & QR
    # ==========================================

    @app.route('/patients')
    @login_required
    @staff_only
    def patients():
        """Patient directory with search query and demographic filters."""
        search = request.args.get('search', '').strip()
        gender_filter = request.args.get('gender', '').strip()

        query = Patient.query

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Patient.name.ilike(search_term)) |
                (Patient.patient_uid.ilike(search_term)) |
                (Patient.phone.ilike(search_term))
            )

        if gender_filter:
            query = query.filter(Patient.gender == gender_filter)

        urgency_case = case(
            (Patient.urgency_level == 'EMERGENCY', 1),
            (Patient.urgency_level == 'URGENT', 2),
            else_=3
        )
        patients_list = query.order_by(urgency_case, Patient.created_at.desc()).all()
        return render_template('patients.html', patients=patients_list, search=search, gender_filter=gender_filter)

    @app.route('/patient/add', methods=['POST'])
    @login_required
    @staff_only
    def patient_add():
        """
        Register a new patient, handle photo upload to static/uploads/,
        generate a unique UID and dynamic QR Code health pass.
        """
        name = request.form.get('name', '').strip()
        age_val = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        symptoms = request.form.get('symptoms', '').strip()
        urgency_level = request.form.get('urgency_level', 'NORMAL').strip().upper()
        if urgency_level not in ['NORMAL', 'URGENT', 'EMERGENCY']:
            urgency_level = 'NORMAL'

        if not name or not age_val or not gender:
            flash('Please fill in all required fields (Name, Age, Gender).', 'danger')
            return redirect(url_for('patients'))

        try:
            age = int(age_val)
        except ValueError:
            flash('Age must be a valid integer.', 'danger')
            return redirect(url_for('patients'))

        # 1. Handle Photo File Upload
        photo_filename = None
        file = request.files.get('photo')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Unsupported file format for photo. Allowed formats: PNG, JPG, JPEG, WEBP.', 'danger')
                return redirect(url_for('patients'))
            try:
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                ext = file.filename.rsplit('.', 1)[1].lower()
                clean_name = secure_filename(file.filename.rsplit('.', 1)[0])
                unique_filename = f"pat_{int(datetime.utcnow().timestamp())}_{clean_name}.{ext}"
                target_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(target_path)
                photo_filename = unique_filename
            except Exception as e:
                flash(f'Could not save uploaded photo: {str(e)}', 'warning')

        # 2. Generate Unique Patient UID
        count_existing = Patient.query.count() + 1
        year_str = datetime.utcnow().strftime('%Y')
        patient_uid = f"PAT-{year_str}-{count_existing:04d}"

        # Ensure UID is strictly unique
        while Patient.query.filter_by(patient_uid=patient_uid).first():
            count_existing += 1
            patient_uid = f"PAT-{year_str}-{count_existing:04d}"

        # 3. Generate Dynamic QR Code Image with valid profile URL
        if request.host_url and 'localhost' not in request.host_url:
            base = request.host_url.rstrip('/')
        else:
            base = os.environ.get('BASE_APP_URL', 'http://127.0.0.1:5000').rstrip('/')
        profile_url = f"{base}/patient_card/{patient_uid}"
        qr_code_rel_path = generate_qr_code(patient_uid, app.config['QRCODE_FOLDER'], profile_url=profile_url)

        # 4. Save to Database
        new_patient = Patient(
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
        )
        db.session.add(new_patient)
        db.session.commit()

        if urgency_level == 'EMERGENCY':
            flash(f'🚨 EMERGENCY: Patient {name} ({patient_uid}) registered with critical symptoms. Auto-prioritized to #1 in Doctor Queue!', 'danger')
        elif urgency_level == 'URGENT':
            flash(f'⚠️ URGENT: Patient {name} ({patient_uid}) registered with high-priority triage status.', 'warning')
        else:
            flash(f'Patient {new_patient.name} successfully registered with UID {patient_uid}. QR Code generated with profile link!', 'success')
        return redirect(url_for('patient_detail', patient_id=new_patient.patient_uid))

    @app.route('/patient/<patient_id>/update-photo', methods=['POST'])
    @app.route('/patient/<int:id>/update-photo', methods=['POST'])
    @login_required
    def patient_update_photo(patient_id=None, id=None):
        """Upload or replace beneficiary photo directly from the clinical profile page."""
        target_id = patient_id if patient_id is not None else id
        patient = None
        cleaned_id = str(target_id).strip()
        if cleaned_id.isdigit():
            patient = db.session.get(Patient, int(cleaned_id))
        if not patient:
            patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_id)).first()

        if not patient:
            flash('Patient record not found.', 'danger')
            return redirect(url_for('patients'))

        file = request.files.get('photo')
        if not file or not file.filename:
            flash('No photo file was selected for upload.', 'warning')
            return redirect(url_for('patient_detail', patient_id=patient.patient_uid))

        if not allowed_file(file.filename):
            flash('Unsupported file format. Please upload a PNG, JPG, JPEG, or WEBP image.', 'danger')
            return redirect(url_for('patient_detail', patient_id=patient.patient_uid))

        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            ext = file.filename.rsplit('.', 1)[1].lower()
            clean_name = secure_filename(file.filename.rsplit('.', 1)[0])
            unique_filename = f"pat_{patient.id}_{int(datetime.utcnow().timestamp())}_{clean_name}.{ext}"
            target_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(target_path)

            if patient.photo_filename:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], patient.photo_filename)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            patient.photo_filename = unique_filename
            db.session.commit()
            flash(f'Identification photo successfully updated for {patient.name}!', 'success')
        except Exception as e:
            flash(f'An error occurred while uploading the photo: {str(e)}', 'danger')

        return redirect(url_for('patient_detail', patient_id=patient.patient_uid))

    @app.route('/patient_card/<patient_id>')
    @app.route('/patient_card/<int:id>')
    def patient_card(patient_id=None, id=None):
        """
        Dedicated Patient Digital ID & Clinical Verification Card.
        Accessible by scanning the patient QR code or visiting /patient_card/<patient_id>.
        Fetches patient demographic record, verified photo path, and latest HealthRecord / consultation notes.
        """
        target_id = patient_id if patient_id is not None else id
        cleaned_id = str(target_id).strip()
        patient = None

        # 1. Lookup by alphanumeric patient_uid (e.g. 'PAT-2026-0001')
        patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_id)).first()

        # 2. Fallback to primary key lookup if integer
        if not patient and cleaned_id.isdigit():
            patient = db.session.get(Patient, int(cleaned_id))

        if not patient:
            flash(f'Patient record "{target_id}" was not found in our community health camp database.', 'danger')
            return render_template('patient_not_found.html', patient_id=target_id), 404

        # Strict Patient Data Isolation Check
        if current_user.is_authenticated and current_user.is_patient():
            user_pid = current_user.patient_id
            user_puid = getattr(current_user.patient_record, 'patient_uid', '')
            if patient.id != user_pid and patient.patient_uid != user_puid:
                flash('Access denied. You can only view your own medical profile.', 'danger')
                return redirect(url_for('my_health_portal'))

        # Strict Patient Data Isolation Check
        if current_user.is_authenticated and current_user.is_patient():
            user_pid = current_user.patient_id
            user_puid = getattr(current_user.patient_record, 'patient_uid', '')
            if patient.id != user_pid and patient.patient_uid != user_puid:
                flash('Access denied. You can only view your own digital health card.', 'danger')
                return redirect(url_for('my_health_portal'))

        # Fetch latest clinical consultation record
        latest_record = HealthRecord.query.filter_by(patient_id=patient.id).order_by(HealthRecord.created_at.desc()).first()

        # Resolve photo with fallback to default_avatar.png
        photo_url = None
        if patient.photo_filename:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], patient.photo_filename)
            if os.path.exists(full_path):
                photo_url = url_for('static', filename=f'uploads/{patient.photo_filename}')

        if not photo_url:
            ensure_default_avatar(app.config['UPLOAD_FOLDER'])
            photo_url = url_for('static', filename='uploads/default_avatar.png')

        # Full verification URL
        verification_url = url_for('patient_card', patient_id=patient.patient_uid, _external=True)

        # Build personalized diet and medicine timing schedule
        prescription_text = getattr(latest_record, 'prescription', '') or ''
        diag_text = getattr(latest_record, 'diagnosis', '') or ''
        vitals_text = f"BP: {getattr(latest_record, 'systolic_bp', '')}/{getattr(latest_record, 'diastolic_bp', '')}, SpO2: {getattr(latest_record, 'spo2', '')}%" if latest_record and getattr(latest_record, 'systolic_bp', None) else ""

        diet_plan = recommend_diet_plan(diag_text, vitals_text, systolic=getattr(latest_record, 'systolic_bp', None), rbs=getattr(latest_record, 'blood_sugar', None))
        med_schedule = build_medicine_schedule_sms(patient, prescription_text, save_to_db=False)
        ambulance_log = AmbulanceDispatchLog.query.filter_by(patient_id=patient.id).order_by(AmbulanceDispatchLog.dispatched_at.desc()).first()

        wellness = calculate_patient_wellness_score(patient, latest_record)
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
        )

    @app.route('/patient/<patient_id>')
    @app.route('/patient/<int:id>')
    def patient_detail(patient_id=None, id=None):
        """
        Patient profile display.
        Accessible by scanning the QR code or visiting /patient/<patient_id>.
        Accepts either unique patient_uid (e.g. PAT-2026-0001) or primary key ID.
        """
        target_id = patient_id if patient_id is not None else id
        patient = None
        cleaned_id = str(target_id).strip()

        # 1. Lookup by alphanumeric patient_uid (e.g. 'PAT-2026-0001')
        patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_id)).first()

        # 2. Fallback to primary key lookup if integer
        if not patient and cleaned_id.isdigit():
            patient = db.session.get(Patient, int(cleaned_id))

        if not patient:
            flash(f'Patient record "{target_id}" was not found in our community health camp database.', 'danger')
            return render_template('patient_not_found.html', patient_id=target_id), 404

        # Strict Patient Data Isolation Check
        if current_user.is_authenticated and current_user.is_patient():
            user_pid = current_user.patient_id
            user_puid = getattr(current_user.patient_record, 'patient_uid', '')
            if patient.id != user_pid and patient.patient_uid != user_puid:
                flash('Access denied. You can only view your own medical profile.', 'danger')
                return redirect(url_for('my_health_portal'))

        # Strict Patient Data Isolation Check
        if current_user.is_authenticated and current_user.is_patient():
            user_pid = current_user.patient_id
            user_puid = getattr(current_user.patient_record, 'patient_uid', '')
            if patient.id != user_pid and patient.patient_uid != user_puid:
                flash('Access denied. You can only view your own digital health card.', 'danger')
                return redirect(url_for('my_health_portal'))

        profile_url = url_for('patient_detail', patient_id=patient.patient_uid, _external=True)
        latest_record = HealthRecord.query.filter_by(patient_id=patient.id).order_by(HealthRecord.created_at.desc()).first()
        prescription_text = getattr(latest_record, 'prescription', '') or ''
        diag_text = getattr(latest_record, 'diagnosis', '') or ''
        vitals_text = f"BP: {getattr(latest_record, 'systolic_bp', '')}/{getattr(latest_record, 'diastolic_bp', '')}, SpO2: {getattr(latest_record, 'spo2', '')}%" if latest_record and getattr(latest_record, 'systolic_bp', None) else ""

        diet_plan = recommend_diet_plan(diag_text, vitals_text, systolic=getattr(latest_record, 'systolic_bp', None), rbs=getattr(latest_record, 'blood_sugar', None))
        med_schedule = build_medicine_schedule_sms(patient, prescription_text, save_to_db=False)
        ambulance_log = AmbulanceDispatchLog.query.filter_by(patient_id=patient.id).order_by(AmbulanceDispatchLog.dispatched_at.desc()).first()

        wellness = calculate_patient_wellness_score(patient, latest_record)
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
        )

    @app.route('/patient/<patient_id>/pdf')
    @app.route('/patient/<int:id>/pdf')
    @login_required
    def patient_pdf(patient_id=None, id=None):
        """
        Generate and stream the official PDF medical card and encounter history
        for a patient using ReportLab. Defensively handles any missing attributes.
        """
        target_id = patient_id if patient_id is not None else id
        patient = None
        cleaned_id = str(target_id).strip()
        if cleaned_id.isdigit():
            patient = db.session.get(Patient, int(cleaned_id))
        if not patient:
            patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_id)).first()

        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('patients'))

        # Strict Patient Data Isolation Check
        if current_user.is_authenticated and current_user.is_patient():
            user_pid = current_user.patient_id
            user_puid = getattr(current_user.patient_record, 'patient_uid', '')
            if patient.id != user_pid and patient.patient_uid != user_puid:
                flash('Access denied. You can only download your own medical PDF pass.', 'danger')
                return redirect(url_for('my_health_portal'))

        records = getattr(patient, 'health_records', [])
        pdf_buffer = generate_patient_pdf(patient, records)
        safe_uid = getattr(patient, 'patient_uid', getattr(patient, 'patient_id', f'PAT-{patient.id}'))
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{safe_uid}_Medical_Card.pdf"
        )

    @app.route('/download_report/<patient_id>')
    @app.route('/download_report/<int:id>')
    @login_required
    def download_report(patient_id=None, id=None):
        """Direct patient medical card download endpoint."""
        return patient_pdf(patient_id=patient_id, id=id)

    @app.route('/export_patient_pdf/<patient_id>')
    @app.route('/export_patient_pdf/<int:id>')
    @login_required
    def export_patient_pdf(patient_id=None, id=None):
        """Export patient medical history PDF."""
        return patient_pdf(patient_id=patient_id, id=id)

    @app.route('/camp_report/<int:camp_id>')
    @login_required
    @staff_only
    def camp_report(camp_id):
        """Generate and stream health camp report PDF."""
        camp = db.session.get(Camp, camp_id)
        if not camp:
            flash('Health camp record not found.', 'danger')
            return redirect(url_for('camps'))
        appointments = Appointment.query.filter_by(camp_id=camp.id).all()
        pdf_buffer = generate_camp_pdf(camp, appointments)
        clean_title = secure_filename(getattr(camp, 'title', f'camp_{camp.id}')).replace(' ', '_')
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Camp_Report_{clean_title}_{camp.id}.pdf"
        )

    @app.route('/patient/<patient_id>/delete', methods=['POST'])
    @app.route('/patient/<int:id>/delete', methods=['POST'])
    @login_required
    @staff_only
    def patient_delete(patient_id=None, id=None):
        """Delete patient and associated health records."""
        target_id = patient_id if patient_id is not None else id
        patient = None
        cleaned_id = str(target_id).strip()
        if cleaned_id.isdigit():
            patient = db.session.get(Patient, int(cleaned_id))
        if not patient:
            patient = Patient.query.filter(Patient.patient_uid.ilike(cleaned_id)).first()

        if patient:
            if patient.photo_filename:
                photo_full = os.path.join(app.config['UPLOAD_FOLDER'], patient.photo_filename)
                if os.path.exists(photo_full):
                    try:
                        os.remove(photo_full)
                    except OSError:
                        pass
            if patient.qr_code_path:
                qr_full = os.path.join(app.config['STATIC_FOLDER'], patient.qr_code_path)
                if os.path.exists(qr_full):
                    try:
                        os.remove(qr_full)
                    except OSError:
                        pass

            db.session.delete(patient)
            db.session.commit()
            flash('Patient record and digital passes removed successfully.', 'info')
        else:
            flash('Patient not found.', 'danger')
        return redirect(url_for('patients'))

    # ==========================================
    # Health Camps & Interactive Leaflet GIS Map
    # ==========================================

    @app.route('/camps')
    @login_required
    @staff_only
    def camps():
        """Interactive Leaflet.js health camp operations and geo-map view."""
        camps_list = Camp.query.order_by(Camp.date.asc()).all()
        camps_json = json.dumps([c.to_dict() for c in camps_list])
        today_str = date.today().strftime('%Y-%m-%d')
        return render_template('camps.html', camps=camps_list, camps_json=camps_json, today_str=today_str)

    @app.route('/camp/add', methods=['POST'])
    @login_required
    @staff_only
    def camp_add():
        """Add and schedule a new health camp location with coordinates."""
        title = request.form.get('title', '').strip()
        location_name = request.form.get('location_name', '').strip()
        lat_val = request.form.get('latitude', '').strip()
        lng_val = request.form.get('longitude', '').strip()
        date_str = request.form.get('date', '').strip()
        target_beneficiaries = int(request.form.get('target_beneficiaries', 100))
        status = request.form.get('status', 'Upcoming').strip()

        if not title or not location_name or not date_str:
            flash('Please provide title, location name, and date.', 'danger')
            return redirect(url_for('camps'))

        try:
            camp_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            camp_date = date.today()

        lat = float(lat_val) if lat_val else None
        lng = float(lng_val) if lng_val else None

        new_camp = Camp(
            title=title,
            location_name=location_name,
            latitude=lat,
            longitude=lng,
            date=camp_date,
            target_beneficiaries=target_beneficiaries,
            status=status
        )
        db.session.add(new_camp)
        db.session.commit()

        flash(f'Health Camp "{title}" successfully scheduled.', 'success')
        return redirect(url_for('camps'))

    # ==========================================
    # Doctors & Medical Staff
    # ==========================================

    @app.route('/doctors')
    @login_required
    @staff_only
    def doctors():
        """Directory of empaneled doctors and clinical specialists."""
        doctors_list = Doctor.query.order_by(Doctor.name.asc()).all()
        return render_template('doctors.html', doctors=doctors_list)

    @app.route('/doctor/add', methods=['POST'])
    @login_required
    @staff_only
    def doctor_add():
        """Empanel a new medical officer."""
        name = request.form.get('name', '').strip()
        specialization = request.form.get('specialization', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        availability = request.form.get('availability', 'Available').strip()

        if not name or not specialization:
            flash('Please provide doctor name and specialization.', 'danger')
            return redirect(url_for('doctors'))

        new_doc = Doctor(
            name=name,
            specialization=specialization,
            phone=phone if phone else None,
            email=email if email else None,
            availability=availability
        )
        db.session.add(new_doc)
        db.session.commit()

        flash(f'Doctor {name} empaneled successfully.', 'success')
        return redirect(url_for('doctors'))

    # ==========================================
    # Consultations & Appointments Queue
    # ==========================================

    @app.route('/appointments')
    @login_required
    @staff_only
    def appointments():
        """Doctor consultation queue and appointment scheduling."""
        urgency_case = case(
            (Patient.urgency_level == 'EMERGENCY', 1),
            (Patient.urgency_level == 'URGENT', 2),
            else_=3
        )
        appointments_list = Appointment.query.outerjoin(Patient).order_by(
            urgency_case,
            Appointment.date.desc(),
            Appointment.id.desc()
        ).all()
        urgency_case = case((Patient.urgency_level == 'EMERGENCY', 1), (Patient.urgency_level == 'URGENT', 2), else_=3)
        patients_list = Patient.query.order_by(urgency_case.asc(), Patient.name.asc()).all()
        doctors_list = Doctor.query.order_by(Doctor.name.asc()).all()
        camps_list = Camp.query.order_by(Camp.date.asc()).all()

        selected_doctor_id = request.args.get('doctor_id', type=int)
        today_str = date.today().strftime('%Y-%m-%d')

        return render_template(
            'appointments.html',
            appointments=appointments_list,
            patients=patients_list,
            doctors=doctors_list,
            camps=camps_list,
            selected_doctor_id=selected_doctor_id,
            today_str=today_str
        )

    @app.route('/appointment/add', methods=['POST'])
    @login_required
    @staff_only
    def appointment_add():
        """Book a consultation appointment token for a patient."""
        patient_id = request.form.get('patient_id', type=int)
        doctor_id = request.form.get('doctor_id', type=int)
        camp_id = request.form.get('camp_id', type=int)
        date_str = request.form.get('date', '').strip()
        time_str = request.form.get('time', '10:00 AM').strip()

        if not patient_id or not doctor_id or not camp_id or not date_str:
            flash('Please complete all required appointment fields.', 'danger')
            return redirect(url_for('appointments'))

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            appt_date = date.today()

        new_appt = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            camp_id=camp_id,
            date=appt_date,
            time=time_str,
            status='Scheduled'
        )
        db.session.add(new_appt)
        db.session.commit()

        flash('Consultation token booked successfully.', 'success')
        return redirect(url_for('appointments'))

    @app.route('/appointment/<int:id>/status', methods=['POST'])
    @login_required
    @staff_only
    def appointment_status(id):
        """Update appointment queue status."""
        appt = db.session.get(Appointment, id)
        if appt:
            new_status = request.form.get('status', 'Scheduled').strip()
            appt.status = new_status
            db.session.commit()
            flash(f'Appointment status updated to "{new_status}".', 'info')
        return redirect(url_for('appointments'))

    # ==========================================
    # Clinical Health Records & Encounters
    # ==========================================

    @app.route('/records')
    @login_required
    @staff_only
    def records():
        """Clinical records directory and consultation history with triage priority."""
        # Prioritize Red-Flag Critical patients at the top of the queue
        records_list = HealthRecord.query.order_by(HealthRecord.is_critical.desc(), HealthRecord.created_at.desc()).all()
        urgency_case = case((Patient.urgency_level == 'EMERGENCY', 1), (Patient.urgency_level == 'URGENT', 2), else_=3)
        patients_list = Patient.query.order_by(urgency_case.asc(), Patient.name.asc()).all()
        doctors_list = Doctor.query.order_by(Doctor.name.asc()).all()
        camps_list = Camp.query.order_by(Camp.date.asc()).all()
        inventory_items = MedicineInventory.query.order_by(MedicineInventory.name.asc()).all()
        ambulance_logs = AmbulanceDispatchLog.query.order_by(AmbulanceDispatchLog.dispatched_at.desc()).limit(10).all()

        selected_patient_id = request.args.get('patient_id', type=int)
        critical_records = [r for r in records_list if getattr(r, 'is_critical', False)]
        consultation_requests = ConsultationRequest.query.order_by(
            case((ConsultationRequest.status == 'Pending Review', 1), else_=2),
            ConsultationRequest.created_at.desc()
        ).all()

        return render_template(
            'records.html',
            records=records_list,
            patients=patients_list,
            doctors=doctors_list,
            camps=camps_list,
            inventory_items=inventory_items,
            ambulance_logs=ambulance_logs,
            critical_records=critical_records,
            consultation_requests=consultation_requests,
            selected_patient_id=selected_patient_id
        )

    @app.route('/record/add', methods=['POST'])
    @login_required
    @staff_only
    def record_add():
        """Record a completed medical consultation, diagnosis, vitals triage, and prescription."""
        patient_id = request.form.get('patient_id', type=int)
        doctor_id = request.form.get('doctor_id', type=int)
        camp_id = request.form.get('camp_id', type=int)
        diagnosis = request.form.get('diagnosis', '').strip()
        prescription = request.form.get('prescription', '').strip()
        doctor_notes = request.form.get('doctor_notes', '').strip()

        # Vitals extraction
        systolic_bp = request.form.get('systolic_bp', type=int)
        diastolic_bp = request.form.get('diastolic_bp', type=int)
        blood_sugar = request.form.get('blood_sugar', type=float)
        spo2 = request.form.get('spo2', type=float)
        pulse_rate = request.form.get('pulse_rate', type=int)

        if not patient_id or not doctor_id or not camp_id or not diagnosis:
            flash('Please select patient, doctor, camp, and provide a diagnosis.', 'danger')
            return redirect(url_for('records'))

        patient = db.session.get(Patient, patient_id)

        # 1. Critical Vitals Triage Assessment
        triage_res = evaluate_vitals_triage(systolic_bp, diastolic_bp, blood_sugar, spo2, pulse_rate)

        new_record = HealthRecord(
            patient_id=patient_id,
            doctor_id=doctor_id,
            camp_id=camp_id,
            diagnosis=diagnosis,
            prescription=prescription if prescription else None,
            doctor_notes=doctor_notes if doctor_notes else None,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
            blood_sugar=blood_sugar,
            spo2=spo2,
            pulse_rate=pulse_rate,
            is_critical=triage_res['is_critical'],
            triage_priority=triage_res['priority']
        )
        db.session.add(new_record)
        db.session.commit()

        # 2. Live Inventory Stock Deduction
        inv_results = []
        if prescription:
            inv_results = deduct_medicine_inventory(prescription)

        # 3. Automated Medicine Timing SMS & Reminders
        whatsapp_url = None
        if prescription and patient:
            reminder_res = build_medicine_schedule_sms(patient, prescription, save_to_db=True)
            whatsapp_url = reminder_res['whatsapp_url']

        # 4. Generate Personalized Indian Diet Recommendation
        diet_plan = recommend_diet_plan(diagnosis, triage_res['summary'], systolic=systolic_bp, rbs=blood_sugar)

        # Notification & Alert Banners
        if triage_res['is_critical']:
            flash(
                f"🚨 RED-FLAG EMERGENCY: Patient {patient.name} has CRITICAL vitals ({triage_res['reasons_text']})! CALL AMBULANCE (108) or log referral immediately.",
                'danger'
            )
        else:
            flash(f"Clinical consultation record saved successfully for {patient.name}.", 'success')

        for item in inv_results:
            if item.get('warning'):
                flash(f"⚠️ Inventory Notice: {item['warning']}", 'warning')

        return redirect(url_for('records', patient_id=patient_id))

    # ==========================================
    # Pharmacy Inventory & Stock Management
    # ==========================================

    @app.route('/inventory')
    @login_required
    @staff_only
    def inventory():
        """Pharmaceutical inventory overview and batch stock monitoring."""
        medicines_list = Medicine.query.order_by(Medicine.name.asc()).all()
        total_quantity = sum(m.quantity for m in medicines_list)
        low_stock_count = sum(1 for m in medicines_list if m.is_low_stock)
        total_valuation = sum(m.quantity * m.unit_price for m in medicines_list)

        return render_template(
            'inventory.html',
            medicines=medicines_list,
            total_quantity=total_quantity,
            low_stock_count=low_stock_count,
            total_valuation=total_valuation
        )

    @app.route('/medicine/add', methods=['POST'])
    @login_required
    @staff_only
    def medicine_add():
        """Register a new pharmaceutical stock batch."""
        name = request.form.get('name', '').strip()
        batch_number = request.form.get('batch_number', '').strip()
        qty_val = request.form.get('quantity', '0').strip()
        expiry_str = request.form.get('expiry_date', '').strip()
        reorder_val = request.form.get('reorder_level', '20').strip()
        price_val = request.form.get('unit_price', '0.0').strip()

        if not name or not batch_number or not expiry_str:
            flash('Please fill in medicine name, batch number, and expiry date.', 'danger')
            return redirect(url_for('inventory'))

        try:
            quantity = int(qty_val)
            reorder_level = int(reorder_val)
            unit_price = float(price_val)
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid numeric or date input.', 'danger')
            return redirect(url_for('inventory'))

        new_med = Medicine(
            name=name,
            batch_number=batch_number,
            quantity=quantity,
            expiry_date=expiry_date,
            unit_price=unit_price,
            reorder_level=reorder_level
        )
        db.session.add(new_med)
        db.session.commit()

        flash(f'Medicine batch "{name} ({batch_number})" added to inventory.', 'success')
        return redirect(url_for('inventory'))

    @app.route('/medicine/<int:id>/update-stock', methods=['POST'])
    @login_required
    @staff_only
    def medicine_update_stock(id):
        """Update inventory stock quantity and reorder threshold for a medicine."""
        med = db.session.get(Medicine, id)
        if med:
            qty_val = request.form.get('quantity', '').strip()
            reorder_val = request.form.get('reorder_level', '').strip()

            if qty_val:
                med.quantity = int(qty_val)
            if reorder_val:
                med.reorder_level = int(reorder_val)

            db.session.commit()
            flash(f'Stock updated for {med.name} ({med.batch_number}). Current stock: {med.quantity}.', 'success')
        return redirect(url_for('inventory'))

    # ==========================================
    # API & Health Check
    # ==========================================

    @app.route('/api/health')
    def api_health():
        """System health and heartbeat check endpoint."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected'
        })

    # CLI command for manual database seeding/re-creation
    @app.cli.command("init-db")
    def cli_init_db():
        """Initialize the database and seed initial demo data via CLI."""
        init_db_data(app)
        print("Database initialized and demo data seeded successfully.")

    @app.cli.command("regenerate-qrs")
    def cli_regenerate_qrs():
        """Regenerate QR codes for all patients with valid profile URLs."""
        count = regenerate_patient_qr_codes(app, "http://127.0.0.1:5000")
        print(f"Regenerated {count} patient QR codes with full application profile URLs.")

    return app


def init_db_data(app: Flask):
    """
    Database initialization helper.
    Creates schema tables and seeds demo records (Admin, Doctors, Camps, Patients, Medicines, Consultations).
    """
    with app.app_context():
        db.create_all()

        # 1. Seed Default Admin
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', role='Admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("[INFO] Created default admin account: admin / admin123")

        # 2. Seed Empaneled Doctors
        if Doctor.query.count() < 2:
            d1 = Doctor(
                name="Dr. Priya Sharma",
                specialization="General Medicine & Family Health",
                phone="+91 98765 43210",
                email="dr.priya@healthcamp.org",
                availability="Available"
            )
            d2 = Doctor(
                name="Dr. Vikram Deshmukh",
                specialization="Pediatrics & Child Care",
                phone="+91 98765 12345",
                email="dr.vikram@healthcamp.org",
                availability="Available"
            )
            d3 = Doctor(
                name="Dr. Sneha Kulkarni",
                specialization="Cardiology & Hypertension Care",
                phone="+91 98765 67890",
                email="dr.sneha@healthcamp.org",
                availability="Available"
            )
            db.session.add_all([d1, d2, d3])
            db.session.commit()
            print("[INFO] Seeded empaneled doctors.")

        # 3. Seed Geo-Tagged Health Camps
        if Camp.query.count() < 2:
            c1 = Camp(
                title="Nagpur Urban Primary Health Camp 2026",
                location_name="Community Civic Hall, Ward 12, Nagpur",
                latitude=21.1458,
                longitude=79.0882,
                date=date.today(),
                target_beneficiaries=200,
                status="Upcoming"
            )
            c2 = Camp(
                title="Rural Outreach Mobile Health Unit",
                location_name="Gram Panchayat Hall, Kalmeshwar, Nagpur",
                latitude=21.2319,
                longitude=78.9192,
                date=date.today(),
                target_beneficiaries=150,
                status="Upcoming"
            )
            c3 = Camp(
                title="Kamptee Free Eye & General Checkup Camp",
                location_name="Municipal High School Ground, Kamptee",
                latitude=21.2227,
                longitude=79.1994,
                date=date.today(),
                target_beneficiaries=250,
                status="Ongoing"
            )
            db.session.add_all([c1, c2, c3])
            db.session.commit()
            print("[INFO] Seeded geo-tagged health camps.")

        # 4. Seed Diverse Age Demographics Patients
        if Patient.query.count() < 4:
            patients_seed = [
                ("PAT-2026-0001", "Ramesh Kumar Patel", 48, "Male", "+91 91234 56789", "Plot 45, Anand Nagar, Nagpur"),
                ("PAT-2026-0002", "Aarav Deshmukh", 11, "Male", "+91 92345 67890", "Ward 3, Kalmeshwar, Nagpur"),
                ("PAT-2026-0003", "Ananya Verma", 26, "Female", "+91 93456 78901", "Flat 204, Shanti Heights, Nagpur"),
                ("PAT-2026-0004", "Gangadhar Rao", 72, "Male", "+91 94567 89012", "Old Basti, Sector 2, Kamptee"),
                ("PAT-2026-0005", "Sunita Bai Meshram", 56, "Female", "+91 95678 90123", "House 18, Tribal Colony, Kalmeshwar")
            ]

            for uid, name, age, gender, phone, addr in patients_seed:
                if not Patient.query.filter_by(patient_uid=uid).first():
                    qr_path = generate_qr_code(uid, app.config['QRCODE_FOLDER'])
                    p = Patient(
                        patient_uid=uid,
                        name=name,
                        age=age,
                        gender=gender,
                        phone=phone,
                        address=addr,
                        qr_code_path=qr_path
                    )
                    db.session.add(p)
            db.session.commit()
            print("[INFO] Seeded diverse demographic patient records.")

        # 5. Seed Medicine Inventory
        if Medicine.query.count() < 4:
            meds = [
                Medicine(name="Paracetamol 500mg", batch_number="PCM-2026-A1", quantity=450, expiry_date=date(2027, 12, 31), unit_price=1.50, reorder_level=100),
                Medicine(name="Amoxicillin 250mg", batch_number="AMX-2026-B2", quantity=45, expiry_date=date(2027, 6, 30), unit_price=3.20, reorder_level=50),
                Medicine(name="Cetirizine 10mg", batch_number="CTZ-2026-C3", quantity=180, expiry_date=date(2028, 3, 15), unit_price=1.10, reorder_level=40),
                Medicine(name="Metformin 500mg", batch_number="MTF-2026-M4", quantity=320, expiry_date=date(2027, 9, 30), unit_price=2.00, reorder_level=60),
                Medicine(name="Amlodipine 5mg", batch_number="AML-2026-K5", quantity=25, expiry_date=date(2027, 8, 31), unit_price=1.80, reorder_level=40),
                Medicine(name="ORS Hydration Sachets", batch_number="ORS-2026-P6", quantity=600, expiry_date=date(2028, 1, 1), unit_price=5.00, reorder_level=100)
            ]
            for m in meds:
                if not Medicine.query.filter_by(batch_number=m.batch_number).first():
                    db.session.add(m)
            db.session.commit()
            print("[INFO] Seeded pharmacy medicine batches.")

        # 6. Seed Consultations and Health Records
        if HealthRecord.query.count() == 0:
            p1 = Patient.query.filter_by(patient_uid="PAT-2026-0001").first()
            d1 = Doctor.query.first()
            c1 = Camp.query.first()

            if p1 and d1 and c1:
                hr = HealthRecord(
                    patient_id=p1.id,
                    doctor_id=d1.id,
                    camp_id=c1.id,
                    diagnosis="Essential Hypertension Stage 1 & Mild Seasonal Rhinitis",
                    prescription="1. Tab Amlodipine 5mg - 1 tab OD morning after breakfast x 30 days\n2. Tab Cetirizine 10mg - 1 tab HS if needed x 5 days",
                    doctor_notes="Advised low-sodium diet and daily 30-minute brisk walk. Follow-up blood pressure check at next mobile camp."
                )
                appt = Appointment(
                    patient_id=p1.id,
                    doctor_id=d1.id,
                    camp_id=c1.id,
                    date=date.today(),
                    time="10:30 AM",
                    status="Completed"
                )
                db.session.add_all([hr, appt])
                db.session.commit()
                print("[INFO] Seeded clinical health record and appointment token.")

        # 7. Ensure all registered patients have valid profile URL QR codes
        updated_qrs = regenerate_patient_qr_codes(app, "http://127.0.0.1:5000")
        if updated_qrs > 0:
            print(f"[INFO] Verified and updated {updated_qrs} patient QR codes with scannable profile URLs.")


# Application instance for WSGI / local execution
app = create_app()


import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    local_ip = get_local_ip()
    print("\n" + "="*60)
    print("🏥 SMART COMMUNITY HEALTH CAMP SYSTEM IS RUNNING!")
    print(f"➜ This Laptop Access : http://127.0.0.1:5000")
    print(f"➜ Other Laptops/Phone: http://{local_ip}:5000")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
