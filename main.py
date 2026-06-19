import os
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__, template_folder='.')

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    video_url = data.get('url')
    download_format = data.get('format', 'video')

    # --- ВСТАВЛЯЙ СЮДА ---
    import shutil
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        print(f"DEBUG: FFmpeg найден по пути: {ffmpeg_path}")
    else:
        print("DEBUG: ВНИМАНИЕ! FFmpeg НЕ НАЙДЕН!")
    # ---------------------
    
    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400
    
    # ... дальше остальной код ...

    # Настройки теперь внутри функции, с правильными отступами
# Базовые настройки
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
        # Убираем строку 'ffmpeg_location': 'ffmpeg',
    }
    # Настраиваем формат
    if download_format == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            
            if download_format == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            return jsonify({
                'success': True, 
                'file_id': os.path.basename(filename),
                'title': info.get('title', 'Audio' if download_format == 'audio' else 'Video')
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
