"""
Screensaver Video Manager
Handles checking and downloading screensaver videos from the API
"""

import requests
import os
import json
import threading
from datetime import datetime


class ScreensaverVideoManager:
    """Manages screensaver video updates from API"""
    
    def __init__(self, machine_id, api_base_url="https://kulhad.vercel.app"):
        self.machine_id = machine_id
        self.api_base_url = api_base_url
        self.video_cache_file = os.path.join('assets', 'screensaver_cache.json')
        self.videos_dir = os.path.join('assets', 'screensaver_videos')
        self.current_video_path = os.path.join('assets', 'screensaver_current.mp4')
        
        # Ensure directories exist
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs('assets', exist_ok=True)
        
        # Load cached video info
        self.cached_video_info = self._load_cache()
    
    def _load_cache(self):
        """Load cached video information"""
        if os.path.exists(self.video_cache_file):
            try:
                with open(self.video_cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load video cache: {e}")
                return {}
        return {}
    
    def _save_cache(self, video_info):
        """Save video information to cache"""
        try:
            with open(self.video_cache_file, 'w') as f:
                json.dump(video_info, f, indent=2)
            print(f"✓ Video cache saved")
        except Exception as e:
            print(f"⚠️ Failed to save video cache: {e}")
    
    def fetch_video_info(self):
        """Fetch video information from API"""
        try:
            url = f"{self.api_base_url}/api/machines/{self.machine_id}/videos"
            print(f"🎬 Fetching video info from: {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('code') == 200 and data.get('videos'):
                videos = data.get('videos', [])
                if videos:
                    # Get the first video
                    video = videos[0]
                    print(f"✓ Found video: {video.get('title')}")
                    return video
                else:
                    print("⚠️ No videos available for this machine")
                    return None
            else:
                print(f"⚠️ API returned no videos: {data}")
                return None
                
        except requests.RequestException as e:
            print(f"❌ Failed to fetch video info: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error fetching video info: {e}")
            return None
    
    def download_video(self, video_url, video_id):
        """Download video from URL"""
        try:
            print(f"📥 Downloading video from: {video_url}")
            
            # Create temporary download path
            temp_video_path = os.path.join(self.videos_dir, f"{video_id}_temp.mp4")
            final_video_path = os.path.join(self.videos_dir, f"{video_id}.mp4")
            
            # Download with progress
            response = requests.get(video_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(temp_video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Print progress every 10%
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            if int(progress) % 10 == 0:
                                print(f"📥 Download progress: {int(progress)}%")
            
            # Move to final location
            if os.path.exists(final_video_path):
                os.remove(final_video_path)
            os.rename(temp_video_path, final_video_path)
            
            # Create/update symlink to current video
            if os.path.exists(self.current_video_path):
                os.remove(self.current_video_path)
            
            # Copy file instead of symlink for better compatibility
            import shutil
            shutil.copy2(final_video_path, self.current_video_path)
            
            print(f"✓ Video downloaded successfully: {final_video_path}")
            print(f"✓ Current video updated: {self.current_video_path}")
            return final_video_path
            
        except requests.RequestException as e:
            print(f"❌ Failed to download video: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error downloading video: {e}")
            return None
    
    def check_and_update_video(self, callback=None):
        """Check if video needs to be updated and download if necessary"""
        print("\n" + "="*60)
        print(f"🎬 Checking for screensaver video updates...")
        print(f"   Machine ID: {self.machine_id}")
        print("="*60)
        
        # Fetch latest video info
        video_info = self.fetch_video_info()
        
        if not video_info:
            print("⚠️ No video info available, using existing video if available")
            
            # Use existing video if available
            if os.path.exists(self.current_video_path):
                print(f"✓ Using existing video: {self.current_video_path}")
                if callback:
                    callback(self.current_video_path)
            else:
                print("⚠️ No screensaver video available")
            return
        
        current_video_id = video_info.get('videoId')
        video_url = video_info.get('videoUrl')
        
        # Check if we need to download
        cached_video_id = self.cached_video_info.get('videoId')
        
        if current_video_id == cached_video_id:
            print(f"✓ Video is up to date (ID: {current_video_id})")
            
            # Check if file exists
            video_path = os.path.join(self.videos_dir, f"{current_video_id}.mp4")
            if os.path.exists(video_path):
                print(f"✓ Using cached video: {video_path}")
                
                # Cleanup old videos even when using cached version
                self.cleanup_old_videos(current_video_id)
                
                # Ensure current video link is up to date
                if not os.path.exists(self.current_video_path):
                    import shutil
                    shutil.copy2(video_path, self.current_video_path)
                    print(f"✓ Current video symlink created")
                
                if callback:
                    callback(self.current_video_path)
            else:
                print(f"⚠️ Cached video file not found, downloading...")
                self._download_and_cache(video_info, video_url, current_video_id, callback)
        else:
            print(f"🆕 New video available!")
            print(f"   Old ID: {cached_video_id}")
            print(f"   New ID: {current_video_id}")
            self._download_and_cache(video_info, video_url, current_video_id, callback)
    
    def cleanup_old_videos(self, current_video_id):
        """Clean up all old video files except the current one"""
        try:
            if not os.path.exists(self.videos_dir):
                return
            
            # Get all video files in the directory
            video_files = [f for f in os.listdir(self.videos_dir) if f.endswith('.mp4')]
            current_filename = f"{current_video_id}.mp4"
            
            deleted_count = 0
            for video_file in video_files:
                if video_file != current_filename:
                    old_path = os.path.join(self.videos_dir, video_file)
                    try:
                        os.remove(old_path)
                        deleted_count += 1
                        print(f"🗑️ Deleted old video: {video_file}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete {video_file}: {e}")
            
            if deleted_count > 0:
                print(f"✓ Cleaned up {deleted_count} old video(s)")
            else:
                print(f"✓ No old videos to clean up")
                
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")
    
    def _download_and_cache(self, video_info, video_url, video_id, callback=None):
        """Download video and update cache"""
        # Download new video
        video_path = self.download_video(video_url, video_id)
        
        if video_path:
            # Clean up all old videos (more thorough than just deleting one)
            self.cleanup_old_videos(video_id)
            
            # Update cache
            self.cached_video_info = {
                'videoId': video_id,
                'title': video_info.get('title'),
                'videoUrl': video_url,
                'downloadedAt': datetime.now().isoformat()
            }
            self._save_cache(self.cached_video_info)
            
            print(f"✓ Screensaver video updated successfully")
            
            if callback:
                callback(self.current_video_path)
        else:
            print(f"❌ Failed to download video")
            
            # Use existing video if download failed
            if os.path.exists(self.current_video_path):
                print(f"⚠️ Using existing video as fallback")
                if callback:
                    callback(self.current_video_path)
    
    def update_video_async(self, callback=None):
        """Update video in a background thread"""
        print("🧵 Starting video update in background thread...")
        
        def update_thread():
            try:
                self.check_and_update_video(callback)
            except Exception as e:
                print(f"❌ Error in video update thread: {e}")
        
        thread = threading.Thread(target=update_thread, daemon=True)
        thread.start()
        print(f"✓ Video update thread started")


# Usage example:
if __name__ == "__main__":
    # Test the video manager
    manager = ScreensaverVideoManager(machine_id="KH-01")
    
    def on_video_ready(video_path):
        print(f"\n🎉 Video ready: {video_path}")
    
    manager.check_and_update_video(callback=on_video_ready)
