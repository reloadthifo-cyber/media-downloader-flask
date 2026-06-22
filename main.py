import os
import requests
# Добавили функцию send_from_directory для безопасной отдачи sitemap и robots
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Получаем путь к корневой директории
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=BASE_DIR
)

# НАСТРОЙКА ЗАЩИТЫ ОТ DDOS / ФЛУДА
limiter = Limiter(
    get_remote_address,               # Определяем пользователя по его IP-адресу
    app=app,
    default_limits=[],                # По умолчанию лимиты на весь сайт НЕ ставим
    storage_uri="memory://"           # Храним данные в оперативной памяти
)

# Кастомная ошибка, если пользователь превысил лимит запросов
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'success': False, 
        'error': 'Слишком много запросов! Пожалуйста, подождите немного перед следующим действием.'
    }), 429

@app.route('/')
def home():
    return render_template('index.html')


# ==========================================
# СЛУЖЕБНЫЕ ФАЙЛЫ ДЛЯ ПОИСКОВИКОВ
# ==========================================

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(BASE_DIR, 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory(BASE_DIR, 'robots.txt', mimetype='text/plain')

# ==========================================


# МЕТОД ОБРАБОТКИ ЗАПРОСА СКАЧИВАНИЯ
@app.route('/download', methods=['POST'])
@limiter.limit("3 per minute; 30 per hour") 
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    agreed = data.get('agreed')
    
    # ПРОВЕРКА СОГЛАСИЯ
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Заголовки для обхода блокировок внешних шлюзов
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "url": video_url,
        "videoQuality": "720",
        "audioFormat": "mp3",
        "isNoTTWatermark": True
    }

    # Используем отказоустойчивые API-шлюзы для мгновенного разбора ссылок
    api_endpoints = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json",
        "https://cobalt.api.g7kk.com/api/json"
    ]

    for api_url in api_endpoints:
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                status = res_data.get("status")
                
                if status in ["stream", "redirect"]:
                    direct_url = res_data.get("url")
                    if direct_url:
                        return jsonify({
                            'success': True, 
                            'download_url': direct_url, 
                            'title': 'Media File'
                        })
                
                elif status == "picker":
                    picker_items = res_data.get("picker", [])
                    if picker_items and picker_items[0].get("url"):
                        return jsonify({
                            'success': True, 
                            'download_url': picker_items[0].get("url"), 
                            'title': 'Media File'
                        })
        except Exception:
            continue

    return jsonify({
        'success': False, 
        'error': 'Сервер не смог получить ссылку для скачивания. Пожалуйста, попробуйте другую ссылку или повторите позже.'
    }), 500


# Заглушка для старого метода, чтобы фронтенд не выдавал ошибку 404
@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь идет напрямую.', 410


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
