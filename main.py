import os
import glob
# Добавили функцию send_from_directory для безопасной отдачи sitemap и robots
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_from_directory
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
    default_limits=[],                # По умолчанию лимиты на весь сайт НЕ ставим (чтобы не блочить обычных людей)
    storage_uri="memory://"           # Храним данные в оперативной памяти (для 1 сервера этого за глаза)
)

DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Кастомная ошибка, если пользователь превысил лимит запросов
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
# НОВЫЙ БЛОК: СЛУЖЕБНЫЕ ФАЙЛЫ ДЛЯ ПОИСКОВИКОВ
# ==========================================

@app.route('/sitemap.xml')
def sitemap():
    # Отдаем sitemap.xml прямо из корневой папки сайта (BASE_DIR)
    return send_from_directory(BASE_DIR, 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    # Отдаем robots.txt прямо из корневой папки сайта (BASE_DIR)
    return send_from_directory(BASE_DIR, 'robots.txt', mimetype='text/plain')

# ==========================================


# Ограничиваем только эту кнопку: максимум 3 скачивания в минуту и 30 в час с одного IP
# Ограничиваем только эту кнопку: максимум 3 скачивания в минуту и 30 в час с одного IP
@app.route('/download', methods=['POST'])
@limiter.limit("3 per minute; 30 per hour") 
@@ -72,60 +73,61 @@
    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

ydl_opts = {
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
        # Просим чистый оригинал без рендеринга водяного знака
        'format': 'bestvideo+bestaudio/best', 
        'noplaylist': True,
        'max_filesize': 350 * 1024 * 1024,
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
        return jsonify({'success': False, 'error': str(e)}), 500

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
