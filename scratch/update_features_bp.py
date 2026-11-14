with open('upgraded_features.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = "@features_bp.route('/api/chatbot', methods=['POST'])"
end_marker = "@features_bp.route('/api/offline-sync', methods=['POST'])"

idx_start = text.find(start_marker)
idx_end = text.find(end_marker)
assert idx_start != -1 and idx_end != -1, f"Markers not found: start={idx_start}, end={idx_end}"

replacement = """@features_bp.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    \"\"\"
    Universal Multilingual AI Health Camp Chatbot API (v3 Upgraded).
    Answers clinical inquiries, emergency triage (108), symptoms (Fever, Cough, Sugar, BP),
    and tablet timings in English, Hindi, Kannada, and Hinglish.
    \"\"\"
    from upgraded_features_v3 import universal_health_chatbot
    data = request.get_json(silent=True) or {}
    query = (data.get('message') or request.form.get('message') or "").strip()

    res = universal_health_chatbot(query)
    return jsonify({
        'reply': res['reply'],
        'language': res['language'],
        'source': res['source'],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    })


"""

new_text = text[:idx_start] + replacement + text[idx_end:]
with open('upgraded_features.py', 'w', encoding='utf-8') as f:
    f.write(new_text)
print("upgraded_features.py api_chatbot successfully forwarded to universal_health_chatbot!")
