"""
Flask web server for Song Detector.
Displays recently identified songs in a web interface.
"""

from flask import Flask, render_template, jsonify
from datetime import datetime
import threading
import os
import json
from audio_capture import AudioCapture
from song_identifier import SongIdentifier

app = Flask(__name__)

# Configuration
CHUNK_DURATION = 10  # seconds - shorter chunks catch song changes faster
MAX_SONGS = 50  # Only for in-memory display, JSON stores all history
SAMPLE_RATE = 44100
PORT = 5000
SONGS_JSON_FILE = 'songs_history.json'  # Persistent storage file

# Thread-safe storage for identified songs
songs_lock = threading.Lock()
identified_songs = []

# Global instances
audio_capture = None
song_identifier = None


def is_same_song(song1, song2):
    """
    Check if two songs are the same based on title and artist.
    
    Args:
        song1: First song dict
        song2: Second song dict
        
    Returns:
        True if songs are the same, False otherwise
    """
    if not song1 or not song2:
        return False
    
    # Normalize strings for comparison (case-insensitive, strip whitespace)
    title1 = song1.get('title', '').strip().lower()
    title2 = song2.get('title', '').strip().lower()
    artist1 = song1.get('artist', '').strip().lower()
    artist2 = song2.get('artist', '').strip().lower()
    
    return title1 == title2 and artist1 == artist2


def get_last_song_from_json():
    """
    Get the most recent song from the JSON file.
    
    Returns:
        Dict of the last song, or None if file doesn't exist or is empty
    """
    if not os.path.exists(SONGS_JSON_FILE):
        return None
    
    try:
        with open(SONGS_JSON_FILE, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
            if songs_data and len(songs_data) > 0:
                # Songs are stored newest first, so first item is most recent
                return songs_data[0]
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not read JSON file to check for duplicates: {e}")
    
    return None


def save_song_to_json(song_info):
    """
    Append a single song to the JSON file.
    Thread-safe: should be called with songs_lock held.
    
    Args:
        song_info: Song dictionary to save
    """
    try:
        # Load existing songs
        existing_songs = []
        if os.path.exists(SONGS_JSON_FILE):
            try:
                with open(SONGS_JSON_FILE, 'r', encoding='utf-8') as f:
                    existing_songs = json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"Warning: Could not read existing JSON file. Starting fresh.")
                existing_songs = []
        
        # Convert song to JSON-serializable format
        song_copy = song_info.copy()
        if song_copy.get('timestamp'):
            if isinstance(song_copy['timestamp'], datetime):
                song_copy['timestamp'] = song_copy['timestamp'].isoformat()
        song_copy.pop('audio_file', None)  # Don't save temporary audio file paths
        
        # Add to beginning (newest first)
        existing_songs.insert(0, song_copy)
        
        # Write to file atomically
        temp_file = SONGS_JSON_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(existing_songs, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        os.replace(temp_file, SONGS_JSON_FILE)
        
    except Exception as e:
        print(f"Error saving song to JSON: {e}")


def process_audio_chunk(audio_file_path):
    """
    Process an audio chunk: identify song and add to list.
    Called by audio capture callback.
    
    Args:
        audio_file_path: Path to the audio file to process
    """
    global identified_songs
    
    # Check if file exists
    if not os.path.exists(audio_file_path):
        print(f"Warning: Audio file not found: {audio_file_path}")
        return
    
    try:
        # Identify the song using Shazamio
        song_info = song_identifier.identify_song_sync(audio_file_path)
        
        if song_info:
            # Check if this is the same song as the last one in JSON file
            last_song = get_last_song_from_json()
            if last_song and is_same_song(song_info, last_song):
                print(f"⊘ Skipping duplicate: '{song_info['title']}' by {song_info['artist']} (still playing)")
                # Clean up audio file since we're not using it
                if os.path.exists(audio_file_path):
                    try:
                        os.remove(audio_file_path)
                    except Exception as e:
                        print(f"Warning: Could not remove audio file: {e}")
                return
            
            # Add timestamp
            song_info['timestamp'] = datetime.now()
            
            # Add to list (thread-safe)
            with songs_lock:
                # Also check against in-memory list to avoid duplicates there
                if len(identified_songs) > 0:
                    last_in_memory = identified_songs[0]
                    if is_same_song(song_info, last_in_memory):
                        print(f"⊘ Skipping duplicate: '{song_info['title']}' by {song_info['artist']} (still in memory)")
                        # Clean up audio file
                        if os.path.exists(audio_file_path):
                            try:
                                os.remove(audio_file_path)
                            except Exception as e:
                                print(f"Warning: Could not remove audio file: {e}")
                        return
                
                identified_songs.insert(0, song_info)  # Add to beginning (newest first)
                
                # Keep only last MAX_SONGS
                if len(identified_songs) > MAX_SONGS:
                    # Remove oldest song
                    old_song = identified_songs.pop()
                    # Clean up old audio file
                    if os.path.exists(old_song.get('audio_file', '')):
                        try:
                            os.remove(old_song['audio_file'])
                        except Exception as e:
                            print(f"Warning: Could not remove old audio file: {e}")
                
                # Save to JSON file
                save_song_to_json(song_info)
                            
            print(f"✓ Identified: '{song_info['title']}' by {song_info['artist']}")
        else:
            # Song not identified - clean up audio file
            print(f"Could not identify song from: {audio_file_path}")
            if os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                except Exception as e:
                    print(f"Warning: Could not remove audio file: {e}")
                    
    except Exception as e:
        print(f"Error processing audio chunk: {e}")
        # Clean up audio file on error
        if os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
            except:
                pass


@app.route('/')
def index():
    """Main web interface route."""
    # Get songs from storage (thread-safe)
    with songs_lock:
        songs = identified_songs.copy()  # Make a copy to avoid holding lock during render
    
    return render_template('index.html', songs=songs)


@app.route('/api/songs')
def api_songs():
    """JSON API endpoint for recent songs."""
    # Get songs from storage (thread-safe)
    with songs_lock:
        songs = identified_songs.copy()
    
    # Convert datetime objects to ISO format strings for JSON serialization
    songs_json = []
    for song in songs:
        song_copy = song.copy()
        if song_copy.get('timestamp'):
            song_copy['timestamp'] = song_copy['timestamp'].isoformat()
        songs_json.append(song_copy)
    
    return jsonify(songs_json)


@app.route('/api/songs/all')
def api_songs_all():
    """JSON API endpoint for all songs from JSON history."""
    try:
        if not os.path.exists(SONGS_JSON_FILE):
            return jsonify([])
        
        with open(SONGS_JSON_FILE, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        
        # Return all songs (they're already in JSON format with ISO timestamps)
        return jsonify(songs_data)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading full song history: {e}")
        return jsonify([])


def start_audio_capture():
    """Start the audio capture service."""
    global audio_capture, song_identifier
    
    try:
        # Initialize song identifier
        song_identifier = SongIdentifier()
        print("Song identifier initialized")
        
        # Initialize audio capture
        audio_capture = AudioCapture(
            chunk_duration=CHUNK_DURATION,
            sample_rate=SAMPLE_RATE
            ,chunk_size=512
        )
        
        # Start audio capture with callback function
        audio_capture.start(callback=process_audio_chunk)
        print(f"Audio capture started (chunks of {CHUNK_DURATION} seconds)")
        
    except Exception as e:
        print(f"Error starting audio capture: {e}")
        raise


if __name__ == '__main__':
    print("=" * 60)
    print("Starting Song Detector for Raspberry Pi Zero 2")
    print("=" * 60)
    print(f"Web interface will be available at http://0.0.0.0:{PORT}")
    print(f"Configuration: {CHUNK_DURATION}s chunks, {SAMPLE_RATE}Hz, max {MAX_SONGS} songs")
    print()
    
    # Start audio capture in background
    try:
        start_audio_capture()
    except Exception as e:
        print(f"Failed to initialize audio capture: {e}")
        print("Please check your USB microphone connection and try again.")
        exit(1)
    
    try:
        # Run Flask app
        print("Starting Flask web server...")
        app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        if audio_capture:
            audio_capture.stop()
        print("Goodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
        if audio_capture:
            audio_capture.stop()
        raise
