import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=BASE_DIR
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

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
@limiter.limit("5 per minute; 60 per hour") 
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    agreed = data.get('agreed')
    
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Настройки yt-dlp с обходом блокировок хостингов
    ydl_opts = {
        'format': 'best',
        'skip_download': True, # Нам нужна только ссылка, файл не сохраняем
        'quiet': True,
        'no_warnings': True,
        # Имитируем трафик с мобильного приложения, чтобы YouTube не выдавал 403 Forbidden
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
                'skip': ['dash', 'hls']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            direct_download_url = info.get('url')
            video_title = info.get('title', 'Media')

            if direct_download_url:
                return jsonify({
                    'success': True, 
                    'download_url': direct_download_url, 
                    'title': video_title
                })
            else:
                return jsonify({'success': False, 'error': 'Не удалось извлечь поток видео.'}), 500

    except Exception as e:
        print(f"Ошибка yt-dlp core: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Не удалось обработать ссылку. Убедитесь, что видео открыто для просмотра.'
        }), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь прямое.', 410

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
