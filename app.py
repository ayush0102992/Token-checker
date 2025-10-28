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
    
    # Check me API
    me_url = "https://graph.facebook.com/v15.0/me"
    params = {'access_token': token, 'fields': 'id,name'}
    try:
        r = requests.get(me_url, params=params, timeout=10)
        if r.status_code != 200:
            return {"valid": False, "status": "NAHI CHAL RAHA", "error": r.json().get('error',{}).get('message','Invalid')}
        data = r.json()
        uid = data.get('id')
        name = data.get('name')
    except:
        return {"valid": False, "status": "NAHI CHAL RAHA", "error": "Network Error"}

    result = {
        "valid": True,
        "status": "CHAL RAHA HAI",
        "name": name,
        "uid": uid,
        "token_prefix": token[:10] + "..." + token[-5:],
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Try message send
    try:
        convo_url = f"https://graph.facebook.com/v15.0/{uid}/conversations"
        r = requests.get(convo_url, params={'access_token': token, 'limit': 1}, timeout=10)
        if r.status_code == 200 and r.json().get('data'):
            convo_id = r.json()['data'][0]['id']
            send_url = f"https://graph.facebook.com/v15.0/{convo_id}/messages"
            send_r = requests.post(send_url, data={'message': f"TEST_{int(time.time())}", 'access_token': token}, timeout=10)
            if send_r.status_code != 200:
                error = send_r.json().get('error',{}).get('message','').lower()
                if "messaging" in error or "permission" in error:
                    result["status"] = "CHAL RAHA HAI (No Msg Perm)"
                else:
                    result["status"] = "CHAL RAHA HAI (Msg Error)"
        else:
            result["status"] = "CHAL RAHA HAI (No Convo)"
    except:
        result["status"] = "CHAL RAHA HAI (Network)"

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

# TEMPLATES
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
    .admin-btn { background: #ff0; color: #000; margin-top: 40px; padding: 14px; font-weight: bold; border-radius: 10px; }
  </style>
</head>
<body>
  <h1>TOKEN CHECKER</h1>
  <p style="color:#0f0;">EAAD, EAAB, EAAAA, EAAG - Sab Chalega!</p>
  <form method="post">
    <input type="text" name="token" placeholder="Paste Any Facebook Token" required>
    <button type="submit">CHECK TOKEN</button>
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
