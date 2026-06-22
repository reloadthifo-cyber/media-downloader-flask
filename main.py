import os
import glob
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

# НАСТРОЙКА ЗАЩИТЫ ОТ DDOS / ФЛУДА
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
        'error': 'Слишком много запросов! Пожалуйста, подождите немного перед следующим скачиванием.'
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

    # Опции yt-dlp, которые успешно скачивали TikTok и Shorts на диск
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'max_filesize': 367001600,  # Ограничение 350 МБ
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            base_path = os.path.splitext(filename)[0]
            found = glob.glob(base_path + '.*')
            if found: 
                filename = found[0]

        return jsonify({
            'success': True, 
            'file_id': os.path.basename(filename), 
            'title': info.get('title', 'Media')
        })
    except Exception as e:
        if 'File is larger than max-filesize' in str(e):
            return jsonify({'success': False, 'error': 'Файл слишком большой. Лимит сервера: 350 МБ.'}), 400
        print(f"Ошибка скачивания: {str(e)}")
        return jsonify({'success': False, 'error': 'Не удалось получить ссылку для скачивания. Пожалуйста, попробуйте другую ссылку или повторите позже.'}), 500


# Функция отдачи файла кусочками и его гарантированного удаления с сервера
@app.route('/get-file/<file_id>')
def get_file(file_id):
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
        response.headers["Content-Disposition"] = f"attachment; filename={file_id}"
        return response

    return 'Файл не найден', 404


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
