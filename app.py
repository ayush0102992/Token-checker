from flask import Flask, request, render_template_string
import requests
import time
import secrets
import json
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

TOKENS_FILE = 'checked_tokens.json'

def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tokens(tokens):
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens[-100:], f, indent=2)

checked_tokens = load_tokens()

def check_token_with_message(token):
    token = token.strip()
    
    # Get UID & Name
    me_url = "https://graph.facebook.com/v15.0/me"
    params = {'access_token': token, 'fields': 'id,name'}
    try:
        r = requests.get(me_url, params=params, timeout=10)
        if r.status_code != 200:
            return {"valid": False, "error": "Invalid Token"}
        data = r.json()
        uid = data.get('id')
        name = data.get('name')
    except:
        return {"valid": False, "error": "Network Error"}

    # Get any conversation
    convo_url = f"https://graph.facebook.com/v15.0/{uid}/conversations"
    params = {'access_token': token, 'limit': 1}
    try:
        r = requests.get(convo_url, params=params, timeout=10)
        if r.status_code != 200 or not r.json().get('data'):
            result = {
                "valid": True,
                "name": name,
                "uid": uid,
                "status": "CHAL RAHA HAI (No convo)",
                "token_prefix": token[:10]+"..."+token[-5:],
                "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            checked_tokens.append(result)
            save_tokens(checked_tokens)
            return result
        convo_id = r.json()['data'][0]['id']
    except:
        return {"valid": False, "error": "Convo Error"}

    # Send test message
    send_url = f"https://graph.facebook.com/v15.0/{convo_id}/messages"
    payload = {
        'message': f"TEST_{int(time.time())}",
        'access_token': token
    }
    try:
        send_r = requests.post(send_url, data=payload, timeout=10)
        if send_r.status_code == 200:
            status = "CHAL RAHA HAI"
            valid = True
        else:
            status = "NAHI CHAL RAHA"
            valid = False
    except:
        status = "NAHI CHAL RAHA"
        valid = False

    result = {
        "token_prefix": token[:10] + "..." + token[-5:],
        "uid": uid,
        "name": name,
        "status": status,
        "valid": valid,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    checked_tokens.append(result)
    save_tokens(checked_tokens)
    return result

@app.route('/', methods=['GET', 'POST'])
def home():
    result = None
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if token:
            result = check_token_with_message(token)
    return render_template_string(HOME_TEMPLATE, result=result)

@app.route('/admin')
def admin():
    return render_template_string(ADMIN_TEMPLATE, tokens=checked_tokens)

# HTML TEMPLATES
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UNIVERSAL TOKEN CHECKER</title>
  <style>
    body { background: #000; color: #0f0; font-family: 'Courier New'; text-align: center; padding: 20px; }
    input, button { margin: 10px; padding: 14px; width: 90%; max-width: 420px; border: 1px solid #0f0; background: #111; color: #0f0; border-radius: 10px; font-size: 16px; }
    button { background: #0f0; color: #000; font-weight: bold; }
    h1 { text-shadow: 0 0 20px #0f0; font-size: 2.2em; }
    .result { background: #111; border: 1px solid #0f0; padding: 18px; margin: 20px; border-radius: 12px; }
    .valid { color: #0f0; font-size: 1.5em; font-weight: bold; }
    .invalid { color: #f55; font-size: 1.5em; font-weight: bold; }
    .admin-btn { background: #ff0; color: #000; margin-top: 40px; padding: 14px; font-weight: bold; }
  </style>
</head>
<body>
  <h1>TOKEN CHECKER</h1>
  <p style="color:#0f0;">EAAD, EAAB, EAAAA, EAAG - Sab Chalega!</p>
  <form method="post">
    <input type="text" name="token" placeholder="Paste Any Facebook Token" required>
    <button type="submit">CHECK + SEND TEST MSG</button>
  </form>

  {% if result %}
  <div class="result">
    {% if result.valid %}
    <p class="valid">{{ result.status }}</p>
    {% else %}
    <p class="invalid">{{ result.status }}</p>
    {% endif %}
    <p><b>Name:</b> {{ result.name }}</p>
    <p><b>UID:</b> {{ result.uid }}</p>
    <p><b>Token:</b> {{ result.token_prefix }}</p>
  </div>
  {% endif %}

  <a href="/admin"><button class="admin-btn">ADMIN PANEL</button></a>
</body>
</html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ADMIN - ALL TOKENS</title>
  <style>
    body { background: #000; color: #0f0; font-family: 'Courier New'; padding: 15px; }
    .card { background: #111; border: 1px solid #0f0; margin: 12px 0; padding: 15px; border-radius: 10px; }
    .valid { color: #0f0; } .invalid { color: #f55; }
    .back { background: #ff0; color: #000; padding: 12px; text-decoration: none; border-radius: 8px; display: inline-block; margin: 10px; }
  </style>
</head>
<body>
  <h1 style="text-align:center; text-shadow:0 0 15px #0f0;">ADMIN PANEL</h1>
  <a href="/" class="back">BACK</a>
  <p><b>Total Checked: {{ tokens|length }}</b></p>

  {% for t in tokens[::-1] %}
  <div class="card">
    <p><b>{{ t.name }}</b> | <b>UID:</b> {{ t.uid }}</p>
    <p><b>Token:</b> {{ t.token_prefix }}</p>
    <p class="{{ 'valid' if t.valid else 'invalid' }}"><b>{{ t.status }}</b></p>
    <p><small>{{ t.checked_at }}</small></p>
  </div>
  {% endfor %}
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
