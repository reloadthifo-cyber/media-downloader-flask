import os
import re
import requests
# Добавили функцию send_from_directory для безопасной отдачи sitemap и robots
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
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

@app.route('/download', methods=['POST'])
@limiter.limit("5 per minute; 60 per hour") 
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    agreed = data.get('agreed')
    
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Используем проверенный и отказоустойчивый шлюз Cobalt API
    # Он развернут на независимых серверах и мгновенно переваривает Shorts и обычный YouTube
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": video_url,
        "videoQuality": "720", # Оптимальное качество для быстрой отдачи
        "audioFormat": "mp3",
        "isNoTTWatermark": True
    }

    try:
        # Отправляем запрос к шлюзу
        response = requests.post(api_url, json=payload, headers=headers, timeout=8)
        
        if response.status_code == 200:
            res_data = response.json()
            status = res_data.get("status")
            
            # Если шлюз успешно сгенерировал прямую ссылку
            if status == "stream" or status == "redirect":
                direct_download_url = res_data.get("url")
                video_title = "YouTube Video"  # Шлюз отдает чистый поток
                
                return jsonify({
                    'success': True, 
                    'download_url': direct_download_url, 
                    'title': video_title
                })
            
            elif status == "picker":
                # Если видео содержит несколько потоков, берем первый доступный
                picker_items = res_data.get("picker", [])
                if picker_items:
                    direct_download_url = picker_items[0].get("url")
                    return jsonify({
                        'success': True, 
                        'download_url': direct_download_url, 
                        'title': "YouTube Video"
                    })

        # Если основной эндпоинт вернул ошибку, пробуем запасное зеркало шлюза
        fallback_url = "https://co.wuk.sh/api/json"
        response = requests.post(fallback_url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            direct_download_url = res_data.get("url")
            if direct_download_url:
                return jsonify({
                    'success': True, 
                    'download_url': direct_download_url, 
                    'title': "YouTube Video"
                })

        return jsonify({
            'success': False, 
            'error': 'Выбранное видео временно недоступно для обработки. Попробуйте другую ссылку.'
        }), 500

    except Exception as e:
        print(f"Ошибка внешнего API: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Произошла ошибка при согласовании потока. Повторите попытку позже.'
        }), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь прямое.', 410

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
