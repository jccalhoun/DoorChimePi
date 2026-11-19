#!/usr/bin/env python3
"""
Door Chime System for Raspberry Pi
Plays sound when door opens using reed switch

REED SWITCH OPERATION (NC reed switch = contacts closed when NO magnet is near):
- Gate closed: magnet near switch → contacts open → GPIO HIGH (pull-up) → not pressed
- Gate opens: magnet moves away → contacts close → GPIO LOW → pressed → chime

Note: If using a normally open (NO) switch, the when_pressed and when_released 
handlers would need to be swapped, and GATE_OPEN_REMINDER set to 0.

WEB PAGE: http://<pi-address>:8080 shows gate status and recent events,
and lets you test the chime or pick a different .wav from this folder.
"""

import os
import sys
import json
import logging
import threading
from collections import deque
from urllib.parse import urlencode
import time
import argparse
import signal
from datetime import datetime
from signal import pause
from pathlib import Path
from gpiozero import Button
from pygame import mixer

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================
BASE_DIR = Path(__file__).parent.resolve()
CHIME_SOUND = BASE_DIR / "doorbell.wav"
LOG_FILE = BASE_DIR / "door_log.txt"

COOLDOWN = 3                   # Minimum seconds between chimes
REED_PIN = 17                  # GPIO pin number (BCM)
MAX_LOG_SIZE_MB = 10           # Max log size before rotation
CHIME_ON_CLOSE = False         # Chime on door closure
DEBUG_MODE = False
GATE_OPEN_REMINDER = 120       # Re-chime every N seconds while gate stays open (0 = off)
WEB_PORT = 8080                # Status web page port (0 = off)
SETTINGS_FILE = BASE_DIR / "chime_settings.json"   # Remembers the chosen sound
VOLUME = 0.7


def debug_print(message: str) -> None:
    """Print debug messages if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")


def available_sounds() -> list:
    """Names of the .wav files sitting next to this script"""
    return sorted(f.name for f in BASE_DIR.glob('*.wav'))


def saved_sound_name() -> str:
    """Sound chosen on the web page, or the default if none/invalid"""
    try:
        name = json.loads(SETTINGS_FILE.read_text()).get("sound", "")
        if name in available_sounds():
            return name
    except (OSError, ValueError, AttributeError):
        pass
    return CHIME_SOUND.name


def load_sound(name: str) -> mixer.Sound:
    """Load one of the .wav files in BASE_DIR by name"""
    if name not in available_sounds():
        raise FileNotFoundError(f"Sound file '{BASE_DIR / name}' not found")
    sound = mixer.Sound(str(BASE_DIR / name))
    sound.set_volume(VOLUME)
    return sound


def setup_audio() -> tuple:
    """Initialize audio; returns (sound, sound_name)"""
    try:
        mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        name = saved_sound_name()
        chime = load_sound(name)
        debug_print(f"Audio initialized: {name}")
        return chime, name

    except FileNotFoundError as e:
        print(f"ERROR: {e}\nAvailable sound files in {BASE_DIR}:")
        for name in available_sounds():
            print(f"  - {name}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Audio initialization failed: {e}")
        sys.exit(1)


def rotate_log_if_needed() -> None:
    """Rotate log file using pathlib for clean file management"""
    try:
        if LOG_FILE.exists():
            size_mb = LOG_FILE.stat().st_size / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                old_log = LOG_FILE.with_suffix('.txt.old')
                if old_log.exists():
                    old_log.unlink()
                LOG_FILE.rename(old_log)
                debug_print(f"Log rotated: {size_mb:.2f}MB exceeded")
    except Exception as e:
        print(f"WARNING: Log rotation failed: {e}")


def log_event(message: str, use_emoji: bool = True) -> None:
    """Log event using ASCII stripping for cross-platform log compatibility"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"

    # Strip emojis for the log file using encode/decode
    clean_log = log_entry.encode("ascii", "ignore").decode("ascii")

    print(log_entry if use_emoji else clean_log)
    rotate_log_if_needed()

    try:
        with open(LOG_FILE, "a", encoding='utf-8') as f:
            f.write(clean_log + "\n")
    except IOError as e:
        print(f"WARNING: Could not write to log file: {e}")


class DoorChime:
    """Main door chime controller managing sensor state and audio"""

    def __init__(self, chime_sound: mixer.Sound, sound_name: str,
                 cooldown_seconds: float = 3) -> None:
        self.chime = chime_sound
        self.sound_name = sound_name
        self.last_opened = None
        self.cooldown = cooldown_seconds
        self.last_trigger_time = 0.0
        self.cooldown_message_shown = False
        self._stop_requested = False

        # Setup GPIO sensor (internal pull-up for NC/NO versatility)
        # hold_time stays short so gpiozero's hold thread can shut down quickly;
        # _gate_left_open() decides when a reminder is actually due
        self.sensor = Button(REED_PIN, pull_up=True, bounce_time=0.05,
                             hold_time=1, hold_repeat=True)
        self._next_reminder = GATE_OPEN_REMINDER
        self.sensor.when_released = self._door_closed
        self.sensor.when_pressed = self._door_opened
        if GATE_OPEN_REMINDER:
            self.sensor.when_held = self._gate_left_open

        debug_print("DoorChime initialized")

    def _gate_left_open(self) -> None:
        open_for = self.sensor.active_time
        if open_for is None or open_for < self._next_reminder:
            return
        self._next_reminder += GATE_OPEN_REMINDER
        log_event("⚠️ Gate still open")
        self._play_chime("reminder")

    def set_sound(self, name: str) -> None:
        """Switch to another .wav in BASE_DIR and remember the choice"""
        self.chime = load_sound(name)
        self.sound_name = name
        SETTINGS_FILE.write_text(json.dumps({"sound": name}))
        log_event(f"Chime sound changed to {name}", use_emoji=False)

    def test_chime(self) -> None:
        """Play the chime now, ignoring the cooldown"""
        mixer.stop()
        self.chime.play()

    def _play_chime(self, event_type: str = "open") -> bool:
        current_time = time.time()
        time_since_last = current_time - self.last_trigger_time

        if time_since_last < self.cooldown:
            if not self.cooldown_message_shown:
                print(f"Cooldown active ({self.cooldown - time_since_last:.1f}s left)")
                self.cooldown_message_shown = True
            return False

        self.cooldown_message_shown = False
        self.last_trigger_time = current_time

        try:
            # Stop any overlapping audio caused by gate bounce or rattling
            if mixer.get_busy():
                debug_print("Audio channel busy, stopping previous playback.")
                mixer.stop()

            self.chime.play()
            debug_print(f"Chime played for {event_type} event")
            return True
        except Exception as e:
            print(f"ERROR: Failed to play sound: {e}")
            log_event(f"Sound playback failed: {e}", use_emoji=False)
            return False

    def _door_opened(self) -> None:
        self._next_reminder = GATE_OPEN_REMINDER
        self.last_opened = datetime.now()
        log_event("🚪 Door opened", use_emoji=True)
        self._play_chime("open")

    def _door_closed(self) -> None:
        log_event("✅ Door closed", use_emoji=True)
        if CHIME_ON_CLOSE:
            self._play_chime("close")

    def stop(self) -> None:
        """Gracefully shut down the chime system"""
        self._stop_requested = True
        log_event("System stopped", use_emoji=False)
        self.sensor.close()
        mixer.quit()
        print("Cleanup complete. Goodbye!")

    def run(self) -> None:
        """Start the door chime system with helpful status display"""
        state = "Open" if self.sensor.is_pressed else "Closed"
        log_event(f"System started - Door initially {state}", use_emoji=False)

        print("\n" + "="*40)
        print("DOOR CHIME SYSTEM ACTIVE")
        print("="*40)
        print(f"GPIO Pin: {REED_PIN} | Initial State: {state}")
        print(f"Log: {LOG_FILE.name} | Cooldown: {self.cooldown}s")
        if WEB_PORT:
            print(f"Web page: http://<this Pi's address>:{WEB_PORT}")
        print("Press Ctrl+C to exit")
        print("="*40 + "\n")

        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            pause()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()


# ============================================================================
# WEB PAGE (status, recent events, test button, sound picker)
# ============================================================================
WEB_PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15;url=/">
<title>Door Chime</title>
<style>
 body{font-family:sans-serif;max-width:34em;margin:1em auto;padding:0 1em}
 .state{font-size:1.6em;font-weight:bold;padding:.5em;border-radius:.4em;text-align:center}
 .open{background:#fdd;color:#900}.closed{background:#dfd;color:#060}
 button,select{font-size:1em;padding:.5em;margin:.2em 0}
 pre{background:#eee;padding:.6em;overflow-x:auto;font-size:.85em}
 .msg{background:#ffd;padding:.5em;border-radius:.4em}
</style></head><body>
<h1>Door Chime</h1>
<div class="state {{ 'open' if is_open else 'closed' }}">Gate is {{ 'OPEN' if is_open else 'closed' }}</div>
<p>Last opened: {{ last_opened or 'not since the chime started' }}</p>
{% if msg %}<p class="msg">{{ msg }}</p>{% endif %}
<form method="post" action="/test"><button>Test chime</button></form>
<form method="post" action="/sound">
 <label>Chime sound:
 <select name="sound">
 {% for name in sounds %}<option {{ 'selected' if name == current }}>{{ name }}</option>{% endfor %}
 </select></label>
 <button>Use this sound</button>
</form>
<h2>Recent events</h2>
<pre>{{ events }}</pre>
</body></html>"""


def start_web(chime_system: "DoorChime") -> None:
    """Serve the status page on the local network in a background thread"""
    try:
        from flask import Flask, render_template_string, request, redirect
    except ImportError:
        print("WARNING: Flask not installed, web page disabled "
              "(sudo apt install python3-flask)")
        return

    app = Flask(__name__)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    @app.get("/")
    def index():
        try:
            with open(LOG_FILE, encoding="utf-8") as f:
                events = "".join(reversed(deque(f, maxlen=20)))
        except OSError:
            events = "(no log yet)"
        last = chime_system.last_opened
        return render_template_string(
            WEB_PAGE,
            is_open=chime_system.sensor.is_pressed,
            last_opened=last.strftime("%Y-%m-%d %H:%M:%S") if last else None,
            sounds=available_sounds(),
            current=chime_system.sound_name,
            events=events,
            msg=request.args.get("msg", ""))

    @app.post("/test")
    def test():
        try:
            chime_system.test_chime()
            msg = "Played test chime"
        except Exception as e:
            msg = f"Could not play sound: {e}"
        return redirect("/?" + urlencode({"msg": msg}))

    @app.post("/sound")
    def sound():
        name = request.form.get("sound", "")
        try:
            chime_system.set_sound(name)   # only accepts .wav files in BASE_DIR
            chime_system.test_chime()
            msg = f"Now using {name}"
        except Exception as e:
            msg = f"Could not switch sound: {e}"
        return redirect("/?" + urlencode({"msg": msg}))

    def serve() -> None:
        try:
            app.run(host="0.0.0.0", port=WEB_PORT, use_reloader=False)
        except OSError as e:
            print(f"WARNING: Web page could not start on port {WEB_PORT}: {e}")

    threading.Thread(target=serve, daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi Door Chime System")
    parser.add_argument('--simulate', action='store_true',
                        help="Run in simulation mode without hardware GPIO (useful for desktop testing)")
    parser.add_argument('--debug', action='store_true',
                        help="Enable verbose debug output")
    return parser.parse_args()


def run_simulator(chime_system: DoorChime) -> None:
    """Interactive keyboard simulator for testing without hardware"""

    def simulation_loop() -> None:
        time.sleep(0.5)
        from gpiozero import Device
        pin = Device.pin_factory.pin(REED_PIN)

        # Initial state: gate closed (magnet holds contacts open → pulled HIGH)
        is_closed = True
        pin.drive_high()

        print("\n" + "-"*40)
        print("SIMULATOR CONTROLS:")
        print("  Press 't' + Enter to TOGGLE the door state")
        print("  Press 'q' + Enter to QUIT")
        print("-"*40 + "\n")

        while True:
            cmd = input().strip().lower()
            if cmd == 'q':
                # Interrupt the main thread to wake it from pause() and trigger
                # the KeyboardInterrupt handler in run(), which calls stop()
                os.kill(os.getpid(), signal.SIGINT)
                return
            elif cmd == 't':
                is_closed = not is_closed
                if is_closed:
                    pin.drive_high()  # Magnet near → contacts open → HIGH
                else:
                    pin.drive_low()   # Magnet away → contacts close → LOW

    sim_thread = threading.Thread(target=simulation_loop, daemon=True)
    sim_thread.start()


def main() -> None:
    args = parse_args()

    global DEBUG_MODE
    if args.debug:
        DEBUG_MODE = True

    if args.simulate:
        print("\n[INFO] Starting in SIMULATION MODE. Hardware GPIO bypassed.")
        from gpiozero import Device
        from gpiozero.pins.mock import MockFactory
        Device.pin_factory = MockFactory()

    chime_sound, sound_name = setup_audio()
    chime_system = DoorChime(chime_sound, sound_name, COOLDOWN)

    if WEB_PORT:
        start_web(chime_system)

    if args.simulate:
        run_simulator(chime_system)

    chime_system.run()


if __name__ == "__main__":
    main()
