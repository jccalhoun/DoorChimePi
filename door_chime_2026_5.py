#!/usr/bin/env python3
"""
Door Chime System for Raspberry Pi
Plays sound when door opens using reed switch

REED SWITCH OPERATION (Normally Closed - NC):
- When door is closed: magnet near switch → circuit closed → GPIO LOW → sensor pressed
- When door opens: magnet away from switch → circuit open → GPIO HIGH (pulled up) → sensor released

Note: If using a normally open (NO) switch, the when_pressed and when_released 
handlers would need to be swapped.
"""

import sys
import time
import argparse
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


def debug_print(message: str) -> None:
    """Print debug messages if DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")


def setup_audio() -> mixer.Sound:
    """Initialize audio system with Path-based error handling"""
    try:
        mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

        if not CHIME_SOUND.exists():
            raise FileNotFoundError(f"Sound file '{CHIME_SOUND}' not found")

        chime = mixer.Sound(str(CHIME_SOUND))
        chime.set_volume(0.7)
        debug_print(f"Audio initialized: {CHIME_SOUND.name}")
        return chime

    except FileNotFoundError as e:
        print(f"ERROR: {e}\nAvailable sound files in {BASE_DIR}:")
        for file in BASE_DIR.glob('*.wav'):
            print(f"  - {file.name}")
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

    def __init__(self, chime_sound: mixer.Sound, cooldown_seconds: float = 3) -> None:
        self.chime = chime_sound
        self.cooldown = cooldown_seconds
        self.last_trigger_time = 0.0
        self.cooldown_message_shown = False
        self._stop_requested = False

        # Setup GPIO sensor (internal pull-up for NC/NO versatility)
        self.sensor = Button(REED_PIN, pull_up=True, bounce_time=0.05)
        self.sensor.when_released = self._door_closed
        self.sensor.when_pressed = self._door_opened

        debug_print("DoorChime initialized")

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
        state = "Closed" if self.sensor.is_pressed else "Open"
        log_event(f"System started - Door initially {state}", use_emoji=False)

        print("\n" + "="*40)
        print("DOOR CHIME SYSTEM ACTIVE")
        print("="*40)
        print(f"GPIO Pin: {REED_PIN} | Initial State: {state}")
        print(f"Log: {LOG_FILE.name} | Cooldown: {self.cooldown}s")
        print("Press Ctrl+C to exit")
        print("="*40 + "\n")

        try:
            pause()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi Door Chime System")
    parser.add_argument('--simulate', action='store_true',
                        help="Run in simulation mode without hardware GPIO (useful for desktop testing)")
    parser.add_argument('--debug', action='store_true',
                        help="Enable verbose debug output")
    return parser.parse_args()


def run_simulator(chime_system: DoorChime) -> None:
    """Interactive keyboard simulator for testing without hardware"""
    import threading
    import _thread

    def simulation_loop() -> None:
        time.sleep(0.5)
        from gpiozero import Device
        pin = Device.pin_factory.pin(REED_PIN)

        # Initial state: door closed (circuit connected → pulled low)
        is_closed = True
        pin.drive_low()

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
                _thread.interrupt_main()
                return
            elif cmd == 't':
                is_closed = not is_closed
                if is_closed:
                    pin.drive_low()   # Simulate magnet closing the circuit
                else:
                    pin.drive_high()  # Simulate magnet moving away (pulled up)

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

    chime_sound = setup_audio()
    chime_system = DoorChime(chime_sound, COOLDOWN)

    if args.simulate:
        run_simulator(chime_system)

    chime_system.run()


if __name__ == "__main__":
    main()
