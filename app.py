"""
Flask web server for Song Detector.
Displays recently identified songs in a web interface.
"""

from flask import Flask, render_template, jsonify
from datetime import datetime
import threading
import os
from audio_capture import AudioCapture
from song_identifier import SongIdentifier

app = Flask(__name__)

# Configuration
CHUNK_DURATION = 10  # seconds
MAX_SONGS = 50
SAMPLE_RATE = 44100
PORT = 5000

# Thread-safe storage for identified songs
songs_lock = threading.Lock()
identified_songs = []

# Global instances
audio_capture = None
song_identifier = None


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
            # Add timestamp
            song_info['timestamp'] = datetime.now()
            
            # Add to list (thread-safe)
            with songs_lock:
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
