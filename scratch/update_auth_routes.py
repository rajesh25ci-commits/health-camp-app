import os

app_path = os.path.join(os.path.dirname(__file__), '..', 'app.py')

with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    @app.route('/login', methods=['GET', 'POST'])
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
        return redirect(url_for('login'))'''

replacement = '''    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """
        Cinematic User Login and Self-Service Portal Handler.
        Supports:
        - Staff Sign In (username/email + custom password)
        - Self-Service Account Creation / Custom Password Setup (via action='setup')
        - Self-Service Password Reset (via action='reset')
        """
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        active_tab = request.args.get('tab', 'login')

        if request.method == 'POST':
            action = request.form.get('action', 'login')
            if action == 'setup':
                return setup_account()
            elif action == 'reset':
                return reset_password()

            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            remember = True if request.form.get('remember') else False

            if not username or not password:
                flash('Please enter both your Username and Password.', 'danger')
                return render_template('login.html', active_tab='login')

            user = User.query.filter(func.lower(User.username) == username.lower()).first()

            if user and user.check_password(password):
                login_user(user, remember=remember)
                display_name = user.full_name or user.username
                flash(f'Welcome back, {display_name}! Signed in as {user.role}.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid username or password. Please verify credentials or set up a new account.', 'danger')
                return render_template('login.html', active_tab='login')

        return render_template('login.html', active_tab=active_tab)

    @app.route('/auth/setup-account', methods=['POST'])
    def setup_account():
        """
        Self-Service Account Creation and Custom Password Setup.
        Validates Camp Access PIN (CAMP_ACCESS_PIN), sets up user with custom password,
        hashes with Werkzeug PBKDF2/scrypt, and logs the user in immediately.
        """
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        role = request.form.get('role', 'Volunteer').strip()
        camp_pin = request.form.get('camp_pin', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        expected_pin = os.environ.get('CAMP_ACCESS_PIN', 'HEALTH2026').strip()

        if not username or not password:
            flash('Username and Password are required to set up your account.', 'danger')
            return redirect(url_for('login', tab='setup'))

        # Security PIN Verification
        if camp_pin != expected_pin:
            flash('Invalid Camp Access PIN! Please enter the authorized PIN (default: HEALTH2026) provided by your camp coordinator.', 'danger')
            return redirect(url_for('login', tab='setup'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('login', tab='setup'))

        if password != confirm_password:
            flash('Passwords do not match. Please verify and re-type your password.', 'danger')
            return redirect(url_for('login', tab='setup'))

        # Check existing username
        existing_user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if existing_user:
            flash(f'Username "{username}" is already in use. Please sign in or use the Reset Password tab.', 'warning')
            return redirect(url_for('login', tab='login'))

        valid_roles = ['Doctor', 'Volunteer', 'Coordinator', 'Admin']
        if role not in valid_roles:
            role = 'Volunteer'

        new_user = User(
            username=username,
            full_name=full_name or username.title(),
            role=role
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        # If role is Doctor, link to Doctor directory if not already present
        if role == 'Doctor' and new_user.full_name:
            doc = Doctor.query.filter(func.lower(Doctor.name) == new_user.full_name.lower()).first()
            if not doc:
                doc = Doctor(
                    name=new_user.full_name,
                    specialization='General Medicine',
                    phone='',
                    email='',
                    availability='Available'
                )
                db.session.add(doc)
                db.session.commit()

        # Automatically log the user in immediately after setting their password
        login_user(new_user, remember=True)
        display_name = new_user.full_name or new_user.username
        flash(f'Welcome to Smart Health Camp, {display_name}! Your {new_user.role} account and secure password are now active.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/auth/reset-password', methods=['POST'])
    def reset_password():
        """
        Self-Service Custom Password Reset.
        Requires Username and Camp Access PIN to securely set a new password.
        Hashes password with Werkzeug and logs the user in immediately.
        """
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))

        username = request.form.get('username', '').strip().lower()
        camp_pin = request.form.get('camp_pin', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        expected_pin = os.environ.get('CAMP_ACCESS_PIN', 'HEALTH2026').strip()

        if not username or not new_password:
            flash('Username and New Password are required.', 'danger')
            return redirect(url_for('login', tab='reset'))

        if camp_pin != expected_pin:
            flash('Invalid Camp Access PIN! Authorization required to set a new password.', 'danger')
            return redirect(url_for('login', tab='reset'))

        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'danger')
            return redirect(url_for('login', tab='reset'))

        if new_password != confirm_password:
            flash('New passwords do not match. Please verify and re-type.', 'danger')
            return redirect(url_for('login', tab='reset'))

        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if not user:
            flash(f'User "{username}" was not found in the health camp registry.', 'danger')
            return redirect(url_for('login', tab='reset'))

        user.set_password(new_password)
        db.session.commit()

        login_user(user, remember=True)
        display_name = user.full_name or user.username
        flash(f'Password updated successfully for {display_name}! You are now signed in as {user.role}.', 'success')
        return redirect(url_for('dashboard'))

    @app.route('/logout')
    @login_required
    def logout():
        """Sign out the currently authenticated user."""
        logout_user()
        flash('You have been successfully logged out.', 'info')
        return redirect(url_for('login'))'''

norm_content = content.replace('\r\n', '\n')
norm_target = target.replace('\r\n', '\n')
norm_replacement = replacement.replace('\r\n', '\n')

if norm_target in norm_content:
    new_content = norm_content.replace(norm_target, norm_replacement, 1)
    if '\r\n' in content:
        new_content = new_content.replace('\n', '\r\n')
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS: Updated login, setup_account, and reset_password routes in app.py")
else:
    print("ERROR: Could not find target in app.py")
