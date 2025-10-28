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
            result = {"valid": True, "name": name, "uid": uid, "status": "CHAL RAHA HAI (No convo)", "token_prefix": token[:10]+"..."+token[-5:], "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}
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

# TEMPLATES (Same as before)
HOME_TEMPLATE = '''... [same as before] ...'''
ADMIN_TEMPLATE = '''... [same as before] ...'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
