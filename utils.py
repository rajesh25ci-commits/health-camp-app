"""
Utility functions for Smart Community Health Camp Management System.
Includes:
- File upload validation
- Dynamic QR code generation for patient identification
- Official PDF medical history and prescription document generation using ReportLab
"""

import os
import io
from datetime import datetime
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from config import Config


def allowed_file(filename: str) -> bool:
    """
    Validate whether the uploaded file has a permissible extension.

    :param filename: Original name of the uploaded file.
    :return: True if extension is permitted, False otherwise.
    """
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS


def ensure_default_qr(folder: str = None) -> str:
    """
    Ensure a default QR code image exists for fallback rendering.
    Returns relative path 'qrcodes/default_qr.png'.
    """
    target_folder = folder or Config.QRCODE_FOLDER
    os.makedirs(target_folder, exist_ok=True)
    filepath = os.path.join(target_folder, "default_qr.png")
    if not os.path.exists(filepath):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2
        )
        qr.add_data("http://127.0.0.1:5000/")
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a365d", back_color="#ffffff")
        img.save(filepath)
    return "qrcodes/default_qr.png"


def ensure_default_avatar(folder: str = None) -> str:
    """
    Ensure a clean default healthcare avatar image exists in static/uploads/.
    Returns relative path 'uploads/default_avatar.png'.
    """
    target_folder = folder or Config.UPLOAD_FOLDER
    os.makedirs(target_folder, exist_ok=True)
    filepath = os.path.join(target_folder, "default_avatar.png")
    if not os.path.exists(filepath):
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (256, 256), color=(241, 245, 249, 255))
        draw = ImageDraw.Draw(img)
        # Outer border circle
        draw.ellipse([16, 16, 240, 240], fill=(224, 231, 255, 255), outline=(59, 130, 246, 255), width=4)
        # Head silhouette
        draw.ellipse([98, 48, 158, 108], fill=(30, 58, 138, 255))
        # Torso silhouette
        draw.chord([52, 120, 204, 238], start=0, end=180, fill=(30, 58, 138, 255))
        # Healthcare plus cross on chest
        cross_color = (255, 255, 255, 255)
        draw.rectangle([122, 145, 134, 175], fill=cross_color)
        draw.rectangle([112, 154, 144, 166], fill=cross_color)
        img.save(filepath, 'PNG')
    return "uploads/default_avatar.png"


def generate_qr_code(patient_uid: str, folder: str = None, profile_url: str = None) -> str:
    """
    Generate a dynamic QR code image encoding a valid patient profile URL.
    Saves the generated PNG image to static/qrcodes/patient_<patient_id>.png.
    Also ensures default_qr.png and backwards-compatible <patient_uid>.png exist.

    :param patient_uid: Unique identifier for the patient (e.g., 'PAT-2026-0001').
    :param folder: Directory path to save the QR code image. Defaults to Config.QRCODE_FOLDER.
    :param profile_url: Explicit URL to encode in the QR code. If None, auto-generates application URL.
    :return: Relative static path to the generated QR code (e.g., 'qrcodes/patient_PAT-2026-0001.png').
    """
    target_folder = folder or Config.QRCODE_FOLDER
    os.makedirs(target_folder, exist_ok=True)
    ensure_default_qr(target_folder)

    clean_id = str(patient_uid).strip()
    if clean_id.startswith('patient_'):
        clean_id = clean_id[len('patient_'):]

    filename = f"patient_{clean_id}.png"
    filepath = os.path.join(target_folder, filename)

    # Determine full patient profile URL to embed
    if profile_url:
        data_to_encode = profile_url
    else:
        try:
            from flask import has_request_context, request
            if has_request_context() and request.host_url and 'localhost' not in request.host_url:
                base = request.host_url.rstrip('/')
                data_to_encode = f"{base}/patient_card/{clean_id}"
            else:
                base_url = os.environ.get('BASE_APP_URL', 'http://127.0.0.1:5000')
                data_to_encode = f"{base_url.rstrip('/')}/patient_card/{clean_id}"
        except Exception:
            base_url = os.environ.get('BASE_APP_URL', 'http://127.0.0.1:5000')
            data_to_encode = f"{base_url.rstrip('/')}/patient_card/{clean_id}"

    # Configure high-quality QR code with auto-version fitting
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(data_to_encode)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a365d", back_color="#ffffff")
    img.save(filepath)

    # Backwards compatibility: also write <clean_id>.png so older links don't break
    legacy_file = os.path.join(target_folder, f"{clean_id}.png")
    if legacy_file != filepath:
        try:
            img.save(legacy_file)
        except Exception:
            pass

    # Return relative path for static URL mapping
    return f"qrcodes/{filename}"


def regenerate_patient_qr_codes(app, base_url: str = "http://127.0.0.1:5000") -> int:
    """
    Regenerate QR codes for all existing patients to ensure they contain
    the valid profile URL and are stored as qrcodes/patient_<patient_id>.png.
    """
    from models import db, Patient
    count = 0
    with app.app_context():
        ensure_default_qr(app.config['QRCODE_FOLDER'])
        patients = Patient.query.all()
        for p in patients:
            uid_val = getattr(p, 'patient_uid', getattr(p, 'patient_id', str(p.id)))
            url = f"{base_url.rstrip('/')}/patient_card/{uid_val}"
            rel_path = generate_qr_code(uid_val, app.config['QRCODE_FOLDER'], profile_url=url)
            p.qr_code_path = rel_path
            count += 1
        db.session.commit()
    return count


def generate_patient_pdf(patient, health_records=None, output_path: str = None):
    """
    Generate an official, enterprise-grade Medical Record & Prescription PDF for a patient.

    :param patient: Patient model instance containing demographics and UID.
    :param health_records: List of HealthRecord model instances associated with the patient.
    :param output_path: Optional file path to save the PDF. If None, returns a BytesIO buffer.
    :return: File path string if output_path is provided, otherwise io.BytesIO stream.
    """
    buffer = io.BytesIO() if output_path is None else output_path

    # Page setup (A4 with 0.5 inch margins)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    header_style = ParagraphStyle(
        'DocHeader',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=0  # Left aligned
    )
    sub_header_style = ParagraphStyle(
        'DocSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E40AF'),
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1F2937')
    )
    body_bold = ParagraphStyle(
        'TableBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#111827')
    )
    notes_style = ParagraphStyle(
        'NotesStyle',
        parent=body_style,
        fontName='Helvetica-Oblique',
        textColor=colors.HexColor('#374151')
    )

    story = []

    # --- Header Banner ---
    title_p = Paragraph("SMART COMMUNITY HEALTH CAMP", header_style)
    subtitle_p = Paragraph(
        "Official Patient Clinical Summary & Medical History Report<br/>"
        "<i>Ministry of Health & Community Care Initiative</i>",
        sub_header_style
    )
    report_meta = Paragraph(
        f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}<br/>"
        f"<b>Status:</b> Official Record",
        sub_header_style
    )

    header_table = Table(
        [[[title_p, Spacer(1, 4), subtitle_p], report_meta]],
        colWidths=[380, 140]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Divider Line
    story.append(Table(
        [['']],
        colWidths=[522],
        style=[('LINEABOVE', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A'))]
    ))
    story.append(Spacer(1, 10))

    # --- Patient Demographic Card ---
    story.append(Paragraph("Patient Identification Profile", section_title))

    # Determine QR code image flowable if available
    qr_flowable = Paragraph("<b>[No QR Code]</b>", body_style)
    qr_rel = getattr(patient, 'qr_code_path', None)
    static_root = getattr(Config, 'STATIC_FOLDER', os.path.join(getattr(Config, 'BASE_DIR', os.getcwd()), 'static'))
    if qr_rel:
        qr_full_path = os.path.join(static_root, qr_rel)
        if not os.path.exists(qr_full_path):
            clean_uid = getattr(patient, 'patient_uid', getattr(patient, 'patient_id', ''))
            alt1 = os.path.join(static_root, f"qrcodes/patient_{clean_uid}.png")
            alt2 = os.path.join(static_root, f"qrcodes/{clean_uid}.png")
            alt3 = os.path.join(static_root, "qrcodes/default_qr.png")
            if os.path.exists(alt1):
                qr_full_path = alt1
            elif os.path.exists(alt2):
                qr_full_path = alt2
            elif os.path.exists(alt3):
                qr_full_path = alt3
        if os.path.exists(qr_full_path):
            try:
                qr_flowable = RLImage(qr_full_path, width=1.1 * inch, height=1.1 * inch)
            except Exception:
                qr_flowable = Paragraph("<b>[QR Error]</b>", body_style)

    p_uid = str(getattr(patient, 'patient_uid', getattr(patient, 'patient_id', 'N/A')))
    p_created = getattr(patient, 'created_at', None)
    reg_date_str = p_created.strftime('%Y-%m-%d') if p_created and hasattr(p_created, 'strftime') else 'N/A'
    p_name = str(getattr(patient, 'name', 'N/A'))
    p_gender = str(getattr(patient, 'gender', 'N/A'))
    p_age = str(getattr(patient, 'age', 'N/A'))
    p_phone = str(getattr(patient, 'phone', 'N/A') or 'N/A')
    p_address = str(getattr(patient, 'address', 'N/A') or 'N/A')

    demo_data = [
        [
            Paragraph("<b>Patient UID:</b>", body_bold),
            Paragraph(p_uid, body_style),
            Paragraph("<b>Registered Date:</b>", body_bold),
            Paragraph(reg_date_str, body_style),
            qr_flowable
        ],
        [
            Paragraph("<b>Full Name:</b>", body_bold),
            Paragraph(p_name, body_style),
            Paragraph("<b>Gender / Age:</b>", body_bold),
            Paragraph(f"{p_gender} / {p_age} yrs", body_style),
            ""
        ],
        [
            Paragraph("<b>Phone:</b>", body_bold),
            Paragraph(p_phone, body_style),
            Paragraph("<b>Address:</b>", body_bold),
            Paragraph(p_address, body_style),
            ""
        ]
    ]

    demo_table = Table(
        demo_data,
        colWidths=[90, 130, 85, 135, 82]
    )
    demo_table.setStyle(TableStyle([
        ('SPAN', (4, 0), (4, 2)),  # Span QR code across all 3 rows
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#D1D5DB')),
        ('INNERGRID', (0, 0), (3, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (4, 0), (4, 2), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 16))

    # --- Clinical Encounters & Prescriptions ---
    story.append(Paragraph("Clinical Encounters & Treatment History", section_title))

    records_list = health_records if health_records is not None else (getattr(patient, 'health_records', []) or [])

    if not records_list:
        no_rec_table = Table(
            [[Paragraph("<i>No clinical health records or prescriptions recorded to date.</i>", notes_style)]],
            colWidths=[522]
        )
        no_rec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#F59E0B')),
            ('PADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(no_rec_table)
    else:
        # Table Header
        record_rows = [
            [
                Paragraph("<b>Date / Camp</b>", body_bold),
                Paragraph("<b>Attending Doctor</b>", body_bold),
                Paragraph("<b>Diagnosis</b>", body_bold),
                Paragraph("<b>Prescription & Dosage</b>", body_bold),
                Paragraph("<b>Clinical Notes</b>", body_bold),
            ]
        ]

        for rec in records_list:
            camp_obj = getattr(rec, 'camp', None)
            camp_info = getattr(camp_obj, 'title', 'General Camp') if camp_obj else "General Camp"
            created_at_val = getattr(rec, 'created_at', None)
            date_info = created_at_val.strftime('%Y-%m-%d') if created_at_val and hasattr(created_at_val, 'strftime') else "N/A"
            doc_obj = getattr(rec, 'doctor', None)
            doc_name = getattr(doc_obj, 'name', 'Medical Officer') if doc_obj else "Medical Officer"
            doc_spec = getattr(doc_obj, 'specialization', 'General Medicine') if doc_obj else "General Medicine"
            doctor_info = f"{doc_name}<br/><font size=7 color='#6B7280'>({doc_spec})</font>"
            presc_val = getattr(rec, 'prescription', None) or "None specified"
            prescription_text = presc_val.replace('\n', '<br/>')
            notes_val = getattr(rec, 'doctor_notes', None) or "—"
            notes_text = notes_val.replace('\n', '<br/>')
            diag_val = getattr(rec, 'diagnosis', None) or "N/A"

            record_rows.append([
                Paragraph(f"<b>{date_info}</b><br/>{camp_info}", body_style),
                Paragraph(doctor_info, body_style),
                Paragraph(diag_val, body_style),
                Paragraph(prescription_text, body_style),
                Paragraph(notes_text, notes_style),
            ])

        records_table = Table(
            record_rows,
            colWidths=[90, 100, 110, 122, 100]
        )
        records_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(records_table)

    story.append(Spacer(1, 24))

    # --- Authorization & Signature Section ---
    sig_data = [
        [
            Paragraph("<b>Camp Medical Officer</b><br/><br/><br/>___________________________<br/>Signature & Seal", body_style),
            Paragraph("<b>Attending Doctor</b><br/><br/><br/>___________________________<br/>Doctor Registration / Stamp", body_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[261, 261])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(KeepTogether([sig_table]))
    story.append(Spacer(1, 15))

    # Footer note
    footer_text = Paragraph(
        "<font size=7 color='#6B7280'>* This medical record summary is generated by the Smart Community Health Camp "
        "Management System. Valid for clinical reference and community follow-ups.</font>",
        body_style
    )
    story.append(footer_text)

    # Build document
    doc.build(story)

    if output_path is None:
        buffer.seek(0)
        return buffer
    return output_path


def generate_camp_pdf(camp, appointments=None, output_path: str = None):
    """
    Generate an official Camp Operational & Beneficiary Summary Report PDF using ReportLab.
    Defensively retrieves attributes using getattr() to prevent AttributeError.
    """
    buffer = io.BytesIO() if output_path is None else output_path
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'CampHeader',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E3A8A')
    )
    sub_header_style = ParagraphStyle(
        'CampSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )
    section_title = ParagraphStyle(
        'CampSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E40AF'),
        spaceAfter=6
    )
    body_style = ParagraphStyle('CampBody', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12)
    body_bold = ParagraphStyle('CampBold', parent=body_style, fontName='Helvetica-Bold')

    story = []

    # Header Banner
    camp_title = str(getattr(camp, 'title', 'Health Camp'))
    title_p = Paragraph(f"CAMP REPORT: {camp_title}", header_style)
    subtitle_p = Paragraph("Community Health Outreach & Beneficiary Summary<br/><i>Smart Community Health Camp System</i>", sub_header_style)
    date_val = getattr(camp, 'date', None)
    camp_date_str = date_val.strftime('%d %B %Y') if date_val and hasattr(date_val, 'strftime') else 'N/A'
    meta_p = Paragraph(f"<b>Camp Date:</b> {camp_date_str}<br/><b>Status:</b> {getattr(camp, 'status', 'Upcoming')}", sub_header_style)

    header_table = Table([[[title_p, Spacer(1, 4), subtitle_p], meta_p]], colWidths=[380, 140])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Camp Summary Card
    story.append(Paragraph("Camp Logistics & Location Profile", section_title))
    lat = getattr(camp, 'latitude', None)
    lng = getattr(camp, 'longitude', None)
    coords = f"{lat:.4f}, {lng:.4f}" if lat is not None and lng is not None else "Not recorded"
    camp_data = [
        [
            Paragraph("<b>Location:</b>", body_bold), Paragraph(str(getattr(camp, 'location_name', 'N/A')), body_style),
            Paragraph("<b>Target Capacity:</b>", body_bold), Paragraph(f"{getattr(camp, 'target_beneficiaries', 100)} Beneficiaries", body_style)
        ],
        [
            Paragraph("<b>Coordinates:</b>", body_bold), Paragraph(coords, body_style),
            Paragraph("<b>Scheduled Date:</b>", body_bold), Paragraph(camp_date_str, body_style)
        ]
    ]
    camp_table = Table(camp_data, colWidths=[90, 180, 100, 152])
    camp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#D1D5DB')),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    story.append(camp_table)
    story.append(Spacer(1, 14))

    # Consultations / Appointments
    story.append(Paragraph("Camp Consultations & Beneficiary Attendance", section_title))
    appts_list = appointments if appointments is not None else (getattr(camp, 'appointments', []) or [])
    if not appts_list:
        no_appt = Table([[Paragraph("<i>No consultations recorded for this camp yet.</i>", body_style)]], colWidths=[522])
        no_appt.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7')), ('PADDING', (0, 0), (-1, -1), 8)]))
        story.append(no_appt)
    else:
        rows = [[Paragraph("<b>Token</b>", body_bold), Paragraph("<b>Patient Name</b>", body_bold), Paragraph("<b>Doctor Assigned</b>", body_bold), Paragraph("<b>Time</b>", body_bold), Paragraph("<b>Status</b>", body_bold)]]
        for a in appts_list:
            p_obj = getattr(a, 'patient', None)
            p_name = getattr(p_obj, 'name', 'N/A') if p_obj else 'N/A'
            p_uid = getattr(p_obj, 'patient_uid', getattr(p_obj, 'patient_id', '')) if p_obj else ''
            d_obj = getattr(a, 'doctor', None)
            d_name = getattr(d_obj, 'name', 'Medical Officer') if d_obj else 'Medical Officer'
            rows.append([
                Paragraph(f"#{getattr(a, 'id', '')}", body_style),
                Paragraph(f"<b>{p_name}</b><br/>{p_uid}", body_style),
                Paragraph(d_name, body_style),
                Paragraph(str(getattr(a, 'time', '10:00 AM')), body_style),
                Paragraph(str(getattr(a, 'status', 'Scheduled')), body_style)
            ])
        appt_table = Table(rows, colWidths=[50, 170, 160, 72, 70])
        appt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')])
        ]))
        story.append(appt_table)

    story.append(Spacer(1, 20))
    doc.build(story)
    if output_path is None:
        buffer.seek(0)
        return buffer
    return output_path
