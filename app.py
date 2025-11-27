from flask import Flask, render_template, request, jsonify
import yt_dlp
import os
import threading
import uuid
from datetime import datetime

app = Flask(__name__)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Store download progress
download_jobs = {}

def format_bytes(bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"

def format_eta(seconds):
    """Convert seconds to human readable ETA"""
    if seconds is None:
        return "Calculating..."
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"

def progress_hook(d, job_id):
    """Hook to track download progress"""
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        eta = d.get('eta', 0)
        
        percent = (downloaded / total * 100) if total > 0 else 0
        
        download_jobs[job_id] = {
            'status': 'downloading',
            'percent': percent,
            'downloaded': format_bytes(downloaded),
            'total_size': format_bytes(total),
            'speed': format_bytes(speed) + '/s' if speed else 'Calculating...',
            'eta': format_eta(eta),
            'filename': d.get('filename', 'Unknown').split('/')[-1]
        }
        
    elif d['status'] == 'finished':
        download_jobs[job_id]['status'] = 'finished'
        download_jobs[job_id]['percent'] = 100
        download_jobs[job_id]['message'] = f"Download completed: {d.get('filename', 'file').split('/')[-1]}"

def download_video(url, download_type, quality, job_id):
    """Background download function"""
    try:
        quality_map = {
            '2160p': 'bestvideo[height<=2160]+bestaudio/best',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best',
            '720p': 'bestvideo[height<=720]+bestaudio/best',
            '480p': 'bestvideo[height<=480]+bestaudio/best',
            '360p': 'bestvideo[height<=360]+bestaudio/best',
        }
        
        if download_type == 'video':
            format_str = quality_map.get(quality, 'bestvideo[height<=1080]+bestaudio/best')
            ydl_opts = {
                'format': format_str,
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'merge_output_format': 'mp4',
                'progress_hooks': [lambda d: progress_hook(d, job_id)],
            }
        else:  # audio
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'progress_hooks': [lambda d: progress_hook(d, job_id)],
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown')
            
            download_jobs[job_id]['status'] = 'finished'
            download_jobs[job_id]['message'] = f'Successfully downloaded: {title}'
            
    except Exception as e:
        download_jobs[job_id]['status'] = 'error'
        download_jobs[job_id]['message'] = str(e)

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
    download_type = data.get('type')
    quality = data.get('quality', '1080p')
    
    if not url:
        return jsonify({'success': False, 'message': 'URL required!'})
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job
    download_jobs[job_id] = {
        'status': 'starting',
        'percent': 0,
        'speed': 'Initializing...',
        'eta': 'Calculating...',
        'filename': 'Preparing...',
        'total_size': 'Calculating...'
    }
    
    # Start download in background thread
    thread = threading.Thread(target=download_video, args=(url, download_type, quality, job_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'job_id': job_id})

@app.route('/progress/<job_id>')
def progress(job_id):
    """Get download progress"""
    if job_id in download_jobs:
        return jsonify(download_jobs[job_id])
    else:
        return jsonify({'status': 'error', 'message': 'Job not found'})

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)