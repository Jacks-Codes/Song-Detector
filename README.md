# Song Detector for Raspberry Pi Zero 2

A song identification system that captures audio from a USB microphone, identifies songs using Shazamio, and displays the last 50 identified songs in a web interface.

## Hardware Requirements

- Raspberry Pi Zero 2 W
- USB Microphone

## Transferring Files to Raspberry Pi

You have several options to transfer the project files to your Raspberry Pi:

### Option 1: Using SCP (Recommended)

From your Mac, transfer all files to the Raspberry Pi:

```bash
# Replace 'pi' with your Pi username and 'raspberrypi.local' with your Pi's hostname or IP
scp -r "/Users/jack/Song Detector" pi@raspberrypi.local:~/

# Or if you know the IP address:
scp -r "/Users/jack/Song Detector" pi@192.168.1.XXX:~/
```

Then SSH into your Pi and navigate to the directory:

```bash
ssh pi@raspberrypi.local
cd ~/Song\ Detector
```

### Option 2: Using Git

If you have Git set up:

1. Create a repository and push your code:
```bash
cd "/Users/jack/Song Detector"
git init
git add .
git commit -m "Initial commit"
# Push to GitHub/GitLab/etc.
```

2. On your Raspberry Pi:
```bash
git clone <your-repo-url>
cd Song\ Detector
```

### Option 3: Using USB Drive

1. Copy the entire project folder to a USB drive
2. Plug the USB drive into your Raspberry Pi
3. Copy files from USB to Pi:
```bash
cp -r /media/pi/USBDRIVE/Song\ Detector ~/
cd ~/Song\ Detector
```

### Option 4: Using SFTP (GUI)

Use an SFTP client like FileZilla or Cyberduck:
- Host: `raspberrypi.local` or your Pi's IP
- Username: `pi` (or your username)
- Password: your Pi password
- Port: `22`

## Setup Instructions

### 1. Install System Dependencies

On your Raspberry Pi, install the required system packages:

```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install python3 python3-pip portaudio19-dev python3-pyaudio
```

### 2. Connect to Network

Make sure your Raspberry Pi Zero 2 W is connected to WiFi:

```bash
# Check WiFi connection
iwconfig

# Or check IP address
hostname -I
```

The Flask server is configured to be accessible from any device on your local network.

### 3. Configure USB Microphone

Connect your USB microphone and verify it's recognized:

```bash
arecord -l
```

You should see your USB microphone listed. Note the card number and device number (e.g., `card 1, device 0`).

Test recording:

```bash
arecord -D plughw:1,0 -f cd -d 5 test.wav
aplay test.wav
```

Adjust the device identifier (`plughw:1,0`) if your microphone uses a different card/device number.

### 4. Install Python Dependencies

Navigate to the project directory and install Python packages:

```bash
cd ~/Song\ Detector
pip3 install -r requirements.txt
```

**Note:** If you encounter permission errors, you may need to use `pip3 install --user -r requirements.txt` or create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### 5. Run the Application

Start the song detector:

```bash
python3 app.py
```

The application will:
- Start capturing audio from the USB microphone in 10-second chunks
- Identify songs using Shazamio
- Start a web server on port 5000

**Note:** The server runs on `0.0.0.0:5000`, making it accessible from any device on your local network.

### 6. Access the Web Interface

Open a web browser on any device connected to the same network and navigate to:

```
http://<Raspberry_Pi_IP>:5000
```

To find your Raspberry Pi's IP address:

```bash
hostname -I
```

### 7. Run on Startup (Optional)

To make the application start automatically when the Raspberry Pi boots:

1. Create a systemd service file:
```bash
sudo nano /etc/systemd/system/song-detector.service
```

2. Add the following content (adjust paths as needed):
```ini
[Unit]
Description=Song Detector
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Song Detector
ExecStart=/usr/bin/python3 /home/pi/Song Detector/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable song-detector.service
sudo systemctl start song-detector.service
```

4. Check status:
```bash
sudo systemctl status song-detector.service
```

## Configuration

You can modify the following settings in `app.py`:

- `CHUNK_DURATION`: Duration of audio chunks in seconds (default: 10)
- `MAX_SONGS`: Maximum number of songs to store (default: 50)
- `SAMPLE_RATE`: Audio sample rate in Hz (default: 16000)
- `PORT`: Web server port (default: 5000)

## Troubleshooting

### USB Microphone Not Detected

- Check USB connection
- Run `arecord -l` to verify detection
- Try a different USB port
- Check microphone permissions

### Audio Quality Issues

- Ensure microphone is positioned correctly
- Check for background noise
- Verify sample rate settings

### Song Identification Fails

- Ensure internet connection is active (Shazamio requires internet)
- Check audio quality and volume levels
- Verify microphone is capturing audio correctly

## Future Enhancements

- Migrate to SQLite database for persistent storage
- Add user authentication
- Implement song history search
- Add statistics and analytics

