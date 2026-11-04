"""
SQLAlchemy Database Models for Smart Community Health Camp Management System.
Defines entity models for Users, Patients, Doctors, Camps, Appointments,
Health Records, and Inventory/Medicines, with explicit relationships and helper methods.
"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy instance
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    User entity representing system operators (Admins, Doctors, Volunteers).
    Includes Flask-Login UserMixin and secure password hashing via Werkzeug.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Volunteer')  # 'Admin', 'Doctor', 'Volunteer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        """Hash plain-text password using PBKDF2/scrypt and store hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify plain-text password against stored password hash."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Check if user has Admin privileges."""
        return self.role == 'Admin'

    def is_doctor(self) -> bool:
        """Check if user has Doctor privileges."""
        return self.role == 'Doctor'

    def is_volunteer(self) -> bool:
        """Check if user has Volunteer privileges."""
        return self.role == 'Volunteer'

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}'>"


class Patient(db.Model):
    """
    Patient entity registered at community health camps.
    Maintains demographics, contact info, photo, and dynamic QR Code identifier.
    """
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    patient_uid = db.Column(db.String(32), unique=True, nullable=False, index=True)  # e.g., 'PAT-2026-0001'
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)  # 'Male', 'Female', 'Other'
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)  # relative path, e.g., 'qrcodes/PAT-2026-0001.png'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')
    health_records = db.relationship('HealthRecord', backref='patient', lazy=True, cascade='all, delete-orphan')

    @property
    def patient_id(self) -> str:
        """Alias for patient_uid to guarantee backwards compatibility and prevent AttributeError."""
        return self.patient_uid

    def to_dict(self) -> dict:
        """Serialize patient details for API / view consumption."""
        return {
            'id': self.id,
            'patient_uid': self.patient_uid,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'phone': self.phone,
            'address': self.address,
            'photo_filename': self.photo_filename,
            'qr_code_path': self.qr_code_path,
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
    specialization = db.Column(db.String(100), nullable=False)  # e.g., General Medicine, Pediatrics, Cardiology
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    availability = db.Column(db.String(100), default='Available', nullable=False)  # e.g., 'Available', 'On Leave', 'Busy'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    health_records = db.relationship('HealthRecord', backref='doctor', lazy=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'specialization': self.specialization,
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
    status = db.Column(db.String(20), default='Upcoming', nullable=False)  # 'Upcoming', 'Ongoing', 'Completed'
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
            'status': self.status
        }

    def __repr__(self) -> str:
        return f"<Appointment id={self.id} patient_id={self.patient_id} doctor_id={self.doctor_id} status='{self.status}'>"


class HealthRecord(db.Model):
    """
    HealthRecord entity encapsulating medical observations, diagnosis,
    prescription, and doctor notes from a specific camp consultation.
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

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'camp_id': self.camp_id,
            'diagnosis': self.diagnosis,
            'prescription': self.prescription,
            'doctor_notes': self.doctor_notes,
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
        """Determines if the available stock has breached the reorder threshold."""
        return self.quantity <= self.reorder_level

    @property
    def is_expired(self) -> bool:
        """Determines if the medicine batch has expired based on current date."""
        return self.expiry_date < date.today()

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
            'is_expired': self.is_expired
        }

    def __repr__(self) -> str:
        return f"<Medicine id={self.id} name='{self.name}' batch='{self.batch_number}' qty={self.quantity}>"
