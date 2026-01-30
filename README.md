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
| **Audio** | Speaker via 3.5mm jack, HDMI, or USB audio device |

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

> **⚠️ Important**: This script is designed for **Normally Closed (NC)** reed switches. If you have a Normally Open (NO) switch, swap the `when_pressed` and `when_released` event handlers in the code.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install python3-pygame python3-gpiozero
```

### 2. Download the Script

```bash
git clone https://github.com/yourusername/raspberry-pi-door-chime.git
cd raspberry-pi-door-chime
```

### 3. Add Your Sound File

Place a WAV file named `doorbell.wav` in the same directory as the script.

**Finding doorbell sounds:**
- [Freesound.org](https://freesound.org/) - Free sound effects library
- [Zapsplat](https://www.zapsplat.com/) - Royalty-free sounds
- Record your own!

### 4. Run the System

```bash
python3 door_chime_final.py
```

Press `Ctrl+C` to stop.

---

## ⚙️ Configuration

Edit the configuration section at the top of `door_chime_final.py`:

```python
COOLDOWN = 3                   # Minimum seconds between chimes
REED_PIN = 17                  # GPIO pin number (BCM)
MAX_LOG_SIZE_MB = 10           # Max log size before rotation
CHIME_ON_CLOSE = False         # Set True to also chime when door closes
DEBUG_MODE = False             # Set True for verbose debugging
```

---

## 🔄 Deployment: Run on Boot

To ensure the chime runs 24/7, even after power outages or reboots, set it up as a systemd service.

### 1. Create the Service File

```bash
sudo nano /etc/systemd/system/doorchime.service
```

### 2. Add Configuration

Paste the following (adjusting paths for your setup):

```ini
[Unit]
Description=Door Chime System
After=multi-user.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/raspberry-pi-door-chime
ExecStart=/usr/bin/python3 /home/pi/raspberry-pi-door-chime/door_chime_final.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable doorchime.service
sudo systemctl start doorchime.service
```

### 4. Verify and Monitor

Check status:
```bash
sudo systemctl status doorchime.service
```

View live logs:
```bash
journalctl -u doorchime.service -f
```

Stop the service:
```bash
sudo systemctl stop doorchime.service
```

---

## 🔧 Troubleshooting

### No Sound Plays
- **Check sound file**: Verify `doorbell.wav` exists in the correct directory
- **Test audio output**: `speaker-test -t wav`
- **Check volume**: Run `alsamixer` and ensure volume is up
- **Enable debug mode**: Set `DEBUG_MODE = True` in the script

### Chime Plays at Wrong Time
- **Verify switch type**: Ensure you have a Normally Closed (NC) switch
- **Check alignment**: Magnet should be within 1-2cm when door is closed
- **Test with magnet**: Move a handheld magnet near the switch to test
- **Wrong switch type?** If you have NO instead of NC, swap the event handlers

### GPIO Permission Errors
```bash
sudo usermod -a -G gpio pi
sudo reboot
```

### Service Won't Start
- Check file paths in the service file match your installation
- Verify Python path: `which python3`
- Check logs: `journalctl -u doorchime.service -n 50`

### Log File Issues
- Ensure write permissions in the script directory
- Log automatically rotates at `MAX_LOG_SIZE_MB` (default: 10MB)
- Old logs saved as `door_log.txt.old`

---

## 📁 File Structure

```
raspberry-pi-door-chime/
├── door_chime_final.py    # Main script
├── doorbell.wav           # Your sound file (you provide this)
├── door_log.txt           # Auto-generated event log
├── door_log.txt.old       # Rotated log (when size exceeded)
└── README.md              # This file
```

---

## 🔍 How It Works

### Reed Switch Operation (Normally Closed)

1. **Door Closed**: Magnet near switch → Circuit closed → GPIO LOW → `sensor.is_pressed = True`
2. **Door Opens**: Magnet moves away → Circuit open → GPIO HIGH (pulled up) → `when_pressed` triggered
3. **Chime Plays**: Sound plays if cooldown period has elapsed
4. **Event Logged**: Timestamp and event written to `door_log.txt`
5. **Door Closes**: Magnet returns → Circuit closes → `when_released` triggered

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
