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
from models import db, User, Patient, Doctor, Camp, Appointment, HealthRecord, Medicine
from utils import (
    allowed_file,
    generate_qr_code,
    generate_patient_pdf,
    regenerate_patient_qr_codes,
    generate_camp_pdf,
    ensure_default_qr,
    ensure_default_avatar
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

    @app.route('/')
    def index():
        """Root landing route: redirects to dashboard if authenticated, else login."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login handler with credential validation and session establishment."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            remember = True if request.form.get('remember') else False

            if not username or not password:
                flash('Please provide both username and password.', 'danger')
                return render_template('login.html')

            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                login_user(user, remember=remember)
                flash(f'Welcome back, {user.username}! Signed in as {user.role}.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid username or password. Please try again.', 'danger')

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        """Sign out the currently authenticated user."""
        logout_user()
        flash('You have been successfully logged out.', 'info')
        return redirect(url_for('login'))

    # ==========================================
    # Dashboard & Visual Analytics (Chart.js)
    # ==========================================

    @app.route('/dashboard')
    @login_required
    def dashboard():
        """
        Executive overview dashboard with top metric cards, stock alerts,
        recent patients, and two Chart.js visual charts.
        """
        total_patients = Patient.query.count()
        total_doctors = Doctor.query.count()
        total_camps = Camp.query.count()
        total_appointments = Appointment.query.count()

        recent_patients = Patient.query.order_by(Patient.created_at.desc()).limit(5).all()
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
            med_quantities=med_quantities
        )

    # ==========================================
    # Patient Management, Photo Upload & QR
    # ==========================================

    @app.route('/patients')
    @login_required
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

        patients_list = query.order_by(Patient.created_at.desc()).all()
        return render_template('patients.html', patients=patients_list, search=search, gender_filter=gender_filter)

    @app.route('/patient/add', methods=['POST'])
    @login_required
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
            qr_code_path=qr_code_rel_path
        )
        db.session.add(new_patient)
        db.session.commit()

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

        return render_template(
            'patient_card.html',
            patient=patient,
            latest_record=latest_record,
            photo_url=photo_url,
            verification_url=verification_url
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

        profile_url = url_for('patient_detail', patient_id=patient.patient_uid, _external=True)
        return render_template('patient_detail.html', patient=patient, profile_url=profile_url)

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
    def camps():
        """Interactive Leaflet.js health camp operations and geo-map view."""
        camps_list = Camp.query.order_by(Camp.date.asc()).all()
        camps_json = json.dumps([c.to_dict() for c in camps_list])
        today_str = date.today().strftime('%Y-%m-%d')
        return render_template('camps.html', camps=camps_list, camps_json=camps_json, today_str=today_str)

    @app.route('/camp/add', methods=['POST'])
    @login_required
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
    def doctors():
        """Directory of empaneled doctors and clinical specialists."""
        doctors_list = Doctor.query.order_by(Doctor.name.asc()).all()
        return render_template('doctors.html', doctors=doctors_list)

    @app.route('/doctor/add', methods=['POST'])
    @login_required
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
    def appointments():
        """Doctor consultation queue and appointment scheduling."""
        appointments_list = Appointment.query.order_by(Appointment.date.desc(), Appointment.id.desc()).all()
        patients_list = Patient.query.order_by(Patient.name.asc()).all()
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
    def records():
        """Clinical records directory and consultation history."""
        records_list = HealthRecord.query.order_by(HealthRecord.created_at.desc()).all()
        patients_list = Patient.query.order_by(Patient.name.asc()).all()
        doctors_list = Doctor.query.order_by(Doctor.name.asc()).all()
        camps_list = Camp.query.order_by(Camp.date.asc()).all()

        selected_patient_id = request.args.get('patient_id', type=int)

        return render_template(
            'records.html',
            records=records_list,
            patients=patients_list,
            doctors=doctors_list,
            camps=camps_list,
            selected_patient_id=selected_patient_id
        )

    @app.route('/record/add', methods=['POST'])
    @login_required
    def record_add():
        """Record a completed medical consultation, diagnosis, and prescription."""
        patient_id = request.form.get('patient_id', type=int)
        doctor_id = request.form.get('doctor_id', type=int)
        camp_id = request.form.get('camp_id', type=int)
        diagnosis = request.form.get('diagnosis', '').strip()
        prescription = request.form.get('prescription', '').strip()
        doctor_notes = request.form.get('doctor_notes', '').strip()

        if not patient_id or not doctor_id or not camp_id or not diagnosis:
            flash('Please select patient, doctor, camp, and provide a diagnosis.', 'danger')
            return redirect(url_for('records'))

        new_record = HealthRecord(
            patient_id=patient_id,
            doctor_id=doctor_id,
            camp_id=camp_id,
            diagnosis=diagnosis,
            prescription=prescription if prescription else None,
            doctor_notes=doctor_notes if doctor_notes else None
        )
        db.session.add(new_record)
        db.session.commit()

        flash('Clinical consultation record saved successfully.', 'success')
        return redirect(url_for('records'))

    # ==========================================
    # Pharmacy Inventory & Stock Management
    # ==========================================

    @app.route('/inventory')
    @login_required
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
