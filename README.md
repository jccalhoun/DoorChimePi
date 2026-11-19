# DoorChimePi
# 🚪🔔🥧 Raspberry Pi Door Chime System

A production-ready door monitoring system that plays audio alerts and logs events when a magnetic reed switch detects door movement. Built with modern Python practices, featuring robust error handling, automatic log rotation, and intelligent cooldown logic.

## 🤖 AI Attribution

This project was developed through an iterative collaboration between a human developer and multiple AI models:
- **Claude**: Code quality, type hinting, error handling, and hardware logic documentation
- **Gemini**: Core architecture, `pathlib` integration, and performance optimizations
- **DeepSeek**: Type hints, f-string consistency, and best practice recommendations

The result is a well-tested, production-ready script that follows modern Python standards.

---

## 📋 Features

### Core Functionality
- **Real-time Monitoring**: Event-driven GPIO handling via `gpiozero`
- **Intelligent Audio**: `pygame.mixer` with optimized buffer settings to reduce latency on Raspberry Pi hardware
- **Configurable Behavior**: Optional chime on door close, adjustable cooldown periods, and debug mode
- **Gate-Left-Open Reminder**: Re-chimes every `GATE_OPEN_REMINDER` seconds while the gate stays open
- **Web Page**: Check gate status and recent events, test the chime, and pick a different sound from any device on your network

### Data Management
- **Automatic Log Rotation**: Prevents SD card exhaustion by capping log sizes at 10MB (configurable)
- **High-Performance Logging**: Uses efficient ASCII encoding for cross-platform compatibility
- **Timestamped Events**: Every door open/close logged with precise timestamps

### Resilience
- **Hardware Debouncing**: `bounce_time` parameter prevents false triggers from electrical noise
- **Software Cooldown**: Prevents "chime fatigue" from vibrating doors or rapid open/close cycles
- **Graceful Error Handling**: Comprehensive exception handling with helpful error messages

---

## 🛠 Hardware Setup

| Component | Specification |
|-----------|--------------|
| **Raspberry Pi** | Any model with GPIO (Pi 3, 4, 5, or Zero) |
| **Reed Switch** | **Normally Closed (NC)** magnetic sensor |
| **Magnet** | Align within 1–2cm of the switch when door is closed |
| **Audio** | Bluetooth speaker, 3.5mm jack, HDMI, or USB audio device |

### Wiring Diagram

```
Reed Switch Pin 1 → GPIO 17 (Pin 11, BCM numbering)
Reed Switch Pin 2 → GND (Pin 6 or any GND pin)
```

**No external resistor needed** - the script uses the Raspberry Pi's internal pull-up resistor.

### Installation Tips
- Mount the reed switch on the **door frame** (stationary)
- Mount the magnet on the **door** (moving part)
- Align within 1-2cm when door is closed
- Test with a handheld magnet before permanent mounting

> **⚠️ Important**: This script is designed for **Normally Closed (NC)** reed switches. If you have a Normally Open (NO) switch, swap the `when_pressed` and `when_released` event handlers in the code and set GATE_OPEN_REMINDER = 0.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install python3-pygame python3-gpiozero python3-flask
```

`python3-flask` is only needed for the web page. Without it the chime still runs and prints a warning.

### 2. Download the Script

```bash
git clone https://github.com/jccalhoun/DoorChimePi.git
cd DoorChimePi
```

### 3. Add Your Sound File

Place a WAV file named `doorbell.wav` in the same directory as the script. You can add more `.wav` files to the same folder and switch between them from the web page.

**Finding doorbell sounds:**
- [Freesound.org](https://freesound.org/) - Free sound effects library
- [Zapsplat](https://www.zapsplat.com/) - Royalty-free sounds
- Record your own!

### 4. Run the System

```bash
python3 door_chime.py
```

Press `Ctrl+C` to stop.

To try it on a computer with no GPIO hardware, run `python3 door_chime.py --simulate` and type `t` + Enter to open or close the simulated gate.

---

## ⚙️ Configuration

Edit the configuration section at the top of `door_chime.py`:

```python
COOLDOWN = 3                   # Minimum seconds between chimes
REED_PIN = 17                  # GPIO pin number (BCM)
MAX_LOG_SIZE_MB = 10           # Max log size before rotation
CHIME_ON_CLOSE = False         # Set True to also chime when door closes
GATE_OPEN_REMINDER = 120       # Re-chime every N seconds while gate stays open (0 = off)
WEB_PORT = 8080                # Status web page port (0 = off)
VOLUME = 0.7                   # Chime volume, 0.0 to 1.0
DEBUG_MODE = False             # Set True for verbose debugging
```

---

## 🌐 Web Page

While the script is running, open `http://<pi-address>:8080` from any phone or computer on the same network. Find the Pi's address with `hostname -I`.

The page shows:

- **Gate status**: open or closed, and when it last opened
- **Recent events**: the last 20 lines of `door_log.txt`, newest first
- **Test chime**: plays the current sound
- **Chime sound**: lists the `.wav` files in the script's folder; choosing one plays it once and saves the choice to `chime_settings.json` so it survives a restart

The page refreshes itself every 15 seconds.

> **⚠️ Note**: The page has no password, so anyone on your network can use it. Do not forward this port through your router.

---

## 🔄 Deployment: Run on Boot

To have the chime start by itself after a reboot or power outage, with no desktop running, set it up as a systemd **user** service. A user service runs inside your login session, which is where Bluetooth audio lives.

### 1. Boot to the Console with Auto-Login

```bash
sudo raspi-config
```

Choose **System Options → Boot / Auto Login → Console Autologin**. This logs you in at boot without starting a desktop.

### 2. Set Up the Bluetooth Speaker (skip for wired audio)

Pair and connect the speaker once, then trust it so it reconnects on its own:

```bash
bluetoothctl trust <speaker MAC address>
```

### 3. Create the Service File

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/doorchime.service
```

Paste the following, replacing `YOUR_USER` and the folder with your own:

```ini
[Unit]
Description=Door Chime
After=pipewire.service wireplumber.service

[Service]
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=/home/YOUR_USER/DoorChimePi
ExecStart=/usr/bin/python3 /home/YOUR_USER/DoorChimePi/door_chime.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

### 4. Enable and Start

```bash
systemctl --user daemon-reload
systemctl --user enable --now doorchime
```

### 5. Verify and Monitor

Check status:
```bash
systemctl --user status doorchime
```

View live logs:
```bash
journalctl --user -u doorchime -f
```

Stop the service:
```bash
systemctl --user stop doorchime
```

---

## 🔧 Troubleshooting

### No Sound Plays
- **Check sound file**: Verify `doorbell.wav` exists in the correct directory
- **Test audio output**: `speaker-test -t wav`
- **Check volume**: Run `alsamixer` and ensure volume is up
- **Enable debug mode**: Set `DEBUG_MODE = True` in the script
- **Bluetooth speaker turned itself off**: Many battery speakers power down after 10–20 minutes of silence. Use a mains-powered speaker or one with auto-off disabled
- **Start of the chime is cut off**: Some Bluetooth speakers take a moment to wake up. Use a `.wav` with a short silent lead-in
- **Works from a terminal but not at boot**: Check that Console Autologin is on and the speaker is trusted (see Deployment)

### Web Page Won't Load
- Confirm the address with `hostname -I` and include the port: `http://<pi-address>:8080`
- Check the logs for a Flask warning: `journalctl --user -u doorchime -n 50`
- Install Flask if it is missing: `sudo apt install python3-flask`
- If another program uses port 8080, change `WEB_PORT`

### Chime Plays at Wrong Time
- **Verify switch type**: Ensure you have a Normally Closed (NC) switch
- **Check alignment**: Magnet should be within 1-2cm when door is closed
- **Test with magnet**: Move a handheld magnet near the switch to test
- **Wrong switch type?** If you have NO instead of NC, swap the event handlers and set `GATE_OPEN_REMINDER = 0`

### GPIO Permission Errors
```bash
sudo usermod -a -G gpio $USER
sudo reboot
```

### Service Won't Start
- Check file paths in the service file match your installation
- Verify Python path: `which python3`
- Check logs: `journalctl --user -u doorchime -n 50`

### Log File Issues
- Ensure write permissions in the script directory
- Log automatically rotates at `MAX_LOG_SIZE_MB` (default: 10MB)
- Old logs saved as `door_log.txt.old`

---

## 📁 File Structure

```
DoorChimePi/
├── door_chime.py          # Main script
├── doorbell.wav           # Default sound file (you provide this)
├── *.wav                  # Any extra sounds to pick from the web page
├── chime_settings.json    # Auto-generated: remembers the chosen sound
├── door_log.txt           # Auto-generated event log
├── door_log.txt.old       # Rotated log (when size exceeded)
└── README.md              # This file
```

---

## 🔍 How It Works

### Reed Switch Operation (Normally Closed)

1. **Gate Closed**: Magnet near switch → contacts open → GPIO HIGH (pulled up) → `sensor.is_pressed = False`
2. **Gate Opens**: Magnet moves away → contacts close → GPIO LOW → `when_pressed` triggered
3. **Chime Plays**: Sound plays if cooldown period has elapsed
4. **Event Logged**: Timestamp and event written to `door_log.txt`
5. **Gate Left Open**: If it stays open for `GATE_OPEN_REMINDER` seconds, `when_held` re-chimes
6. **Gate Closes**: Magnet returns → contacts open → `when_released` triggered

### Cooldown Logic

Prevents rapid repeated chimes from:
- Doors that vibrate or bounce
- Multiple people passing through quickly
- Wind or pets triggering the sensor

After a chime plays, subsequent triggers within the cooldown period are ignored (but still logged).

### Log Rotation

When `door_log.txt` exceeds `MAX_LOG_SIZE_MB`:
1. Current log renamed to `door_log.txt.old`
2. New empty `door_log.txt` created
3. Prevents SD card exhaustion on long-running installations

---

## 💻 Technical Details

- **Language**: Python 3.7+
- **GPIO Library**: gpiozero (high-level, beginner-friendly)
- **Audio**: pygame.mixer (reliable, low-latency on Raspberry Pi)
- **Web Page**: Flask, running in a background thread of the same script
- **File Handling**: pathlib (modern Python approach)
- **Type Hints**: Full type annotations for IDE support and type checking
- **Performance**: Optimized ASCII encoding for log processing

### Why These Libraries?

- **gpiozero**: Simpler and more Pythonic than RPi.GPIO, with built-in debouncing
- **pygame.mixer**: Better performance than playsound or aplay on Raspberry Pi
- **pathlib**: Modern, cross-platform file handling (Python 3.4+)

---

## 🧪 Testing

Before permanent installation:

1. **Test audio**: Run the script and verify sound plays
2. **Test sensor**: Use a handheld magnet to trigger the switch
3. **Test alignment**: Close door and verify initial state is "Closed"
4. **Test cooldown**: Open door rapidly multiple times, verify cooldown works
5. **Test logging**: Check that `door_log.txt` is being created and updated
6. **Test the web page**: Open `http://<pi-address>:8080`, press **Test chime**, and try switching sounds
7. **Test a reboot**: Restart the Pi and confirm the chime and web page come back on their own

---

## 📜 License

MIT License - Free to use and modify for personal or commercial projects.

---

## 🤝 Contributing

While this is a personal home automation project, suggestions and improvements are welcome!

- Open an issue for bug reports or feature requests
- Submit pull requests for improvements
- Share your setup and customizations!

---

## 🙏 Acknowledgments

- Built on the excellent [gpiozero](https://gpiozero.readthedocs.io/) library
- Thanks to the Raspberry Pi community for GPIO best practices
- Developed with assistance from Claude, Gemini, and DeepSeek AI models

---

## 📚 Additional Resources

- [gpiozero Documentation](https://gpiozero.readthedocs.io/)
- [Raspberry Pi GPIO Pinout](https://pinout.xyz/)
- [Reed Switch Guide](https://learn.sparkfun.com/tutorials/reed-switch-hookup-guide)
- [systemd Service Tutorial](https://www.raspberrypi.org/documentation/linux/usage/systemd.md)

---

**Happy door monitoring! 🚪✨**

*If you find this project helpful, consider starring it on GitHub!*
