"""
Audio capture module for USB microphone on Raspberry Pi.
Records audio in configurable chunks and saves as WAV files.
"""

import pyaudio
import wave
import threading
import os
import time
import tempfile
from datetime import datetime


class AudioCapture:
    """Captures audio from USB microphone in chunks."""
    
    def __init__(self, chunk_duration=10, sample_rate=16000, channels=1, chunk_size=1024):
        """
        Initialize audio capture.
        
        Args:
            chunk_duration: Duration of each audio chunk in seconds (default: 10)
            sample_rate: Sample rate in Hz (default: 16000 for Shazam compatibility)
            channels: Number of audio channels (default: 1 for mono)
            chunk_size: Buffer size for audio reading (default: 1024)
        """
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        
        # PyAudio and stream objects (initialized in start())
        self.audio = None
        self.stream = None
        
        # Threading control
        self.is_recording = False
        self.recording_thread = None
        
        # Callback function to call with each audio file path
        self.callback = None
        
    def start(self, callback=None):
        """
        Start continuous audio capture.
        
        Args:
            callback: Function to call with path to each recorded audio file
        """
        if self.is_recording:
            return  # Already recording
            
        self.callback = callback
        self.is_recording = True
        
        # Initialize PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Try to find USB microphone device
        device_index = None
        try:
            # Look for USB microphone in device list
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                # Check if it's a USB mic (name contains 'usb') and has input channels
                if 'usb' in info['name'].lower() and info['maxInputChannels'] > 0:
                    device_index = i
                    print(f"Found USB microphone: {info['name']} (device {i})")
                    break
            
            # Fall back to default input device if no USB mic found
            if device_index is None:
                default_info = self.audio.get_default_input_device_info()
                device_index = default_info['index']
                print(f"Using default input device: {default_info['name']} (device {device_index})")
        except Exception as e:
            print(f"Warning: Error detecting audio devices: {e}. Using default.")
            device_index = None  # Will use default
        
        # Open audio stream
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,  # 16-bit audio
                channels=self.channels,
                rate=self.sample_rate,
                input=True,  # This is an input stream (microphone)
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size
            )
            print(f"Audio stream opened: {self.sample_rate}Hz, {self.channels} channel(s)")
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            self.audio.terminate()
            raise
        
        # Start recording thread
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()
        print("Recording thread started")
        
    def stop(self):
        """Stop audio capture."""
        if not self.is_recording:
            return
            
        print("Stopping audio capture...")
        self.is_recording = False
        
        # Wait for recording thread to finish current chunk
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        # Close audio stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"Error closing stream: {e}")
        
        # Terminate PyAudio
        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                print(f"Error terminating PyAudio: {e}")
        
        print("Audio capture stopped")
            
    def _record_loop(self):
        """Main recording loop that captures audio chunks."""
        # Calculate how many frames we need for the desired chunk duration
        # Example: 16000 Hz * 10 seconds / 1024 frames = ~156 frames
        frames_per_chunk = int(self.sample_rate * self.chunk_duration / self.chunk_size)
        
        print(f"Recording loop started: capturing {self.chunk_duration}s chunks ({frames_per_chunk} frames each)")
        
        while self.is_recording:
            try:
                frames = []
                
                # Read audio data in small chunks until we have enough for the full duration
                for _ in range(frames_per_chunk):
                    if not self.is_recording:
                        break  # Exit if we're told to stop
                    
                    # Read a chunk of audio data
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    frames.append(data)
                
                # If we collected frames and we're still recording, save them
                if frames and self.is_recording:
                    # Save chunk to temporary WAV file
                    temp_file = self._save_chunk(frames)
                    
                    # Call callback with file path if we have one
                    if temp_file and self.callback:
                        try:
                            self.callback(temp_file)
                        except Exception as e:
                            print(f"Error in callback: {e}")
                            
            except Exception as e:
                print(f"Error in recording loop: {e}")
                if self.is_recording:
                    time.sleep(1)  # Brief pause before retrying
                    
    def _save_chunk(self, frames):
        """
        Save audio frames to a temporary WAV file.
        
        Args:
            frames: List of audio frame data (bytes)
            
        Returns:
            Path to saved WAV file, or None on error
        """
        try:
            # Create a unique temporary filename
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            temp_file = os.path.join(temp_dir, f"song_detector_{timestamp}.wav")
            
            # Open WAV file for writing
            wf = wave.open(temp_file, 'wb')
            
            # Set WAV file parameters
            wf.setnchannels(self.channels)  # Mono or stereo
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))  # 16-bit = 2 bytes
            wf.setframerate(self.sample_rate)  # Sample rate (e.g., 16000 Hz)
            
            # Write all frames to file
            wf.writeframes(b''.join(frames))
            wf.close()
            
            return temp_file
            
        except Exception as e:
            print(f"Error saving audio chunk: {e}")
            return None
