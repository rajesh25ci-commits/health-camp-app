with open('templates/base.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = """                    <li class="nav-item">
                        <a class="nav-link px-3 py-2 rounded-2 {% if request.endpoint == 'inventory' %}active bg-white bg-opacity-10 fw-semibold text-white{% endif %}" href="{{ url_for('inventory') }}">
                            <i class="fas fa-pills me-2"></i>Pharmacy Inventory
                        </a>
                    </li>"""

replacement = """                    <li class="nav-item">
                        <a class="nav-link px-3 py-2 rounded-2 {% if request.endpoint == 'inventory' %}active bg-white bg-opacity-10 fw-semibold text-white{% endif %}" href="{{ url_for('inventory') }}">
                            <i class="fas fa-pills me-2"></i>Pharmacy Inventory
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link px-3 py-2 rounded-2 {% if request.endpoint == 'features_bp.ambulance_logs' %}active bg-white bg-opacity-10 fw-semibold text-white{% endif %}" href="{{ url_for('features_bp.ambulance_logs') }}">
                            <i class="fas fa-truck-medical me-2 text-warning"></i>108 Dispatches
                        </a>
                    </li>"""

if target not in text:
    target = target.replace('\n', '\r\n')
    replacement = replacement.replace('\n', '\r\n')

if target in text:
    text = text.replace(target, replacement, 1)
    with open('templates/base.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Navbar updated with 108 Dispatches link successfully!")
else:
    print("Target not found.")
