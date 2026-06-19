import os
import subprocess
import glob
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__, template_folder='.')

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    download_format = data.get('format', 'video')

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Базовые и самые стабильные опции для скачивания медиафайла
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
        'format': 'best',  # Скачивает один готовый файл целиком (обычно mp4)
        'noplaylist': True,
    }

    try:
        # Шаг 1: Скачиваем медиа как обычный файл
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Защита: проверяем реальное расширение файла (иногда yt-dlp качает mkv/webm вместо mp4)
        if not os.path.exists(filename):
            base_path = os.path.splitext(filename)[0]
            found_files = glob.glob(base_path + '.*')
            if found_files:
                filename = found_files[0]

        # Шаг 2: Если выбрано аудио — принудительно конвертируем скачанный файл в MP3
        if download_format == 'audio':
            mp3_filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Конвертируем с помощью системного ffmpeg
            subprocess.run([
                'ffmpeg', '-i', filename, 
                '-vn', '-acodec', 'libmp3lame', 
                '-q:a', '2', '-y', mp3_filename
            ], check=True)
            
            # Удаляем видео-оригинал, чтобы экономить место на хостинге
            if os.path.exists(filename) and filename != mp3_filename:
                os.remove(filename)
                
            filename = mp3_filename

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
        return send_file(file_path, as_attachment=True)
    return 'Файл не найден', 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
