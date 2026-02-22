import os
import sys
import yt_dlp

class YoutubeDownloader:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self):
        """Locates ffmpeg in several potential locations, including Android support."""
        locations = []
        
        # 1. User Application Data (for downloaded ffmpeg on Windows)
        if sys.platform == "win32":
            app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'YoutubeDownloaderPro')
            locations.append(os.path.join(app_data_dir, 'ffmpeg.exe'))

        # 2. If running as a bundled executable (Windows/Linux)
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            internal_dir = os.path.join(base_dir, '_internal')
            ext = ".exe" if sys.platform == "win32" else ""
            locations.extend([
                os.path.join(base_dir, 'bin', f'ffmpeg{ext}'),
                os.path.join(internal_dir, 'bin', f'ffmpeg{ext}'),
                os.path.join(base_dir, f'ffmpeg{ext}'),
                os.path.join(internal_dir, f'ffmpeg{ext}'),
            ])
        
        # 3. Development paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ext = ".exe" if sys.platform == "win32" else ""
        locations.extend([
            os.path.join(script_dir, 'bin', f'ffmpeg{ext}'),
            os.path.join(script_dir, f'ffmpeg{ext}'),
        ])
        
        # Check all possible locations
        for loc in locations:
            if os.path.exists(loc):
                return loc
            
        # 4. Fallback to PATH (common for Android/Linux/macOS)
        return 'ffmpeg'

    def is_ffmpeg_available(self):
        """Checks if ffmpeg is available on the system."""
        path = self._find_ffmpeg()
        if path == 'ffmpeg':
            import subprocess
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                return True
            except:
                return False
        return os.path.exists(path)

    def download_ffmpeg(self, progress_callback=None):
        """Downloads ffmpeg.exe for Windows."""
        import requests
        import zipfile
        import io
        
        # Static build URL for Windows (gyan.dev)
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'YoutubeDownloaderPro')
        os.makedirs(app_data_dir, exist_ok=True)
        ffmpeg_dest = os.path.join(app_data_dir, 'ffmpeg.exe')

        if os.path.exists(ffmpeg_dest):
            return True

        try:
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            bytes_downloaded = 0
            zip_buffer = io.BytesIO()

            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    zip_buffer.write(chunk)
                    bytes_downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(bytes_downloaded / total_size * 100)

            with zipfile.ZipFile(zip_buffer) as z:
                # Find ffmpeg.exe in the zip
                for file_info in z.infolist():
                    if file_info.filename.endswith('ffmpeg.exe'):
                        # Extract only ffmpeg.exe
                        with z.open(file_info) as source, open(ffmpeg_dest, 'wb') as target:
                            import shutil
                            shutil.copyfileobj(source, target)
                        break
            
            # Update path
            self.ffmpeg_path = ffmpeg_dest
            return True
        except Exception as e:
            raise Exception(f"Грешка при сваляне на FFmpeg: {str(e)}")

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%', '')
            try:
                percent = float(p)
                if self.progress_callback:
                    self.progress_callback(percent)
            except ValueError:
                pass

    def search(self, query, max_results=5):
        """Searches for videos and returns a list of results."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',  # Fast extraction
            'force_generic_extractor': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                search_query = f"ytsearch{max_results}:{query}"
                info = ydl.extract_info(search_query, download=False)
                
                results = []
                if 'entries' in info:
                    for entry in info['entries']:
                        results.append({
                            'title': entry.get('title'),
                            'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            'thumbnail': entry.get('thumbnail'),
                            'duration': entry.get('duration'),
                            'id': entry.get('id')
                        })
                return results
            except Exception as e:
                raise Exception(f"Грешка при търсене: {str(e)}")

    def get_info(self, url):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': self.ffmpeg_path,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr', 'ios'],
                    'formats': ['missing_pot'],
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                formats = info.get('formats', [])
                
                resolutions = set()
                audio_bitrates = set()

                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('height'):
                        resolutions.add(f['height'])
                    
                    if f.get('acodec') != 'none' and f.get('abr'):
                        audio_bitrates.add(int(f['abr']))
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'resolutions': sorted(list(resolutions), reverse=True),
                    'audio_bitrates': sorted(list(audio_bitrates), reverse=True),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url')
                }
            except Exception as e:
                raise Exception(f"Error fetching info: {str(e)}")

    def download(self, url, save_path, resolution='720', mode='video_audio'):
        common_opts = {
            'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
            'progress_hooks': [self._progress_hook],
            'ffmpeg_location': self.ffmpeg_path,
            'nocheckcertificate': True,
            'windowsfilenames': True,
            'overwrites': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr', 'ios'],
                    'formats': ['missing_pot']
                }
            },
        }
        
        # ... (rest of mode logic stays same)
        if mode == 'audio_only':
            bitrate = resolution if resolution else '192' 
            ydl_opts = {
                **common_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': str(bitrate),
                }],
            }
        elif mode == 'video_only':
            ydl_opts = {
                **common_opts,
                'format': f'bestvideo[height<={resolution}]/best',
            }
        else:
            ydl_opts = {
                **common_opts,
                'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]',
                'merge_output_format': 'mp4',
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # If it was an audio download, the extension changed to .mp3
            if mode == 'audio_only':
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            # Check if file exists and has size > 0
            if not os.path.exists(filename):
                # Try to find the file if the title substitution changed something
                # This is fallback logic
                pass
            elif os.path.getsize(filename) == 0:
                raise Exception("Сваленият файл е празен. Вероятно проблем с YouTube или интернет връзката.")
            
            return filename
