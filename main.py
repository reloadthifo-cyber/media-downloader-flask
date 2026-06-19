import os
import glob
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, after_this_request
import yt_dlp

# Получаем путь к корневой директории, где лежат main.py и index.html
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    # Указываем Flask искать HTML-шаблоны прямо в корне, а не в папке templates
    template_folder=BASE_DIR,
    static_folder=BASE_DIR
)

DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
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
        'format': 'best', # Скачиваем лучшее качество без конвертации
        'noplaylist': True,
        'max_filesize': 350 * 1024 * 1024, # Дополнительная защита: не качать файлы больше 350 МБ
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Если расширение не определилось (защита для yt-dlp)
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
        # Если файл упал из-за превышения размера
        if 'File is larger than max-filesize' in str(e):
            return jsonify({'success': False, 'error': 'Файл слишком большой. Лимит сервера: 350 МБ.'}), 400
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    file_path = os.path.join(DOWNLOAD_FOLDER, file_id)
    
    if os.path.exists(file_path):
        # Функция-генератор: читает файл блоками по 8 КБ и сразу отдает в сеть
        def generate():
            try:
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
            finally:
                # Этот блок выполнится ОГОВОРОЧНО после того, как генератор закончит отдачу
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    app.logger.error(f"Ошибка при удалении файла в генераторе: {e}")

        # Формируем безопасный потоковый ответ
        response = Response(
            stream_with_context(generate()),
            mimetype='application/octet-stream'
        )
        # Добавляем заголовок, чтобы браузер скачивал файл, а не открывал внутри вкладки
        response.headers["Content-Disposition"] = f"attachment; filename={file_id}"
        return response
    
    return 'Файл не найден', 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
