import os
import uuid
import threading
import time
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
import yt_dlp

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configuration
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# In-memory storage for job statuses
jobs = {}

def update_job_status(job_id, status, text=None, progress=0, filename=None, downloaded_bytes="0 MB", total_bytes="? MB"):
    jobs[job_id] = {
        'status': status,
        'text': text,
        'progress': progress,
        'filename': filename,
        'downloaded_mb': downloaded_bytes,
        'total_mb': total_bytes,
        'timestamp': time.time()
    }

def format_bytes(b):
    if b is None: return "? MB"
    return f"{b / (1024 * 1024):.2f} MB"

def progress_hook(job_id):
    def hook(d):
        if d['status'] == 'downloading':
            p_str = d.get('_percent_str', '0%').replace('%', '').strip()
            downloaded = format_bytes(d.get('downloaded_bytes'))
            total = format_bytes(d.get('total_bytes') or d.get('total_bytes_estimate'))
            
            try:
                progress = float(p_str)
            except:
                progress = 0
                
            update_job_status(
                job_id, 
                'downloading', 
                f"Сваляне: {p_str}% ({downloaded} от {total})", 
                progress,
                downloaded_bytes=downloaded,
                total_bytes=total
            )
        elif d['status'] == 'finished':
            update_job_status(job_id, 'processing', "Обработка и сливане на файловете...", 100)
    return hook

def download_task(job_id, url, format_opts):
    try:
        # Detect ffmpeg (common Render path vs local)
        ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg', 'ffmpeg')
        
        # Check if we are in dev environment and ffmpeg is in sibling python_desktop/bin
        if not os.path.exists(ffmpeg_path):
            potential_path = os.path.abspath(os.path.join(os.getcwd(), '..', 'python_desktop', 'bin', 'ffmpeg.exe'))
            if os.path.exists(potential_path):
                ffmpeg_path = potential_path
        
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = 'ffmpeg' # Fallback to system path

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{job_id}_%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook(job_id)],
            'format': format_opts.get('format_id', 'best'),
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr', 'ios'],
                    'formats': ['missing_pot'],
                }
            },
            'nocheckcertificate': True,
            'quiet': False,
            'no_warnings': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            },
            'ffmpeg_location': ffmpeg_path,
            'merge_output_format': 'mp4',
            'postprocessors': format_opts.get('postprocessors', [])
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if format_opts.get('is_audio'):
                filename = os.path.splitext(filename)[0] + '.mp3'

            update_job_status(job_id, 'completed', "Завършено успешно!", 100, os.path.basename(filename))
            
    except Exception as e:
        update_job_status(job_id, 'error', f"Грешка: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_videos():
    data = request.json
    query = data.get('query')
    if not query:
        return jsonify({'error': 'Моля въведете ключова дума'}), 400

    try:
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr', 'ios'],
                    'formats': ['missing_pot'],
                }
            },
            'http_headers': {
                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"ytsearch5:{query}", download=False)
            results = []
            
            if 'entries' in search_result:
                for entry in search_result['entries']:
                    results.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'thumbnail': entry.get('thumbnails')[0]['url'] if entry.get('thumbnails') else None,
                        'channel': entry.get('uploader'),
                        'duration': entry.get('duration_string'),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                    })
            return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/formats', methods=['POST'])
def get_formats():
    data = request.json
    url_or_id = data.get('url') or data.get('id')
    if not url_or_id:
        return jsonify({'error': 'Моля въведете URL или ID'}), 400

    if not url_or_id.startswith('http'):
        url = f"https://www.youtube.com/watch?v={url_or_id}"
    else:
        url = url_or_id

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr', 'ios'],
                    'formats': ['missing_pot'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none':
                    res = f.get('height')
                    if res in [360, 480, 720, 1080]:
                        formats.append({
                            'id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'quality': f'{res}p',
                            'note': f.get('format_note', ''),
                            'filesize': f.get('filesize_approx') or f.get('filesize'),
                            'has_audio': f.get('acodec') != 'none'
                        })
            
            formats.sort(key=lambda x: (int(x['quality'].replace('p', '')), x['has_audio']), reverse=True)
            seen_quality = set()
            unique_formats = []
            for f in formats:
                if f['quality'] not in seen_quality:
                    unique_formats.append(f)
                    seen_quality.add(f['quality'])

            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'formats': unique_formats
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    type = data.get('type') 
    format_id = data.get('format_id')
    
    if not url:
        return jsonify({'error': 'URL е задължителен'}), 400

    job_id = str(uuid.uuid4())
    update_job_status(job_id, 'starting', "Инициализиране...")

    format_opts = {}
    if type == 'audio':
        format_opts = {
            'format_id': 'bestaudio/best',
            'is_audio': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }
    else:
        format_opts = {
            'format_id': f'{format_id}+bestaudio/best' if format_id else 'bestvideo+bestaudio/best'
        }

    thread = threading.Thread(target=download_task, args=(job_id, url, format_opts))
    thread.start()

    return jsonify({'job_id': job_id})

@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Задачата не е намерена'}), 404
    return jsonify(job)

@app.route('/api/file/<job_id>', methods=['GET'])
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'completed':
        return jsonify({'error': 'Файлът не е готов'}), 404
    return send_from_directory(DOWNLOAD_FOLDER, job['filename'], as_attachment=True)

def cleanup():
    while True:
        now = time.time()
        for job_id in list(jobs.keys()):
            if now - jobs[job_id]['timestamp'] > 3600:
                filename = jobs[job_id].get('filename')
                if filename:
                    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except:
                            pass
                del jobs[job_id]
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
