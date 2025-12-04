# Screensaver Video Auto-Update System

## Overview
Automatic screensaver video management system that fetches, downloads, and updates videos from the API based on machine ID.

## Features
- ✅ Automatic video checking on app startup
- ✅ Runs in background thread (non-blocking)
- ✅ Smart caching - only downloads when video ID changes
- ✅ Falls back to existing video if download fails
- ✅ Machine ID automatically read from app config
- ✅ Video stored in `assets/screensaver_current.mp4`

## How It Works

### 1. **API Call**
```
GET https://kulhad.vercel.app/api/machines/{machineId}/videos
```

### 2. **Response Format**
```json
{
  "code": 200,
  "message": "Videos retrieved successfully",
  "machineId": "KH-01",
  "totalVideos": 1,
  "videos": [{
    "videoId": "ms71qhcpj7y5cz1ndn0vak13qd7wb7z6",
    "title": "file_example_MP4_480_1_5MG.mp4",
    "videoUrl": "https://silent-sockeye-142.convex.cloud/api/storage/...",
    "fileSize": 1570024
  }]
}
```

### 3. **Update Logic**
1. Fetch video info from API
2. Compare `videoId` with cached ID
3. If different → Download new video → **Delete all old videos**
4. If same → Use existing cached video → **Clean up any orphaned old videos**
5. Update screensaver page with video path

**Cleanup Behavior:**
- ✅ All old videos are automatically deleted
- ✅ Only the current video is kept
- ✅ Prevents disk space waste
- ✅ Happens on every app startup

## File Structure

```
assets/
├── screensaver_cache.json        # Cached video metadata
├── screensaver_current.mp4       # Current active video (symlink/copy)
└── screensaver_videos/
    └── {videoId}.mp4             # Downloaded videos by ID
```

## Implementation

### Main Components

#### 1. `utils/screensaver_manager.py`
- `ScreensaverVideoManager` class
- Handles API calls, downloading, and caching
- Methods:
  - `fetch_video_info()` - Get video info from API
  - `download_video()` - Download video from URL
  - `check_and_update_video()` - Check and update if needed
  - `update_video_async()` - Update in background thread

#### 2. Integration in `main_app.py`
```python
# Initialize manager
self.screensaver_video_manager = ScreensaverVideoManager(
    machine_id=self.MACHINE_ID
)

# Update video in background
self.screensaver_video_manager.update_video_async(
    callback=on_video_ready
)
```

## Configuration

### Machine ID
Set in `main_app.py`:
```python
self.MACHINE_ID = "KH-01"
```

### API Base URL
Default: `https://kulhad.vercel.app`

Can be changed when initializing:
```python
manager = ScreensaverVideoManager(
    machine_id="KH-01",
    api_base_url="https://your-api.com"
)
```

## Testing

Run test script:
```bash
python3 test_screensaver_manager.py
```

Expected output:
- ✅ Fetches video info from API
- ✅ Downloads video if new (or uses cached)
- ✅ Creates `assets/screensaver_current.mp4`
- ✅ Calls callback with video path

## Usage Flow

### First Run
1. App starts
2. Manager checks API for videos
3. No cached video → Downloads new video
4. Saves to `assets/screensaver_videos/{videoId}.mp4`
5. Creates `assets/screensaver_current.mp4`
6. Updates screensaver page
7. Saves cache with video ID

### Subsequent Runs (Same Video)
1. App starts
2. Manager checks API for videos
3. Video ID matches cache → Skip download
4. Uses existing `assets/screensaver_current.mp4`
5. Updates screensaver page

### When Video Changes
1. App starts
2. Manager checks API for videos
3. New video ID detected
4. Downloads new video
5. Replaces `assets/screensaver_current.mp4`
6. Updates cache with new video ID
7. Old video remains in `screensaver_videos/` folder

## Error Handling

### API Call Fails
- Uses existing cached video
- Logs warning message

### Download Fails
- Uses existing cached video
- Logs error message

### No Video Available
- Logs warning
- Screensaver shows placeholder

## Benefits

1. **Centralized Management** - Update videos for all machines from one API
2. **Automatic Updates** - No manual intervention needed
3. **Bandwidth Efficient** - Only downloads when changed
4. **Non-Blocking** - Runs in background thread
5. **Fault Tolerant** - Falls back to existing videos on errors

## Future Enhancements

- [ ] Video format validation
- [ ] Video compression for faster downloads
- [ ] Multiple videos rotation
- [ ] Scheduled updates (check periodically)
- [ ] Video quality selection
