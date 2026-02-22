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
# In production, use Redis or a database
jobs = {}

def update_job_status(job_id, status, text=None, progress=0, filename=None):
    jobs[job_id] = {
        'status': status,
        'text': text,
        'progress': progress,
        'filename': filename,
        'timestamp': time.time()
    }

def progress_hook(job_id):
    def hook(d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%', '')
            try:
                progress = float(p)
            except:
                progress = 0
            update_job_status(job_id, 'downloading', f"Downloading... {p}%", progress)
        elif d['status'] == 'finished':
            update_job_status(job_id, 'processing', "Processing with ffmpeg...", 100)
    return hook

def download_task(job_id, url, format_opts):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{job_id}_%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook(job_id)],
            'format': format_opts.get('format_id', 'best'),
            # Bypass 403 Forbidden and other YouTube restrictions
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb', 'ios'],
                    'player_skip_bundle_url': True,
                }
            },
            'nocheckcertificate': True,
            'quiet': False,
            'no_warnings': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            # Use cookies.txt only if manually provided (avoids DPAPI error)
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            # Ensure ffmpeg is used for merging/converting
            'postprocessors': format_opts.get('postprocessors', [])
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # If it was an audio only download, yt-dlp might change extension
            if format_opts.get('is_audio'):
                filename = os.path.splitext(filename)[0] + '.mp3'

            update_job_status(job_id, 'completed', "Finished!", 100, os.path.basename(filename))
            
    except Exception as e:
        update_job_status(job_id, 'error', f"Error: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory('static', 'service-worker.js')

@app.route('/api/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        ydl_opts = {
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb', 'ios'],
                    'player_skip_bundle_url': True,
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            for f in info.get('formats', []):
                # We want video formats with resolution
                if f.get('vcodec') != 'none':
                    res = f.get('height')
                    if res and res in [360, 480, 720, 1080, 1440, 2160]:
                        # Check if it has audio or if it's video-only
                        has_audio = f.get('acodec') != 'none'
                        
                        formats.append({
                            'id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'quality': f'{res}p',
                            'note': f.get('format_note', ''),
                            'filesize': f.get('filesize_approx') or f.get('filesize'),
                            'has_audio': has_audio
                        })
            
            # Sort by quality (highest first)
            formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
            
            # Deduplicate by quality, preferring formats with audio if available
            unique_formats = []
            seen_quality = {}
            for f in formats:
                q = f['quality']
                if q not in seen_quality:
                    unique_formats.append(f)
                    seen_quality[q] = f
                else:
                    # If we found a format with the same quality, prefer the one with audio
                    if f['has_audio'] and not seen_quality[q]['has_audio']:
                        idx = next(i for i, x in enumerate(unique_formats) if x['quality'] == q)
                        unique_formats[idx] = f
                        seen_quality[q] = f

            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'formats': [{
                    'id': f['id'],
                    'ext': 'mp4' if not f['has_audio'] else f['ext'],
                    'quality': f['quality'],
                    'note': f'Video + Audio' if f['has_audio'] else 'HD (Video Only)',
                    'filesize': f['filesize'],
                    'needs_merge': not f['has_audio']
                } for f in unique_formats]
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    type = data.get('type') # 'video', 'audio'
    format_id = data.get('format_id')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    job_id = str(uuid.uuid4())
    update_job_status(job_id, 'starting', "Starting process...")

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
        # If we have a specific format_id, use it. 
        # By default, use bestvideo+bestaudio.
        # We append /best for safety if the specific ID isn't available for some reason.
        if format_id:
            format_opts = {
                'format_id': f'{format_id}+bestaudio/best'
            }
        else:
            format_opts = {
                'format_id': 'bestvideo+bestaudio/best'
            }

    thread = threading.Thread(target=download_task, args=(job_id, url, format_opts))
    thread.start()

    return jsonify({'job_id': job_id})

@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

@app.route('/api/file/<job_id>', methods=['GET'])
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'completed':
        return jsonify({'error': 'File not ready'}), 404
    
    return send_from_directory(DOWNLOAD_FOLDER, job['filename'], as_attachment=True)

# Cleanup task (runs in background periodically)
def cleanup():
    while True:
        now = time.time()
        for job_id in list(jobs.keys()):
            # Delete jobs older than 1 hour
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
        time.sleep(300) # Check every 5 minutes

cleanup_thread = threading.Thread(target=cleanup, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
