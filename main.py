import os
import subprocess
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
    data = request.json
    video_url = data.get('url')
    download_format = data.get('format', 'video')

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Обновленные опции для пробива блокировки YouTube
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
        'format': 'best',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'noplaylist': True,
        # ТРЮК: Заставляем использовать IOS/Android клиенты плеера (они реже выдают 429 ошибку)
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android'],
                'skip': ['webpage']
            }
        }
    }

    try:
        # Шаг 1: Скачиваем медиа как обычное видео
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
        
        # Шаг 2: Если пользователь выбрал аудио — конвертируем
        if download_format == 'audio':
            mp3_filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Запуск системного ffmpeg
            subprocess.run([
                'ffmpeg', '-i', filename, 
                '-vn', '-acodec', 'libmp3lame', 
                '-q:a', '2', '-y', mp3_filename
            ], check=True)
            
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
