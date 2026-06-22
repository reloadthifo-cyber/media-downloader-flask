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

# Функция точного поиска ID видео
def extract_youtube_id(url):
    pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)|shorts/|watch\?.*v=)|youtu\.be/)([^"&?/\s]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

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

    # 1. Извлекаем ID с помощью регулярного выражения (поддерживает Shorts на 100%)
    video_id = extract_youtube_id(video_url)
    if not video_id:
        return jsonify({'success': False, 'error': 'Не удалось распознать ссылку на видео. Проверьте формат.'}), 400

    # 2. Обновленный список активных и стабильных инстансов API Invidious
    invidious_instances = [
        "https://invidious.io.lol",
        "https://yewtu.be",
        "https://inv.tux.pizza",
        "https://invidious.nerdvpn.de",
        "https://iv.melmac.space",
        "https://invidious.perennialte.ch",
        "https://yt.artemislena.eu",
        "https://invidious.flokinet.to"
    ]
    
    direct_download_url = None
    video_title = "Media"

    # 3. Перебираем инстансы в поиске рабочего потока
    for instance in invidious_instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            response = requests.get(api_url, timeout=4)
            
            if response.status_code == 200:
                res_data = response.json()
                video_title = res_data.get('title', 'Media')
                format_streams = res_data.get('formatStreams', [])
                
                if format_streams:
                    # Выбираем стабильный поток (обычно последний в списке — наилучший со звуком)
                    direct_download_url = format_streams[-1].get('url')
                    if direct_download_url:
                        break
        except Exception:
            continue

    # 4. Возвращаем результат
    if direct_download_url:
        return jsonify({
            'success': True, 
            'download_url': direct_download_url, 
            'title': video_title
        })
    else:
        return jsonify({
            'success': False, 
            'error': 'Все узлы обработки перегружены. Пожалуйста, попробуйте еще раз через минуту или с другим видео.'
        }), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь прямое.', 410

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
