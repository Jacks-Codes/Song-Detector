"""
Song identification module using Shazamio.
Identifies songs from audio files and extracts metadata.
"""

import asyncio
from shazamio import Shazam


class SongIdentifier:
    """Identifies songs from audio files using Shazamio."""
    
    def __init__(self):
        """Initialize Shazamio client."""
        self.shazam = Shazam()
        
    async def identify_song(self, audio_file_path):
        """
        Identify a song from an audio file.
        
        Args:
            audio_file_path: Path to the audio file (WAV format)
            
        Returns:
            Dictionary with song information, or None if not identified
            Format: {
                'title': str,
                'artist': str,
                'album': str,
                'timestamp': datetime,
                'audio_file': str
            }
        """
        try:
            # Use Shazamio to recognize the song
            result = await self.shazam.recognize_song(audio_file_path)
            
            # Check if we got a valid result with track information
            if result and 'track' in result:
                track = result['track']
                
                # Extract basic song information
                song_info = {
                    'title': track.get('title', 'Unknown'),
                    'artist': track.get('subtitle', 'Unknown Artist'),
                    'album': 'Unknown Album',  # Will try to find below
                    'artwork': None,  # Album artwork URL
                    'timestamp': None,  # Will be set by caller in app.py
                    'audio_file': audio_file_path
                }
                
                # Extract album artwork - check multiple possible locations
                if 'images' in track:
                    # Try different image size keys
                    for size_key in ['coverart', 'coverarthq', 'background']:
                        if size_key in track['images']:
                            song_info['artwork'] = track['images'][size_key]
                            break
                
                # If no artwork found, try sections
                if not song_info['artwork'] and 'sections' in track:
                    for section in track['sections']:
                        if 'image' in section:
                            song_info['artwork'] = section['image']
                            break
                        if 'images' in section:
                            for img_key in ['coverart', 'coverarthq']:
                                if img_key in section['images']:
                                    song_info['artwork'] = section['images'][img_key]
                                    break
                            if song_info['artwork']:
                                break
                
                # Try to extract album information from metadata sections
                # Shazam API structure can vary, so we check multiple places
                if 'sections' in track:
                    for section in track['sections']:
                        if 'metadata' in section:
                            for metadata in section['metadata']:
                                # Look for album metadata
                                if metadata.get('title') == 'Album':
                                    song_info['album'] = metadata.get('text', 'Unknown Album')
                                    break
                        # Break outer loop if we found the album
                        if song_info['album'] != 'Unknown Album':
                            break
                
                return song_info
            else:
                # Song not identified
                return None
                
        except Exception as e:
            print(f"Error identifying song: {e}")
            return None
            
    def identify_song_sync(self, audio_file_path):
        """
        Synchronous wrapper for identify_song.
        This allows us to call the async identify_song method from synchronous code.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Dictionary with song information, or None if not identified
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If there's no event loop running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async method and return the result
        return loop.run_until_complete(self.identify_song(audio_file_path))
