with open('app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Cut off old main block
if 'if __name__ ==' in code:
    code = code.split('if __name__ ==')[0].strip()

# New auto-network runner block
new_block = """


if __name__ == '__main__':
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    print("\\n" + "="*50)
    print(f"➜ THIS LAPTOP:  http://127.0.0.1:5000")
    print(f"➜ OTHER LAPTOP: http://{local_ip}:5000")
    print("="*50 + "\\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
"""

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code + new_block)

print("\nSUCCESS: app.py has been updated automatically!")