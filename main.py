import os
# Добавили функцию send_from_directory для безопасной отдачи sitemap и robots
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp

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

    # Настройки для извлечения прямой ссылки без скачивания файла на сервер Render
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # Ищем лучшее готовое качество со звуком (обычно 720p)
        'skip_download': True,          # Нам нужна только ссылка, сам файл не качаем
        'quiet': True,
        'no_warnings': True,
        # Обход замедлений и базовых проверок YouTube:
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Извлекаем метаданные видео
            info = ydl.extract_info(video_url, download=False)
            
            # Получаем прямую ссылку на видеопоток и название
            direct_download_url = info.get('url')
            video_title = info.get('title', 'Media')

            if direct_download_url:
                return jsonify({
                    'success': True, 
                    'download_url': direct_download_url, 
                    'title': video_title
                })
            else:
                return jsonify({'success': False, 'error': 'Поток видео не найден.'}), 500

    except Exception as e:
        # Логируем ошибку в консоль Render, чтобы ее было видно, если что-то пойдет не так
        print(f"Ошибка yt-dlp: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Не удалось получить ссылку. Убедитесь, что видео открыто для публичного просмотра.'
        }), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь прямое.', 410

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
