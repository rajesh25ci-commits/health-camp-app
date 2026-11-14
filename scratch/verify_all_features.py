import os
import sys
import json

# Set test environment
os.environ['TESTING'] = 'True'
os.environ['SECRET_KEY'] = 'test-secret-key'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, Patient, HealthRecord, Doctor, Camp, Appointment
from upgraded_features_v3 import (
    universal_health_chatbot,
    get_symptom_based_prescription,
    compute_camp_gamification,
    calculate_patient_wellness_score,
    get_patient_journey_steps,
    detect_language
)

def run_tests():
    passed = 0
    total = 0

    def assert_test(cond, title):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            sys.stdout.buffer.write(f"[PASS] {title}\n".encode('utf-8'))
        else:
            sys.stdout.buffer.write(f"[FAIL] {title}\n".encode('utf-8'))

    sys.stdout.buffer.write(b"\n============================================================\n")
    sys.stdout.buffer.write(b"RUNNING COMPREHENSIVE V3 SYSTEM VERIFICATION SUITE\n")
    sys.stdout.buffer.write(b"============================================================\n\n")

    # -------------------------------------------------------------
    # 1. SECURITY & NO EXPOSED CREDENTIALS TEST
    # -------------------------------------------------------------
    login_html_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'login.html')
    with open(login_html_path, 'r', encoding='utf-8') as f:
        login_content = f.read()

    assert_test('admin123' not in login_content, "Requirement 3: templates/login.html has NO 'admin123' demo credentials")
    assert_test('demo credentials' not in login_content.lower(), "Requirement 3: templates/login.html has NO demo credential hints")

    # -------------------------------------------------------------
    # 2. CHATBOT MULTILINGUAL & STRICT PRIORITY TESTS
    # -------------------------------------------------------------
    # Test A: "i have a fever so recommend me some tablet"
    # MUST return Paracetamol and NOT BP/Thyroid schedule!
    res_fever = universal_health_chatbot("i have a fever so recommend me some tablet")
    fever_reply = res_fever.get('reply', '')
    assert_test('Paracetamol' in fever_reply or 'paracetamol' in fever_reply,
                "Requirement 2: Fever query returns Paracetamol 650mg")
    assert_test('Thyroid' not in fever_reply and 'Amlodipine' not in fever_reply,
                "Requirement 2: Fever query does NOT return generic BP/Thyroid schedule")
    assert_test(res_fever.get('status') == 'success', "Requirement 2: Chatbot response status is success")

    # Test B: Emergency Chest Pain -> Priority 1 Triage
    res_emer = universal_health_chatbot("Patient has severe chest pain and breathlessness")
    emer_reply = res_emer.get('reply', '')
    assert_test('108' in emer_reply and 'EMERGENCY' in emer_reply,
                "Requirement 2: Emergency chest pain triggers Priority 1 (108 Ambulance alert)")

    # Test C: Kannada Fever
    res_kn = universal_health_chatbot("ನನಗೆ ವಿಪರೀತ ಜ್ವರ ಇದೆ ಮಾತ್ರೆ ಕೊಡಿ")
    kn_reply = res_kn.get('reply', '')
    assert_test('ಪ್ಯಾರಸಿಟಮಾಲ್' in kn_reply or 'Paracetamol' in kn_reply or 'ಜ್ವರ' in kn_reply,
                "Requirement 2: Kannada fever query returns Kannada clinical response")

    # Test D: Hindi Acidity
    res_hi = universal_health_chatbot("pet me bahut gas aur acidity hai dawa bataiye")
    hi_reply = res_hi.get('reply', '')
    assert_test('Pantoprazole' in hi_reply or 'गैस' in hi_reply or 'एसिडिटी' in hi_reply or 'khali pet' in hi_reply.lower(),
                "Requirement 2: Hindi acidity query returns targeted Pantoprazole guidance")

    # Test E: Generic Tablet timing ONLY when no symptom
    res_gen = universal_health_chatbot("how to take medicine 1-0-1 timing")
    gen_reply = res_gen.get('reply', '')
    assert_test('1-0-1' in gen_reply or 'Morning' in gen_reply,
                "Requirement 2: Generic timing query returns 1-0-1 schedule explanation")

    # -------------------------------------------------------------
    # 3. SYMPTOM-FIRST TABLET SCHEDULE COMPONENT LOGIC
    # -------------------------------------------------------------
    sched_none = get_symptom_based_prescription(None)
    assert_test(sched_none.get('has_prescription') is False,
                "Requirement 4: Symptom schedule is LOCKED (False) when patient has no symptoms")

    sched_fever = get_symptom_based_prescription("High fever since 2 days with headache")
    assert_test(sched_fever.get('has_prescription') is True,
                "Requirement 4: Symptom schedule UNLOCKS (True) when patient has fever symptoms")
    assert_test(len(sched_fever.get('morning', [])) > 0 and len(sched_fever.get('night', [])) > 0,
                "Requirement 4: Symptom schedule provides structured Morning and Night slots")

    # -------------------------------------------------------------
    # 4. GAMIFICATION & WELLNESS SCORE TESTS
    # -------------------------------------------------------------
    with app.app_context():
        camp_stats = compute_camp_gamification()
        assert_test('level_tier' in camp_stats and 'total_xp' in camp_stats and 'progress_percent' in camp_stats,
                    "Requirement 4: compute_camp_gamification computes tier, total_xp, and progress_percent")
        assert_test(camp_stats['total_xp'] >= 0 and 0 <= camp_stats['progress_percent'] <= 100,
                    "Requirement 4: Gamification XP and progress percentage are within valid bounds")

    # Test wellness score
    class DummyPatient:
        patient_uid = 'PAT-2026-9999'
        age = 45
        urgency_level = 'NORMAL'
        symptoms = 'Mild tiredness'

    class DummyRecord:
        systolic_bp = 120
        diastolic_bp = 80
        blood_sugar = 110
        spo2 = 98
        pulse_rate = 72
        prescription = 'Paracetamol'
        is_critical = False

    wellness = calculate_patient_wellness_score(DummyPatient(), DummyRecord())
    assert_test(wellness['score'] >= 80 and wellness['label'] == 'Stable & Good Wellness',
                f"Requirement 4: Normal vitals yield Stable & Good Wellness score (got {wellness['score']}, {wellness['label']})")

    steps = get_patient_journey_steps(DummyPatient(), DummyRecord())
    assert_test(len(steps) == 4 and steps[0]['completed'] is True,
                "Requirement 4: 4-Step Patient Journey Tracker correctly structured")

    # -------------------------------------------------------------
    # 5. FLASK APP ROUTES & DATABASE INTEGRATION TESTS
    # -------------------------------------------------------------
    with app.test_client() as client:
        with app.app_context():
            # Create a test patient with EMERGENCY urgency level
            test_uid = 'PAT-TEST-9999'
            existing = Patient.query.filter_by(patient_uid=test_uid).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

            test_patient = Patient(
                name='Emergency Test Patient',
                age=58,
                gender='Male',
                phone='9876543210',
                address='Ward 4, Test Village',
                patient_uid=test_uid,
                symptoms='Severe acute chest pain radiating to left arm',
                urgency_level='EMERGENCY'
            )
            db.session.add(test_patient)
            db.session.commit()

            # Verify in DB
            saved_p = Patient.query.filter_by(patient_uid=test_uid).first()
            assert_test(saved_p is not None and saved_p.symptoms == 'Severe acute chest pain radiating to left arm',
                        "Requirement 1: Patient model persists symptoms")
            assert_test(saved_p is not None and saved_p.urgency_level == 'EMERGENCY',
                        "Requirement 1: Patient model persists urgency_level='EMERGENCY'")

            # Test Doctor Queue Prioritization:
            # Query recent_patients equivalent: urgency_case sort
            from sqlalchemy import case
            urgency_case = case(
                (Patient.urgency_level == 'EMERGENCY', 1),
                (Patient.urgency_level == 'URGENT', 2),
                else_=3
            )
            top_patient = Patient.query.order_by(urgency_case.asc(), Patient.created_at.desc()).first()
            assert_test(top_patient.urgency_level == 'EMERGENCY',
                        "Requirement 1: Doctor Queue prioritizes EMERGENCY patients to the very top (#1)")

            # Test public/verification routes
            resp_card = client.get(f'/patient_card/{test_uid}')
            assert_test(resp_card.status_code == 200,
                        f"Requirement 1: Digital ID & Verification route /patient_card/{test_uid} returns 200 OK")
            card_html = resp_card.get_data(as_text=True)
            assert_test('Severe acute chest pain' in card_html,
                        "Requirement 1: /patient_card displays patient symptoms")
            assert_test('EMERGENCY' in card_html,
                        "Requirement 1: /patient_card displays EMERGENCY triage badge")
            assert_test('Clinical Care Journey Tracker' in card_html,
                        "Requirement 4: /patient_card renders 4-Step Journey Tracker")

            # Clean up test patient
            db.session.delete(saved_p)
            db.session.commit()

            # Test Chatbot API via HTTP POST
            api_res = client.post('/api/chatbot', json={'message': 'i have a fever so recommend me some tablet'})
            assert_test(api_res.status_code == 200, "Requirement 2: POST /api/chatbot returns 200 OK")
            api_data = api_res.get_json()
            assert_test('Paracetamol' in api_data.get('reply', ''),
                        "Requirement 2: POST /api/chatbot returns Paracetamol for fever")

    sys.stdout.buffer.write(b"\n============================================================\n")
    sys.stdout.buffer.write(f"TEST RESULTS: {passed} / {total} TESTS PASSED ({(passed/total)*100:.1f}%)\n".encode('utf-8'))
    sys.stdout.buffer.write(b"============================================================\n\n")

    return passed == total

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
