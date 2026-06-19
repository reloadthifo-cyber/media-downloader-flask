import os
import glob
from flask import Flask, render_template, request, jsonify, send_file, after_this_request, make_response
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
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    file_path = os.path.join(DOWNLOAD_FOLDER, file_id)
    
    if os.path.exists(file_path):
        # Удаляем файл сразу после того, как он отправится пользователю
        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                app.logger.error(f"Ошибка при удалении файла: {e}")
            return response
            
        # Формируем специальный ответ с заголовками для обхода блокировок iOS (iPhone)
        response = make_response(send_file(file_path, as_attachment=True, download_name=file_id))
        response.headers['Content-Description'] = 'File Transfer'
        # Маскируем под поток байт, чтобы Айфон не запускал плеер, а сохранял видео в Загрузки
        response.headers['Content-Type'] = 'application/octet-stream' 
        response.headers['Content-Disposition'] = f'attachment; filename="{file_id}"'
        
        return response
    
    return 'Файл не найден', 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
