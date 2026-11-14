import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ['TESTING'] = 'True'
os.environ['SECRET_KEY'] = 'test-secret-cinematic-portal'

from app import app
from models import db, User, Doctor

def run_auth_tests():
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
    sys.stdout.buffer.write(b"RUNNING CINEMATIC GLASSMORPHISM AUTHENTICATION PORTAL TESTS\n")
    sys.stdout.buffer.write(b"============================================================\n\n")

    # 1. Inspect login.html file directly
    login_html_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'login.html')
    with open(login_html_path, 'r', encoding='utf-8') as f:
        html_src = f.read()

    assert_test('admin123' not in html_src, "login.html: Zero occurrences of hardcoded 'admin123'")
    assert_test('demo credential' not in html_src.lower(), "login.html: Zero demo credential hints")
    assert_test('ambient-orb' in html_src, "login.html: Animated ambient floating glowing orbs present")
    assert_test('ecg-pulse-line' in html_src and 'ecg-svg' in html_src, "login.html: Live animated SVG Heartbeat/ECG Pulse line present")
    assert_test('glass-card' in html_src, "login.html: Frosted-glass (backdrop-filter) authentication card present")
    assert_test('Digital QR Passes' in html_src and '108 Emergency Triage' in html_src, "login.html: Live camp impact badges present")
    assert_test('Multilingual AI Care' in html_src and 'Symptom-First' in html_src, "login.html: AI & dosage schedule impact badges present")
    assert_test('btn-eye-toggle' in html_src and 'togglePasswordVisibility' in html_src, "login.html: Interactive Show/Hide Password eye toggles present")
    assert_test('checkPasswordStrength' in html_src and 'strength-meter-bar' in html_src, "login.html: Real-time password strength meter present")
    assert_test('pills-login' in html_src and 'pills-setup' in html_src and 'pills-reset' in html_src, "login.html: 3 Interactive Pill Tabs (Sign In, New Account, Reset) present")

    with app.test_client() as client:
        with app.app_context():
            # Clean up test accounts if any
            test_username = 'dr.ananya.sharma'
            u = User.query.filter_by(username=test_username).first()
            if u:
                db.session.delete(u)
                db.session.commit()

            # 2. GET /login HTTP 200
            resp = client.get('/login')
            assert_test(resp.status_code == 200, "Route GET /login returns HTTP 200")
            resp_text = resp.get_data(as_text=True)
            assert_test('Medical Staff Portal' in resp_text, "GET /login renders Medical Staff Portal")

            # 3. POST /auth/setup-account - Invalid Camp Access PIN
            res_bad_pin = client.post('/auth/setup-account', data={
                'full_name': 'Dr. Ananya Sharma',
                'username': test_username,
                'role': 'Doctor',
                'camp_pin': 'WRONG_PIN_123',
                'password': 'CustomSecurePass123!',
                'confirm_password': 'CustomSecurePass123!'
            }, follow_redirects=False)
            assert_test(res_bad_pin.status_code == 302 and 'tab=setup' in res_bad_pin.headers.get('Location', ''),
                        "Account Setup: Invalid Camp PIN is blocked & redirected to setup tab")

            # 4. POST /auth/setup-account - Password mismatch
            res_mismatch = client.post('/auth/setup-account', data={
                'full_name': 'Dr. Ananya Sharma',
                'username': test_username,
                'role': 'Doctor',
                'camp_pin': 'HEALTH2026',
                'password': 'CustomSecurePass123!',
                'confirm_password': 'DifferentPassword456!'
            }, follow_redirects=False)
            assert_test(res_mismatch.status_code == 302 and 'tab=setup' in res_mismatch.headers.get('Location', ''),
                        "Account Setup: Password mismatch is rejected")

            # 5. POST /auth/setup-account - SUCCESS with valid CAMP_ACCESS_PIN
            res_success = client.post('/auth/setup-account', data={
                'full_name': 'Dr. Ananya Sharma',
                'username': test_username,
                'role': 'Doctor',
                'camp_pin': 'HEALTH2026',
                'password': 'CustomSecurePass123!',
                'confirm_password': 'CustomSecurePass123!'
            }, follow_redirects=False)
            assert_test(res_success.status_code == 302 and '/dashboard' in res_success.headers.get('Location', ''),
                        "Account Setup: Success redirects directly to /dashboard")

            # Verify in DB
            new_user = User.query.filter_by(username=test_username).first()
            assert_test(new_user is not None, "Account Setup: User record created in SQLite DB")
            assert_test(new_user.full_name == 'Dr. Ananya Sharma', "Account Setup: Full name stored correctly")
            assert_test(new_user.role == 'Doctor', "Account Setup: Role 'Doctor' assigned correctly")
            assert_test(new_user.check_password('CustomSecurePass123!'), "Account Setup: Werkzeug password hash verifies custom password")
            assert_test(not new_user.check_password('WrongPass!'), "Account Setup: Incorrect password fails verification")

            # Verify doctor directory record automatically linked
            doc_rec = Doctor.query.filter_by(name='Dr. Ananya Sharma').first()
            assert_test(doc_rec is not None, "Account Setup: Doctor profile automatically linked in Doctor directory")

            # 6. Test Logging in with the newly created custom password via /login
            # First logout
            client.get('/logout')
            login_res = client.post('/login', data={
                'username': test_username,
                'password': 'CustomSecurePass123!'
            }, follow_redirects=False)
            assert_test(login_res.status_code == 302 and '/dashboard' in login_res.headers.get('Location', ''),
                        "Sign In: Successfully signed in using new custom credentials")

            # 7. Test Reset Password (/auth/reset-password)
            client.get('/logout')
            # Invalid PIN on reset
            res_reset_bad = client.post('/auth/reset-password', data={
                'username': test_username,
                'camp_pin': 'WRONG_PIN',
                'new_password': 'BrandNewPassword2026!',
                'confirm_password': 'BrandNewPassword2026!'
            }, follow_redirects=False)
            assert_test(res_reset_bad.status_code == 302 and 'tab=reset' in res_reset_bad.headers.get('Location', ''),
                        "Password Reset: Invalid PIN is rejected")

            # Valid PIN on reset
            res_reset_ok = client.post('/auth/reset-password', data={
                'username': test_username,
                'camp_pin': 'HEALTH2026',
                'new_password': 'BrandNewPassword2026!',
                'confirm_password': 'BrandNewPassword2026!'
            }, follow_redirects=False)
            assert_test(res_reset_ok.status_code == 302 and '/dashboard' in res_reset_ok.headers.get('Location', ''),
                        "Password Reset: Success redirects immediately to /dashboard")

            # Verify in DB
            db.session.refresh(new_user)
            assert_test(new_user.check_password('BrandNewPassword2026!'),
                        "Password Reset: New custom password verified in DB")
            assert_test(not new_user.check_password('CustomSecurePass123!'),
                        "Password Reset: Old password is invalidated")

            # Clean up
            db.session.delete(new_user)
            if doc_rec:
                db.session.delete(doc_rec)
            db.session.commit()

    sys.stdout.buffer.write(b"\n============================================================\n")
    sys.stdout.buffer.write(f"TEST RESULTS: {passed} / {total} TESTS PASSED ({(passed/total)*100:.1f}%)\n".encode('utf-8'))
    sys.stdout.buffer.write(b"============================================================\n\n")

    return passed == total

if __name__ == '__main__':
    ok = run_auth_tests()
    sys.exit(0 if ok else 1)
