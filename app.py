from flask import Flask, render_template, request, jsonify
import yt_dlp
import os
import threading
import time
from collections import defaultdict
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use /tmp for Render (read-only filesystem)
DOWNLOAD_FOLDER = '/tmp/downloads' if os.environ.get('RENDER') else 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Store download progress
progress_data = defaultdict(dict)

class ProgressLogger:
    def __init__(self, job_id):
        self.job_id = job_id
        
    def __call__(self, d):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                if total > 0:
                    percent = (downloaded / total) * 100
                else:
                    percent = 0
                
                speed = d.get('speed')
                if speed:
                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
                    elif speed > 1024:
                        speed_str = f"{speed / 1024:.2f} KB/s"
                    else:
                        speed_str = f"{speed:.2f} B/s"
                else:
                    speed_str = "Calculating..."
                
                eta = d.get('eta', 0)
                if eta:
                    if eta < 60:
                        eta_str = f"{int(eta)}s"
                    else:
                        minutes = int(eta / 60)
                        seconds = int(eta % 60)
                        eta_str = f"{minutes}m {seconds}s"
                else:
                    eta_str = "Calculating..."
                
                filename = d.get('filename', 'Unknown')
                if '/' in filename:
                    filename = filename.split('/')[-1]
                elif '\\' in filename:
                    filename = filename.split('\\')[-1]
                
                if total > 1024 * 1024 * 1024:
                    size_str = f"{total / (1024 * 1024 * 1024):.2f} GB"
                elif total > 1024 * 1024:
                    size_str = f"{total / (1024 * 1024):.2f} MB"
                elif total > 1024:
                    size_str = f"{total / 1024:.2f} KB"
                else:
                    size_str = f"{total} B"
                
                progress_data[self.job_id] = {
                    'status': 'downloading',
                    'percent': round(percent, 1),
                    'speed': speed_str,
                    'eta': eta_str,
                    'filename': filename,
                    'total_size': size_str,
                }
                
            except Exception as e:
                logger.error(f"Progress error: {e}")
                
        elif d['status'] == 'finished':
            progress_data[self.job_id]['status'] = 'processing'
            progress_data[self.job_id]['percent'] = 100

def download_task(url, download_type, quality, job_id):
    """Background download task"""
    try:
        progress_data[job_id] = {
            'status': 'starting',
            'percent': 0,
            'speed': 'Initializing...',
            'eta': 'Calculating...',
            'filename': 'Preparing...',
            'total_size': 'Calculating...'
        }
        
        quality_map = {
            '2160p': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        }
        
        if download_type == 'video':
            format_str = quality_map.get(quality, quality_map['1080p'])
            ydl_opts = {
                'format': format_str,
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'progress_hooks': [ProgressLogger(job_id)],
                'merge_output_format': 'mp4',
                'keepvideo': False,
                'quiet': True,
                'no_warnings': True,
            }
        else:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'progress_hooks': [ProgressLogger(job_id)],
                'keepvideo': False,
                'quiet': True,
                'no_warnings': True,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown')
            
            # Clean temp files
            import glob
            temp_files = glob.glob(f'{DOWNLOAD_FOLDER}/*.f*.mp4') + glob.glob(f'{DOWNLOAD_FOLDER}/*.f*.webm') + glob.glob(f'{DOWNLOAD_FOLDER}/*.part')
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            
            progress_data[job_id]['status'] = 'finished'
            progress_data[job_id]['percent'] = 100
            progress_data[job_id]['message'] = f'Successfully downloaded: {title}'
            
    except Exception as e:
        progress_data[job_id]['status'] = 'error'
        progress_data[job_id]['message'] = f'Error: {str(e)}'
        logger.error(f"Download error: {e}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/fair-use')
def fair_use():
    return render_template('fair_use.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    download_type = data.get('type', 'video')
    quality = data.get('quality', '1080p')
    
    if not url:
        return jsonify({'success': False, 'message': 'URL required!'})
    
    job_id = f"job_{int(time.time() * 1000)}"
    
    thread = threading.Thread(target=download_task, args=(url, download_type, quality, job_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'job_id': job_id})

@app.route('/progress/<job_id>')
def get_progress(job_id):
    if job_id in progress_data:
        return jsonify(progress_data[job_id])
    else:
        return jsonify({'status': 'error', 'message': 'Job not found'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)