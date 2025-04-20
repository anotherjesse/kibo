"""robot_face.py – Raspberry Pi‑driven 240×320 ILI9341 face renderer.

Key fixes in this revision
--------------------------
* **Back‑light always on via plain GPIO18** (no pwmio). Turns OFF on `Ctrl‑C`.
* **Image rotated 180 °** so the face is upright on your current wiring.
"""

from __future__ import annotations

import queue, random, threading, time
from typing import Tuple

from PIL import Image, ImageDraw

# Physical pixel dimensions
SCREEN_W, SCREEN_H = 240, 320
ROTATE_DEG = 90         

# ---------------- hardware init -----------------
import board, busio, digitalio
from adafruit_rgb_display import ili9341

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs  = digitalio.DigitalInOut(board.CE0)
dc  = digitalio.DigitalInOut(board.D25)
rst = digitalio.DigitalInOut(board.D24)

DISPLAY = ili9341.ILI9341(
    spi, cs=cs, dc=dc, rst=rst,
    baudrate=40_000_000,
    width=SCREEN_W, height=SCREEN_H,
)

# Back‑light simple ON/OFF
_backlight = digitalio.DigitalInOut(board.D18)
_backlight.direction = digitalio.Direction.OUTPUT
_backlight.value = True     # ON

# -------------------------------------------------
CMD_LOOK, CMD_EXPR, CMD_BLINK = range(3)

class RobotFace:
    def __init__(
        self,
        display=DISPLAY,
        *,
        eye_radius:int=32,         # Slightly smaller eyes
        pupil_radius:int=10,       # Smaller pupils
        iris_color:Tuple[int,int,int]=(0,170,255),  # Softer blue
        pupil_color:Tuple[int,int,int]=(0,0,0),
        eye_white:Tuple[int,int,int]=(255,255,255),
        bg_color:Tuple[int,int,int]=(255,255,255),  # White background
        fps:int=40,
    ) -> None:
        self.display = display
        self.eye_r = eye_radius
        self.pupil_r = pupil_radius
        self.iris_r = int(self.eye_r*0.65)  # Slightly larger iris relative to eye
        self.iris_color, self.pupil_color = iris_color, pupil_color
        self.eye_white, self.bg_color = eye_white, bg_color
        # Set a text/line color with good contrast on white background
        self.line_color = (60, 60, 80)  # Dark gray-blue for outlines and text
        self.dt = 1.0 / fps
        self._look_h = self._look_v = 0.0
        self._expression = "neutral"
        self._blink_req = None
        self._blink_t = 0.0
        self.q: "queue.Queue[tuple[int,object]]" = queue.Queue()
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    # ---------- API ----------
    def look(self, h:float, v:float=0.0):
        self.q.put((CMD_LOOK, (h, v)))
    def set_expression(self, e:str):
        self.q.put((CMD_EXPR, e))
    def blink(self, eye:str="both"):
        self.q.put((CMD_BLINK, eye))
    def stop(self):
        self._running = False
        _backlight.value = False  # turn off BL

    # ---------- render loop ----------
    def _loop(self):
        w, h = SCREEN_W, SCREEN_H
        eye_y = h//2 + 20  # Move eyes significantly down (was h//2 - 5)
        eye_off = w//4
        pupil_max = self.eye_r - self.pupil_r - 2
        last = time.monotonic()
        nat_blink_timer = 0.0
        while self._running:
            # handle commands
            while not self.q.empty():
                cmd, data = self.q.get()
                if cmd == CMD_LOOK:
                    self._look_h, self._look_v = data  # type: ignore
                elif cmd == CMD_EXPR:
                    self._expression = str(data)
                elif cmd == CMD_BLINK:
                    self._blink_req, self._blink_t = str(data), 0.0
            now = time.monotonic()
            dt = now - last
            last = now
            nat_blink_timer += dt
            self._blink_t += dt
            if nat_blink_timer > random.uniform(6,9):
                self._blink_req, self._blink_t = "both", 0.0
                nat_blink_timer = 0.0
            blinking = False
            blink_eye = "both"
            if self._blink_req and self._blink_t < 0.3:
                blinking, blink_eye = True, self._blink_req
            elif self._blink_req and self._blink_t >= 0.3:
                self._blink_req = None
            img = Image.new("RGB", (w, h), self.bg_color)
            draw = ImageDraw.Draw(img)
            
            # Draw cat ears
            ear_size = self.eye_r * 1.5  # Equal width and height
            ear_spacing = w // 2.8  # Bring ears a bit closer together
            ear_y_pos = eye_y - self.eye_r * 4.5  # Position ears much higher relative to eyes
            ear_line_width = 5  # Thicker line width for hollow ears
            
            # Function to rotate a point around an anchor
            def rotate_point(point, anchor, angle_degrees):
                import math
                # Convert angle to radians
                angle_rad = math.radians(angle_degrees)
                # Translate point to origin
                x, y = point[0] - anchor[0], point[1] - anchor[1]
                # Rotate point
                x_new = x * math.cos(angle_rad) - y * math.sin(angle_rad)
                y_new = x * math.sin(angle_rad) + y * math.cos(angle_rad)
                # Translate point back
                return (x_new + anchor[0], y_new + anchor[1])
            
            # Left ear (hollow with pink inside)
            left_ear_angle = -35  # Rotate 35 degrees counterclockwise (was -30)
            left_ear_base = (w//2 - ear_spacing, ear_y_pos + ear_size)  # Base point of ear
            
            left_ear_points_original = [
                (w//2 - ear_spacing - ear_size//2, ear_y_pos + ear_size),  # Bottom left
                (w//2 - ear_spacing, ear_y_pos),  # Top point
                (w//2 - ear_spacing + ear_size//2, ear_y_pos + ear_size),  # Bottom right
            ]
            
            # Rotate the ear points
            left_ear_points = [
                rotate_point(left_ear_points_original[0], left_ear_base, left_ear_angle),
                rotate_point(left_ear_points_original[1], left_ear_base, left_ear_angle),
                rotate_point(left_ear_points_original[2], left_ear_base, left_ear_angle),
            ]
            
            # Small pink triangle inside left ear - also rotated
            inner_scale = 0.85  # Much larger inner triangle
            offset_y = ear_size * 0.15  # Offset from the top point
            
            inner_left_ear_points_original = [
                (w//2 - ear_spacing - ear_size//2 + ear_line_width, ear_y_pos + ear_size - ear_line_width),
                (w//2 - ear_spacing, ear_y_pos + offset_y),
                (w//2 - ear_spacing + ear_size//2 - ear_line_width, ear_y_pos + ear_size - ear_line_width),
            ]
            
            inner_left_ear_points = [
                rotate_point(inner_left_ear_points_original[0], left_ear_base, left_ear_angle),
                rotate_point(inner_left_ear_points_original[1], left_ear_base, left_ear_angle),
                rotate_point(inner_left_ear_points_original[2], left_ear_base, left_ear_angle),
            ]
            
            draw.polygon(inner_left_ear_points, fill=(255, 150, 180))  # Brighter pink
            
            # Draw lines for left ear outline
            draw.line([left_ear_points[0], left_ear_points[1]], fill=self.line_color, width=ear_line_width)
            draw.line([left_ear_points[1], left_ear_points[2]], fill=self.line_color, width=ear_line_width)
            
            # Right ear (hollow with pink inside)
            right_ear_angle = 35  # Rotate 35 degrees clockwise (was 30)
            right_ear_base = (w//2 + ear_spacing, ear_y_pos + ear_size)  # Base point of ear
            
            right_ear_points_original = [
                (w//2 + ear_spacing - ear_size//2, ear_y_pos + ear_size),  # Bottom left
                (w//2 + ear_spacing, ear_y_pos),  # Top point
                (w//2 + ear_spacing + ear_size//2, ear_y_pos + ear_size),  # Bottom right
            ]
            
            # Rotate the ear points
            right_ear_points = [
                rotate_point(right_ear_points_original[0], right_ear_base, right_ear_angle),
                rotate_point(right_ear_points_original[1], right_ear_base, right_ear_angle),
                rotate_point(right_ear_points_original[2], right_ear_base, right_ear_angle),
            ]
            
            # Small pink triangle inside right ear - also rotated
            inner_right_ear_points_original = [
                (w//2 + ear_spacing - ear_size//2 + ear_line_width, ear_y_pos + ear_size - ear_line_width),
                (w//2 + ear_spacing, ear_y_pos + offset_y),
                (w//2 + ear_spacing + ear_size//2 - ear_line_width, ear_y_pos + ear_size - ear_line_width),
            ]
            
            inner_right_ear_points = [
                rotate_point(inner_right_ear_points_original[0], right_ear_base, right_ear_angle),
                rotate_point(inner_right_ear_points_original[1], right_ear_base, right_ear_angle),
                rotate_point(inner_right_ear_points_original[2], right_ear_base, right_ear_angle),
            ]
            
            draw.polygon(inner_right_ear_points, fill=(255, 150, 180))  # Brighter pink
            
            # Draw lines for right ear outline
            draw.line([right_ear_points[0], right_ear_points[1]], fill=self.line_color, width=ear_line_width)
            draw.line([right_ear_points[1], right_ear_points[2]], fill=self.line_color, width=ear_line_width)
            
            # Calculate where ears connect to head (for head positioning)
            ear_base_y = ear_y_pos + ear_size
            
            # Draw head outline - positioned slightly below ear bases
            head_radius = int(h * 0.4)  # Large circle for the head
            head_center_y = ear_base_y + head_radius - 25  # Move up more (25px instead of 15px)
            # Draw a thick black circle outline around the head
            draw.ellipse((w//2 - head_radius, head_center_y - head_radius, 
                          w//2 + head_radius, head_center_y + head_radius), 
                          outline=(0, 0, 0), width=6)
            
            # Limit eye movement to be less intense
            dx = int(self._look_h * (self.eye_r - self.pupil_r - 4) * 0.7)
            dy = int(self._look_v * (self.eye_r - self.pupil_r - 4) * 0.7)
            
            # Draw eyes
            for idx,(cx,cy) in enumerate(((w//2-eye_off,eye_y),(w//2+eye_off,eye_y))):
                side = "left" if idx==0 else "right"
                if blinking and (blink_eye in ("both", side)):
                    # Curved blink line instead of straight
                    y_offset = 3
                    draw.arc((cx-self.eye_r, cy-y_offset, cx+self.eye_r, cy+y_offset), 0, 180, fill=self.line_color, width=4)
                    continue
                
                draw.ellipse((cx-self.eye_r, cy-self.eye_r, cx+self.eye_r, cy+self.eye_r), fill=self.eye_white)
                # Add outline to the eye for better contrast on white background
                draw.ellipse((cx-self.eye_r, cy-self.eye_r, cx+self.eye_r, cy+self.eye_r), outline=self.line_color, width=2)
                
                # Add small highlight to eyes for cuteness
                highlight_size = self.iris_r // 3
                highlight_offset = self.iris_r // 2
                draw.ellipse((cx-self.iris_r+dx, cy-self.iris_r+dy, cx+self.iris_r+dx, cy+self.iris_r+dy), fill=self.iris_color)
                draw.ellipse((cx-self.pupil_r+dx, cy-self.pupil_r+dy, cx+self.pupil_r+dx, cy+self.pupil_r+dy), fill=self.pupil_color)
                draw.ellipse((cx-highlight_size+dx+highlight_offset, cy-highlight_size+dy-highlight_offset, 
                             cx+highlight_size+dx+highlight_offset, cy+highlight_size+dy-highlight_offset), fill=(255,255,255))
            
            # Draw mouth with more expressive styles
            mx0, mx1 = w//4, 3*w//4
            my = int(h*0.7)  # Move mouth up (was 0.78)
            mouth_h = h//6    # Make mouth height slightly smaller
            
            if self._expression == "happy":
                # Cuter smile with rounder edges
                draw.arc((mx0, my-mouth_h//2, mx1, my+mouth_h//2), 180, 360, fill=self.line_color, width=4)
            elif self._expression == "sad":
                # Gentler sad face
                draw.arc((mx0, my, mx1, my+mouth_h//2), 0, 180, fill=self.line_color, width=4)
            else:
                # Slightly curved neutral mouth
                draw.arc((mx0, my-mouth_h//10, mx1, my+mouth_h//10), 0, 180, fill=self.line_color, width=4)
            
            # rotate and display
            self.display.image(img.rotate(ROTATE_DEG))
            time.sleep(self.dt)

face = RobotFace()

if __name__ == "__main__":
    try:
        while True:
            random.choice([
                lambda: face.look(random.uniform(-0.7,0.7), random.uniform(-0.3,0.3)),  # Reduced eye movement range
                lambda: face.set_expression(random.choice(["neutral","happy","sad"])),
                lambda: face.blink(random.choice(["both","left","right"])),
            ])()
            time.sleep(random.uniform(1.0,2.5))
    except KeyboardInterrupt:
        face.stop()

