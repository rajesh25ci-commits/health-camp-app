"""
SQLAlchemy Database Models for Smart Community Health Camp Management System.
Defines entity models for Users, Patients, Doctors, Camps, Appointments,
Health Records, and Inventory/Medicines, with explicit relationships and helper methods.
Includes strict role support for Dual-Portal (Patient vs Doctor & Clinical Staff).
"""

import random
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy instance
db = SQLAlchemy()


def generate_10_digit_patient_id() -> str:
    """
    Generate a guaranteed unique 10-digit numeric Patient ID (e.g., 7391048265).
    Checks against existing Patient records to avoid collisions.
    """
    while True:
        candidate = str(random.randint(1000000000, 9999999999))
        if not Patient.query.filter_by(patient_uid=candidate).first():
            return candidate


class User(UserMixin, db.Model):
    """
    User entity representing portal operators and registered patients.
    Supports Dual-Portal authentication:
    - 'Patient' (personal health pass & data isolation)
    - 'Doctor', 'Admin', 'Pharmacist', 'Receptionist', 'Emergency Staff'
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default='Patient')  # 'Patient', 'Doctor', 'Admin', 'Pharmacist', 'Receptionist', 'Emergency Staff'
    phone = db.Column(db.String(20), nullable=True)

    # Email Verification attributes
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_otp = db.Column(db.String(10), nullable=True)
    otp_created_at = db.Column(db.DateTime, nullable=True)

    # Professional Medical Credentials (for Doctor/Clinical Staff)
    license_number = db.Column(db.String(80), nullable=True)  # NMC / State Medical Council ID
    specialization = db.Column(db.String(120), nullable=True)  # General Physician, Cardiologist, Pediatrician, etc.
    qualification = db.Column(db.String(100), nullable=True)   # MBBS, MD, B.Pharm, etc.

    # Patient Association (for Patient role)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    patient_record = db.relationship('Patient', backref=db.backref('user_account', uselist=False), foreign_keys=[patient_id])

    def set_password(self, password: str) -> None:
        """Hash plain-text password using PBKDF2/scrypt and store hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify plain-text password against stored password hash."""
        return check_password_hash(self.password_hash, password)

    def is_patient(self) -> bool:
        """Check if user is a registered Patient."""
        return self.role == 'Patient'

    def is_admin(self) -> bool:
        """Check if user has Admin privileges."""
        return self.role == 'Admin'

    def is_doctor(self) -> bool:
        """Check if user has Doctor privileges."""
        return self.role in ('Doctor', 'Admin')

    def is_pharmacist(self) -> bool:
        """Check if user has Pharmacist privileges."""
        return self.role in ('Pharmacist', 'Admin')

    def is_receptionist(self) -> bool:
        """Check if user has Receptionist privileges."""
        return self.role in ('Receptionist', 'Admin', 'Coordinator')

    def is_emergency_staff(self) -> bool:
        """Check if user has Emergency triage/108 privileges."""
        return self.role in ('Emergency Staff', 'Emergency', 'Doctor', 'Admin')

    def is_volunteer(self) -> bool:
        """Check if user has Volunteer privileges."""
        return self.role in ('Volunteer', 'Receptionist', 'Admin')

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}' email='{self.email}'>"


class Patient(db.Model):
    """
    Patient entity registered at community health camps or via self-service Patient Portal.
    Maintains complete demographic profile, unique 10-digit ID, DOB, location,
    blood group, known allergies, and scannable Digital Health Pass QR.
    """
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    patient_uid = db.Column(db.String(32), unique=True, nullable=False, index=True)  # Guaranteed 10-digit numeric ID (e.g. '7391048265')
    first_name = db.Column(db.String(60), nullable=True)
    last_name = db.Column(db.String(60), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.Date, nullable=True)  # Calendar DOB picker
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)  # 'Male', 'Female', 'Other'
    blood_group = db.Column(db.String(10), nullable=True, default='O+')  # 'A+', 'B+', 'O+', etc.
    allergies = db.Column(db.Text, nullable=True, default='None')       # 'Penicillin', 'Sulfa', 'None'
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)

    # Cascading Location
    country = db.Column(db.String(80), nullable=True, default='India')
    state = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)

    photo_filename = db.Column(db.String(255), nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    symptoms = db.Column(db.Text, nullable=True)
    urgency_level = db.Column(db.String(20), default='NORMAL', nullable=False)  # 'NORMAL', 'URGENT', 'EMERGENCY'
    temperature = db.Column(db.Float, default=98.6, nullable=True)

    # Relationships
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')
    health_records = db.relationship('HealthRecord', backref='patient', lazy=True, cascade='all, delete-orphan')
    consultation_requests = db.relationship('ConsultationRequest', backref='patient', lazy=True, cascade='all, delete-orphan')

    @property
    def patient_id(self) -> str:
        """Alias for patient_uid to guarantee backwards compatibility."""
        return self.patient_uid

    @property
    def display_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.name or "Beneficiary"

    @property
    def formatted_dob(self) -> str:
        if self.dob:
            return self.dob.strftime('%Y-%m-%d')
        return "N/A"

    @property
    def location_display(self) -> str:
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else (self.address or "India")

    def to_dict(self) -> dict:
        """Serialize patient details for API / view consumption."""
        return {
            'id': self.id,
            'patient_uid': self.patient_uid,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'name': self.name,
            'dob': self.formatted_dob,
            'age': self.age,
            'gender': self.gender,
            'blood_group': self.blood_group,
            'allergies': self.allergies,
            'phone': self.phone,
            'email': self.email,
            'country': self.country,
            'state': self.state,
            'city': self.city,
            'location': self.location_display,
            'address': self.address,
            'photo_filename': self.photo_filename,
            'qr_code_path': self.qr_code_path,
            'symptoms': self.symptoms,
            'urgency_level': self.urgency_level,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self) -> str:
        return f"<Patient id={self.id} uid='{self.patient_uid}' name='{self.name}'>"


class Doctor(db.Model):
    """
    Doctor entity representing medical professionals participating in health camps.
    """
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    license_number = db.Column(db.String(80), nullable=True)
    specialization = db.Column(db.String(100), nullable=False)  # General Medicine, Pediatrics, Cardiology, etc.
    qualification = db.Column(db.String(100), nullable=True)   # MBBS, MD, etc.
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    availability = db.Column(db.String(100), default='Available', nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    health_records = db.relationship('HealthRecord', backref='doctor', lazy=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'license_number': self.license_number,
            'specialization': self.specialization,
            'qualification': self.qualification,
            'phone': self.phone,
            'email': self.email,
            'photo_filename': self.photo_filename,
            'availability': self.availability
        }

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} name='{self.name}' spec='{self.specialization}'>"


class Camp(db.Model):
    """
    Camp entity representing a community health camp event.
    Stores geospatial location, schedule date, and target capacity.
    """
    __tablename__ = 'camps'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    location_name = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    target_beneficiaries = db.Column(db.Integer, default=100, nullable=False)
    status = db.Column(db.String(20), default='Upcoming', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    appointments = db.relationship('Appointment', backref='camp', lazy=True)
    health_records = db.relationship('HealthRecord', backref='camp', lazy=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'location_name': self.location_name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'target_beneficiaries': self.target_beneficiaries,
            'status': self.status
        }

    def __repr__(self) -> str:
        return f"<Camp id={self.id} title='{self.title}' date='{self.date}'>"


class Appointment(db.Model):
    """
    Appointment entity scheduling a consultation between a Patient and Doctor at a Camp.
    """
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    camp_id = db.Column(db.Integer, db.ForeignKey('camps.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    time = db.Column(db.String(20), nullable=False)  # e.g., '10:00 AM'
    status = db.Column(db.String(20), default='Scheduled', nullable=False)  # 'Scheduled', 'In-Progress', 'Completed', 'Cancelled'
    slot_number = db.Column(db.Integer, default=1, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    systolic_bp = db.Column(db.Integer, nullable=True)
    diastolic_bp = db.Column(db.Integer, nullable=True)
    blood_sugar = db.Column(db.Float, nullable=True)
    spo2 = db.Column(db.Float, nullable=True)
    pulse_rate = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Float, default=98.6, nullable=True)
    is_critical = db.Column(db.Boolean, default=False, nullable=True)
    triage_priority = db.Column(db.String(20), default='NORMAL_GREEN', nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.name if self.patient else None,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.name if self.doctor else None,
            'camp_id': self.camp_id,
            'camp_title': self.camp.title if self.camp else None,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'time': self.time,
            'status': self.status,
            'slot_number': self.slot_number
        }

    def __repr__(self) -> str:
        return f"<Appointment id={self.id} patient_id={self.patient_id} doctor_id={self.doctor_id} status='{self.status}'>"


class HealthRecord(db.Model):
    """
    HealthRecord entity encapsulating medical observations, diagnosis,
    prescription, AI risk assessment, and doctor notes from a consultation.
    """
    __tablename__ = 'health_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    camp_id = db.Column(db.Integer, db.ForeignKey('camps.id'), nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    prescription = db.Column(db.Text, nullable=True)
    doctor_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Vitals
    systolic_bp = db.Column(db.Integer, nullable=True)
    diastolic_bp = db.Column(db.Integer, nullable=True)
    blood_sugar = db.Column(db.Float, nullable=True)
    spo2 = db.Column(db.Float, nullable=True)
    pulse_rate = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Float, default=98.6, nullable=True)
    is_critical = db.Column(db.Boolean, default=False, nullable=True)
    triage_priority = db.Column(db.String(20), default='NORMAL_GREEN', nullable=True)

    # AI Health Risk Assessment
    risk_level = db.Column(db.String(20), default='LOW RISK', nullable=True)  # 'LOW RISK', 'MEDIUM RISK', 'HIGH RISK'
    risk_reason = db.Column(db.Text, nullable=True)

    # Post-Camp Patient Follow-up Tracker
    followup_date = db.Column(db.Date, nullable=True)
    followup_status = db.Column(db.String(30), default='None', nullable=True)  # 'None', 'Scheduled', 'Reminded', 'Completed'
    followup_notes = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'camp_id': self.camp_id,
            'diagnosis': self.diagnosis,
            'prescription': self.prescription,
            'doctor_notes': self.doctor_notes,
            'risk_level': self.risk_level,
            'risk_reason': self.risk_reason,
            'followup_date': self.followup_date.strftime('%Y-%m-%d') if self.followup_date else None,
            'followup_status': self.followup_status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    def __repr__(self) -> str:
        return f"<HealthRecord id={self.id} patient_id={self.patient_id} doctor_id={self.doctor_id}>"


class Medicine(db.Model):
    """
    Medicine entity managing medical camp inventory and pharmacy stock.
    Tracks batch number, quantity, expiry date, pricing, and reorder levels.
    """
    __tablename__ = 'medicines'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    batch_number = db.Column(db.String(50), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    unit_price = db.Column(db.Float, default=0.0, nullable=False)
    reorder_level = db.Column(db.Integer, default=10, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level

    @property
    def is_expired(self) -> bool:
        return self.expiry_date < date.today()

    @property
    def is_expiring_soon(self) -> bool:
        if self.is_expired:
            return False
        return (self.expiry_date - date.today()).days <= 60

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'batch_number': self.batch_number,
            'quantity': self.quantity,
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else None,
            'unit_price': self.unit_price,
            'reorder_level': self.reorder_level,
            'is_low_stock': self.is_low_stock,
            'is_expired': self.is_expired,
            'is_expiring_soon': self.is_expiring_soon
        }

    def __repr__(self) -> str:
        return f"<Medicine id={self.id} name='{self.name}' batch='{self.batch_number}' qty={self.quantity}>"


class ConsultationRequest(db.Model):
    """
    Patient Remote Symptom Report & Tele-Consultation Request.
    Supports triage between 'Online Advice Only (No Camp Visit Needed)' and
    'Want to Visit Physical Health Camp', and records doctor clinical tele-advice,
    prescriptions, and diet guidance.
    """
    __tablename__ = 'consultation_requests'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    camp_id = db.Column(db.Integer, db.ForeignKey('camps.id'), nullable=True)

    # Patient submission details
    symptoms = db.Column(db.Text, nullable=False)
    duration = db.Column(db.String(100), nullable=True)
    allergies = db.Column(db.Text, nullable=True, default='None')
    consultation_preference = db.Column(
        db.String(80),
        default='Online Advice Only (No Camp Visit Needed)',
        nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Review status
    status = db.Column(db.String(50), default='Pending Review', nullable=False)  # 'Pending Review' or 'Reviewed / Advice Sent'
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Doctor Response / Tele-advice fields
    visit_decision = db.Column(db.String(150), nullable=True)
    clinical_advice = db.Column(db.Text, nullable=True)
    morning_tablets = db.Column(db.Text, nullable=True)
    afternoon_tablets = db.Column(db.Text, nullable=True)
    night_tablets = db.Column(db.Text, nullable=True)
    diet_recommendations = db.Column(db.Text, nullable=True)

    # Linked HealthRecord id
    health_record_id = db.Column(db.Integer, db.ForeignKey('health_records.id'), nullable=True)

    # Relationships
    doctor = db.relationship('Doctor', backref=db.backref('consultation_requests', lazy=True))
    camp = db.relationship('Camp', backref=db.backref('consultation_requests', lazy=True))
    health_record = db.relationship('HealthRecord', backref=db.backref('consultation_request', uselist=False))

    @property
    def is_reviewed(self) -> bool:
        return self.status == 'Reviewed / Advice Sent'

    @property
    def formatted_created_at(self) -> str:
        return self.created_at.strftime('%d %b %Y, %I:%M %p')

    @property
    def formatted_reviewed_at(self) -> str:
        return self.reviewed_at.strftime('%d %b %Y, %I:%M %p') if self.reviewed_at else 'Pending'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'camp_id': self.camp_id,
            'symptoms': self.symptoms,
            'duration': self.duration,
            'allergies': self.allergies,
            'consultation_preference': self.consultation_preference,
            'status': self.status,
            'visit_decision': self.visit_decision,
            'clinical_advice': self.clinical_advice,
            'morning_tablets': self.morning_tablets,
            'afternoon_tablets': self.afternoon_tablets,
            'night_tablets': self.night_tablets,
            'diet_recommendations': self.diet_recommendations,
            'created_at': self.formatted_created_at,
            'reviewed_at': self.formatted_reviewed_at
        }


# Model alias as requested by user specification
SymptomReport = ConsultationRequest

