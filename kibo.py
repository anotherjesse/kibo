import time
import random

# Core Kibo APIs -------------------------------------------------------------
#  - Body : controls the 4 hobby servos in Kibo’s neck/body.
#  - face            : high‑level API for the LCD face (expression, blink, look).

from body import Body  # make sure kibo.py is on your PYTHONPATH
from face import face

# ---------------------------------------------------------------------------
# Helper routines – small, reusable motion / face snippets
# ---------------------------------------------------------------------------

def nod(ctl: Body, down: int = 20, up: int = 60, t: float = 0.6):
    """Quick nod: servo 3 is the tilt/nod axis."""
    ctl.move({3: down}, t)
    time.sleep(t)
    ctl.move({3: up}, t)
    time.sleep(t)


def sway_left_right(ctl: Body, angle: int = 60, t: float = 0.4):
    """Sway torso (servo 1) left then right."""
    ctl.move({1: 0}, t)
    time.sleep(t)
    ctl.move({1: angle}, t)
    time.sleep(t)
    ctl.move({1: 180 - angle}, t)
    time.sleep(t)
    ctl.move({1: 90}, t)  # back to center
    time.sleep(t)


def ear_wiggle(ctl: Body, repeats: int = 4, t: float = 0.2):
    """Wiggle ears (servo 2)."""
    for _ in range(repeats):
        ctl.move({2: 40}, t)
        time.sleep(t)
        ctl.move({2: 140}, t)
        time.sleep(t)
    ctl.move({2: 90}, t)
    time.sleep(t)

# ---------------------------------------------------------------------------
# Scene definitions
# ---------------------------------------------------------------------------

def scene_wake_up(face_mod, ctl: Body):
    """Kibo wakes from sleep → neutral and alert."""
    # Start with eyes closed (simulate sleep by neutral + look down)
    face_mod.set_expression("neutral")
    face_mod.look(0, -0.4)
    time.sleep(1.0)
    # Slow blink awake
    face_mod.blink("both")
    time.sleep(0.5)
    face_mod.blink("both")
    # Stretch: small sway + nod
    sway_left_right(ctl, angle=45, t=0.5)
    nod(ctl, down=10, up=60, t=0.4)
    face_mod.look(0, 0)  # eyes forward
    time.sleep(0.5)


def scene_meh(face_mod, ctl: Body):
    """Kibo feels meh → sad expression & half‑hearted shrug."""
    face_mod.set_expression("sad")
    # Slight head tilt (servo 0) and minimal sway to convey lethargy
    ctl.move({0: 70}, 0.6)
    ctl.move({1: 60}, 0.8)
    time.sleep(1.2)
    ctl.center_all(0.8)
    time.sleep(0.8)


def scene_happy_dance(face_mod, ctl: Body, bars: int = 4):
    """Simple two‑beat left/right dance with a happy face."""
    face_mod.set_expression("happy")
    for _ in range(bars):
        sway_left_right(ctl, angle=70, t=0.35)
        ear_wiggle(ctl, repeats=2, t=0.15)
    # Finish with a cheerful blink
    face_mod.blink(random.choice(["left", "right", "both"]))

# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_demo():
    ctl = Body()
    try:
        # Initial neutral/reset
        ctl.center_all(1.2)
        face.set_expression("neutral")
        time.sleep(1.0)

        # --- Demo sequence --------------------------------------------------
        scene_wake_up(face, ctl)
        time.sleep(0.5)

        scene_meh(face, ctl)
        time.sleep(0.5)

        scene_happy_dance(face, ctl, bars=6)
        time.sleep(0.5)

        # Return to neutral & idle random loop for fun
        face.set_expression("neutral")
        ctl.center_all(1.0)
        idle_start = time.time()
        while time.time() - idle_start < 15:  # 15 s of idle randomness
            random.choice([
                lambda: face.look(random.uniform(-1, 1), random.uniform(-0.5, 0.5)),
                lambda: face.blink(random.choice(["both", "left", "right"])),
            ])()
            time.sleep(random.uniform(1.0, 2.0))

    except KeyboardInterrupt:
        pass
    finally:
        ctl.stop()
        face.stop()


if __name__ == "__main__":
    run_demo()

