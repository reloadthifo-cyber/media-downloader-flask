import os
import glob
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
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
    # --- АВТООЧИСТКА СТАРЫХ ФАЙЛОВ ---
    # Удаляем файлы старше 10 минут, чтобы на Render не забивалось место
    try:
        now = time.time()
        for f in os.listdir(DOWNLOAD_FOLDER):
            file_p = os.path.join(DOWNLOAD_FOLDER, f)
            if os.path.isfile(file_p) and os.stat(file_p).st_mtime < now - 600:
                os.remove(file_p)
    except Exception as e:
        app.logger.error(f"Ошибка при очистке старых файлов: {e}")
    # ----------------------------------

    data = request.json or {}
    video_url = data.get('url')

    # ПРОВЕРКА СОГЛАСИЯ
    agreed = data.get('agreed')
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
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
    # Безопасно извлекаем имя файла (защита от Path Traversal)
    secure_id = os.path.basename(file_id)
    file_path = os.path.join(DOWNLOAD_FOLDER, secure_id)

    if os.path.exists(file_path):
        # send_from_directory корректно поддерживает докачку (Range requests)
        # и стабильно работает на любых браузерах и прокси-серверах
        return send_from_directory(
            DOWNLOAD_FOLDER, 
            secure_id, 
            as_attachment=True,
            download_name=secure_id
        )

    return 'Файл не найден или был удален по таймеру', 404


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
