import os
import subprocess
import glob
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import imageio_ffmpeg  # Наш секретный козырь для конвертации

# Убрали template_folder='.', так как у тебя теперь есть нормальная папка templates
app = Flask(__name__)

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

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
        'format': 'best',
        'noplaylist': True,
    }

    try:
        # Скачиваем оригинальный файл (MP4)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Проверка реального расширения
        if not os.path.exists(filename):
            base_path = os.path.splitext(filename)[0]
            found_files = glob.glob(base_path + '.*')
            if found_files:
                filename = found_files[0]

        # Конвертация в аудио
        if download_format == 'audio':
            mp3_filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Получаем 100% рабочий путь к ffmpeg из Python-библиотеки
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            subprocess.run([
                ffmpeg_exe, '-i', filename, 
                '-vn', '-acodec', 'libmp3lame', 
                '-q:a', '2', '-y', mp3_filename
            ], check=True)
            
            # Удаляем исходный видеофайл
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
