import os
import glob
import uuid  # Добавили генератор уникальных безопасных имён
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=BASE_DIR
)

# НАСТРОЙКА ЗАЩИТЫ ОТ DDOS
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'success': False, 
        'error': 'Слишком много запросов! Пожалуйста, подождите немного перед следующим действием.'
    }), 429

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(BASE_DIR, 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory(BASE_DIR, 'robots.txt', mimetype='text/plain')


@app.route('/download', methods=['POST'])
@limiter.limit("3 per minute; 30 per hour") 
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    agreed = data.get('agreed')
    
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Генерируем случайное безопасное имя без пробелов и решёток
    unique_id = str(uuid.uuid4())
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        # Сохраняем строго под уникальным безопасным ID
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'max_filesize': 367001600
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)

        # Если yt-dlp изменил расширение (например, на .mkv или .webm)
        if not os.path.exists(filename):
            found = glob.glob(os.path.join(DOWNLOAD_FOLDER, f'{unique_id}.*'))
            if found: 
                filename = found[0]
            else:
                return jsonify({'success': False, 'error': 'Файл не найден после скачивания'}), 500

        # Сохраняем оригинальное название видео в сессию или передаем безопасную строку
        safe_title = info.get('title', 'Media')
        # Убираем символы, ломающие http-заголовки
        safe_title = "".join([c for c in safe_title if c.isalpha() or c.isdigit() or c in ' .-_']).strip()

        return jsonify({
            'success': True, 
            'file_id': os.path.basename(filename), 
            'title': safe_title if safe_title else 'video'
        })
        
    except Exception as e:
        if 'File is larger than max-filesize' in str(e):
            return jsonify({'success': False, 'error': 'Файл слишком большой. Лимит сервера: 350 МБ.'}), 400
        print(f"Ошибка парсинга: {str(e)}")
        return jsonify({'success': False, 'error': 'Не удалось обработать медиафайл. Попробуйте еще раз.'}), 500


@app.route('/get-file/<file_id>')
def get_file(file_id):
    # Защита от Path Traversal (чтобы через /.. не угнали системные файлы)
    file_id = os.path.basename(file_id)
    file_path = os.path.join(DOWNLOAD_FOLDER, file_id)

    if os.path.exists(file_path):
        def generate():
            try:
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
            finally:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    app.logger.error(f"Ошибка при удалении файла: {e}")

        response = Response(
            stream_with_context(generate()),
            mimetype='application/octet-stream'
        )
        # Отдаем файл браузеру с корректным принудительным скачиванием
        response.headers["Content-Disposition"] = f"attachment; filename={file_id}"
        return response

    return 'Файл не найден или уже был скачан', 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
