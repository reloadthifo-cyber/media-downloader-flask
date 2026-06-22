import os
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
        'error': 'Слишком много запросов! Пожалуйста, подождите немного.'
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
@limiter.limit("10 per minute; 100 per hour") 
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    agreed = data.get('agreed')
    
    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400

    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    # Правильные заголовки и структура JSON для Cobalt API
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "url": video_url,
        "videoQuality": "720",  # Числовая строка или стандартное качество
        "audioFormat": "mp3",
        "isNoTTWatermark": True
    }

    # Список зеркал Cobalt API для максимальной надежности
    api_endpoints = [
        "https://api.cobalt.tools/api/json",
        "https://co.wuk.sh/api/json",
        "https://cobalt.api.g7kk.com/api/json"
    ]

    for api_url in api_endpoints:
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                res_data = response.json()
                status = res_data.get("status")
                
                # Обработка успешных статусов согласно спецификации
                if status in ["stream", "redirect"]:
                    direct_url = res_data.get("url")
                    if direct_url:
                        return jsonify({
                            'success': True, 
                            'download_url': direct_url, 
                            'title': 'YouTube Video'
                        })
                
                elif status == "picker":
                    picker_items = res_data.get("picker", [])
                    if picker_items and picker_items[0].get("url"):
                        return jsonify({
                            'success': True, 
                            'download_url': picker_items[0].get("url"), 
                            'title': 'YouTube Video'
                        })
        except Exception as e:
            print(f"Эндпоинт {api_url} завершился ошибкой: {str(e)}")
            continue

    return jsonify({
        'success': False, 
        'error': 'Не удалось получить прямую ссылку через шлюзы. Попробуйте еще раз или используйте другое видео.'
    }), 500

@app.route('/get-file/<file_id>')
def get_file(file_id):
    return 'Этот метод устарел, скачивание теперь прямое.', 410

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
