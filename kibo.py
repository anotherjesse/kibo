"""
servo_controller.py (v2)
Threaded servo controller with per‑channel limits and centers for the
Adafruit 16‑channel PWM Servo HAT.

Highlights
==========
* **Per‑channel min, max, center** enforcement — commands get clamped so
  you never over‑drive a joint.
* `.move()` API unchanged but now safe: angles outside range are clipped.
* `.center_all(duration)` helper to glide every servo to its defined
  center.
* Linear easing, 50 Hz tick, thread‑safe just like v1.

Channel defaults for your robot
-------------------------------
* `0`: 30 – 80 °   (center 55)
* `1`: 0 – 180 °  (center 90)
* `2`: 40 – 140 ° (center 90)
* `3`: 0 – 180 °  (center 60)

Change those limits by passing a `limits` dict when you construct
`ServoController`.

Example
-------
```python
from servo_controller import ServoController
ctl = ServoController()
# Bob up (servo 0) and nod down (servo 3) over 1 s
ctl.move({0: 80, 3: 20, 1: None, 2: None}, 1.0)
# Recentre everything in two seconds
ctl.center_all(2.0)
```
"""

import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Iterable
from adafruit_servokit import ServoKit


@dataclass
class Limits:
    min_angle: float
    max_angle: float
    center: float
    name: str

    def clamp(self, value: float) -> float:
        return max(self.min_angle, min(self.max_angle, value))


DEFAULT_LIMITS: Dict[int, Limits] = {
    0: Limits(30, 80, 55, 'bob'),
    1: Limits(0, 180, 90, 'sway'),
    2: Limits(40, 140, 90, 'ear wiggle'),
    3: Limits(0, 180, 60, 'nodding'),
}


class ServoController:
    """Background servo mover with limits / centers."""

    def __init__(
        self,
        active_channels: Iterable[int] = (0, 1, 2, 3),
        limits: Dict[int, Limits] = None,
        tick_hz: int = 50,
        i2c_address: int = 0x40,
    ) -> None:
        self.kit = ServoKit(channels=16, address=i2c_address)
        self.tick = 1.0 / tick_hz
        self.channels = list(active_channels)
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}

        self._lock = threading.Lock()
        self._current: Dict[int, float] = {
            ch: self.kit.servo[ch].angle or self.limits[ch].center for ch in self.channels
        }
        self._target = dict(self._current)
        self._delta = {ch: 0.0 for ch in self.channels}
        self._steps_left = {ch: 0 for ch in self.channels}

        self._stop_evt = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    # -----------------------------------------------------------
    # Public API
    # -----------------------------------------------------------

    def move(self, targets: Dict[int, Optional[float]], duration: float) -> None:
        """Move channels to new angles, clamped to limits.

        Args:
            targets: dict {channel: angle or None}
            duration: seconds to complete move (>=0)
        """
        if duration <= 0:
            duration = self.tick
        steps = max(1, int(duration / self.tick))

        with self._lock:
            for ch in self.channels:
                new_angle = targets.get(ch, None)
                if new_angle is not None:
                    # Clamp to limits
                    new_angle = self.limits[ch].clamp(float(new_angle))
                    cur = self._current[ch]
                    self._target[ch] = new_angle
                    self._delta[ch] = (new_angle - cur) / steps
                    self._steps_left[ch] = steps
                # If None: keep existing trajectory.

    def center_all(self, duration: float = 1.0) -> None:
        """Move every channel to its center over *duration* seconds."""
        self.move({ch: self.limits[ch].center for ch in self.channels}, duration)

    def get_angles(self) -> Dict[int, float]:
        with self._lock:
            return dict(self._current)

    def stop(self) -> None:
        self._stop_evt.set()
        self._thread.join()

    # -----------------------------------------------------------
    # Internal worker
    # -----------------------------------------------------------

    def _worker(self) -> None:
        while not self._stop_evt.is_set():
            time.sleep(self.tick)
            with self._lock:
                for ch in self.channels:
                    if self._steps_left[ch] > 0:
                        self._current[ch] += self._delta[ch]
                        self._steps_left[ch] -= 1
                        self.kit.servo[ch].angle = self._current[ch]


if __name__ == "__main__":
    ctl = ServoController()
    try:

        ctl.center_all(1.5)
        ctl.move({0: 80, 3: 20}, 1.0)
        time.sleep(2.2)
        ctl.center_all(1.5)
        time.sleep(1.6)
    finally:
        ctl.stop()

