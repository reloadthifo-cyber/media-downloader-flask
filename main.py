import os
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


# ЮРИДИЧЕСКИ ЧИСТЫЙ МЕТОД: ПОЛУЧЕНИЕ ПРЯМОЙ ССЫЛКИ ЧЕРЕЗ INVIDIOUS API
@app.route('/download', methods=['POST'])
@limiter.limit("3 per minute; 30 per hour") 
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    
    # ПРОВЕРКА СОГЛАСИЯ
    agreed = data.get('agreed')
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # 1. Извлекаем ID видео из ссылки YouTube
  # 1. Извлекаем ID видео из ссылки YouTube
    video_id = None
    try:
        if "shorts/" in video_url:
            video_id = video_url.split("shorts/")[-1].split("?")[0].split("&")[0]
        elif "v=" in video_url:
            video_id = video_url.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[-1].split("?")[0]
        else:
            video_id = video_url.split("/")[-1].split("?")[0]
    except Exception:
        return jsonify({'success': False, 'error': 'Не удалось распознать ссылку на видео'}), 400

    # 2. Список стабильных публичных инстансов Invidious API
    # (Добавлены дополнительные рабочие узлы на случай высокой нагрузки)
    invidious_instances = [
        "https://invidious.io.lol",
        "https://yewtu.be",
        "https://vid.puffyan.us",
        "https://inv.tux.pizza",
        "https://invidious.nerdvpn.de",
        "https://invidious.flokinet.to"
    ]
    
    direct_download_url = None
    video_title = "Media"

    # 3. Опрашиваем узлы для получения прямой ссылки на видеопоток
    for instance in invidious_instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                res_data = response.json()
                video_title = res_data.get('title', 'Media')
                format_streams = res_data.get('formatStreams', [])
                
                if format_streams:
                    # Берем видео с наилучшим доступным качеством (со звуком) из списка потоков
                    direct_download_url = format_streams[-1].get('url')
                    break
        except Exception:
            continue  # Если один сервер недоступен, пробуем следующий

    # 4. Если ссылку найти удалось, отдаем её фронтенду для скачивания на стороне клиента
    if direct_download_url:
        return jsonify({
            'success': True, 
            'download_url': direct_download_url,  # Передаем прямую ссылку
            'title': video_title
        })
    else:
        return jsonify({
            'success': False, 
            'error': 'Не удалось получить ссылку для скачивания. Попробуйте позже или используйте другое видео.'
        }), 500


# Роут /get-file больше не нужен, так как файлы на сервере больше не хранятся!
# Но оставляем заглушку, чтобы старый фронтенд (если он закеширован) не падал с 404 ошибкой.
@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь прямое.', 410


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
