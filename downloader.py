# SABSE PEHLE yt-dlp import karein
import yt_dlp

# YouTube video download karne ka function
def download_video(url):
    print("Download shuru ho raha hai...")
    
    # Settings (options)
    settings = {
        'format': 'best',  # Best quality download hogi
        'outtmpl': '%(title)s.%(ext)s',  # Video ka naam kya hoga
    }
    
    # Download karo
    with yt_dlp.YoutubeDL(settings) as downloader:
        downloader.download([url])
    
    print("Download complete! ✅")

# Program yahan se start hoga
print("=" * 50)
print("YouTube Video Downloader")
print("=" * 50)

# User se YouTube link lein
video_link = input("\nYouTube video ka link paste karein: ")

# Download function ko call karein
download_video(video_link)

print("\nVideo download ho gaya! Same folder mein check karein 😊")