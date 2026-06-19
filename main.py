import os
from flask import Flask, render_template, request, jsonify
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=BASE_DIR,
    static_folder=BASE_DIR
)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json or {}
    video_url = data.get('url')
    agreed = data.get('agreed')

    if not agreed:
        return jsonify({'success': False, 'error': 'Вы должны согласиться с условиями'}), 400
    if not video_url:
        return jsonify({'success': False, 'error': 'Ссылка пустая'}), 400

    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # download=False — сервер НИЧЕГО не качает на диск
            info = ydl.extract_info(video_url, download=False)
            
            # Получаем прямую временную ссылку на медиапоток
            direct_url = info.get('url')
            
            if not direct_url:
                return jsonify({'success': False, 'error': 'Не удалось получить ссылку'}), 500

            return jsonify({
                'success': True,
                'direct_url': direct_url, # Отправляем ссылку браузеру
                'title': info.get('title', 'Video')
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
