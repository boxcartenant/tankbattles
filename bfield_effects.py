import tkinter as tk
import math
from config import WIDTH, HEIGHT, UNIT_SIZE, FPS
from PIL import Image, ImageTk
import time
import random

# Step-by-step guide for adding new effects:
#
# 1. Add a new entry to EFFECT_TYPES dictionary:
#    - Key: Effect name (e.g., "New Effect").
#    - Value: Dictionary with:
#      - "type": "bubble" (one large sprite), "scatter" (multiple small sprites), or "line" (sprites in a line).
#      - "target": "allied", "enemy", "both" (units), or "bullets".
#      - "effect": Attribute to modify (e.g., "HP", "speed", "damage_boost").
#      - "magnitude type": "scalar" (add to attribute) or "multiplier" (multiply attribute).
#      - "magnitude": Value to apply (e.g., -70 for damage, 0.5 for speed reduction).
#      - "frequency": Times per second to apply (0 for one-time on entering area).
#      - "duration": Seconds the effect lasts (0 for instant effects).
#      - "cost": Cash cost.
#      - "delay": Seconds before activation after round starts.
#      - "radius": For "bubble"/"line", sprite size; for "scatter", distribution area radius.
#      - "count": Number of sprites (1 for "bubble", ignored for "bubble").
# 2. Add a 16x16 sprite to effect_sprites.png, vertically below the last sprite.
#    - Sprite order must match EFFECT_TYPES key order (e.g., first key at y=0, second at y=16).
# 3. Update _apply_to_unit in Effect class to handle the new "effect" identifier if it targets units.
# 4. For "bubble"/"line" effects, ensure the sprite is scaled to "radius" in _render_visual.
# 5. For networked games, ensure netHandler.send("effect", {"name": effect_name, "x": x, "y": y}) is called in Batfield.py.
# 6. Test in solo and networked modes to verify rendering, timing, and synchronization.

# Load sprite sheet for effects
EFFECT_SPRITES = Image.open("effect_sprites.png")

class Effect:
    def __init__(self, canvas, name, effect_type, target, effect, magnitude_type, magnitude, frequency, duration, cost, delay, radius, count, x=None, y=None, orientation="horizontal", end_x=None, end_y=None, team="green"):
        self.canvas = canvas
        self.name = name
        self.type = effect_type  # bubble, scatter, line
        self.target = target  # allied, enemy, both, bullets
        self.effect = effect  # HP, speed, damage_boost, sm
        self.magnitude_type = magnitude_type  # scalar, multiplier
        self.magnitude = magnitude
        self.frequency = frequency  # Times per second (0 for one-time)
        self.duration = duration
        self.cost = cost
        self.delay = delay
        self.radius = radius  # Sprite size (bubble/line) or distribution area (scatter)
        self.count = count
        self.x = x
        self.y = y
        self.orientation = orientation  # horizontal, vertical, custom
        self.end_x = end_x  # For custom line
        self.end_y = end_y  # For custom line
        self.active = False
        self.start_time = None
        self.last_apply = None
        self.sprite = None
        self.sprite_ids = []
        self.sprite_positions = []
        self.affected_units = set()  # Track units for one-time effects
        self.setup_phase = True  # True during setup
        self.team = team
        self.charging_up = True

    def apply(self):
        # Show immediately during setup
        self._render_visual()
        # Will be hidden and reactivated in start_battle/activate

    def start_battle(self, unit_manager):
        # Called when round timer starts
        self.setup_phase = False
        self._remove_visual()
        self.canvas.after(int(self.delay * 1000), lambda unit_manger=unit_manager: self._activate(unit_manager))

    def _activate(self, unit_manager):
        self.charging_up = False
        self.active = True
        self.start_time = time.time()
        self.last_apply = time.time()
        self._render_visual()
        if self.duration == 0:
            self._apply_instant_effect(unit_manager)
            self.active = False
            self._remove_visual()

    def _apply_to_unit(self, unit):
        if self.frequency == 0 and unit in self.affected_units:
            return
        if self.magnitude_type == "scalar":
            if self.effect == "HP":
                unit.HPMod(self.magnitude)
        elif self.magnitude_type == "multiplier":
            if self.effect == "speed":
                unit.v *= self.magnitude
            elif self.effect == "damage":
                unit.damage *= self.magnitude  # Proxy for damage
        if self.frequency == 0:
            self.affected_units.add(unit)

    def _apply_instant_effect(self, unit_manager):
        units = self._get_target_units(unit_manager)
        for unit in units.values():
            if self._in_range(unit.xc, unit.yc) and unit.alive:
                self._apply_to_unit(unit)

    def _get_target_units(self, unit_manager):
        if self.team == "green":
            return (
                unit_manager.greenUnits if self.target == "allied" else
                unit_manager.redUnits if self.target == "enemy" else
                {**unit_manager.greenUnits, **unit_manager.redUnits}
            )
        else:
            return (
                unit_manager.greenUnits if self.target == "enemy" else
                unit_manager.redUnits if self.target == "allied" else
                {**unit_manager.redUnits, **unit_manager.greenUnits}
            )

    def _in_range(self, xc, yc):
        if self.x is None or self.y is None:
            return False
        if self.type == "bubble":
            return math.sqrt((self.x - xc)**2 + (self.y - yc)**2) <= self.radius
        else:
            if self.type == "scatter":
                sprite_size = UNIT_SIZE  # Default 16x16 sprite
                half_size = 2 * sprite_size / 2
            else:
                sprite_size = self.radius
                half_size = sprite_size / 2
            for sprite_x, sprite_y in self.sprite_positions:
                #print("target",xc,yc,"fire",sprite_x,sprite_y)
                if (abs(sprite_x - xc) <= half_size and
                    abs(sprite_y - yc) <= half_size):
                    return True
            return False
        return False

    def update(self, unit_manager):
        if (not self.active) or self.setup_phase or self.charging_up:
            return
        #print('pre duration checks')
        if self.duration > 0 and time.time() - self.start_time >= self.duration:
            self.active = False
            self._remove_visual()
            return
        #print("past duration checks")
        if self.frequency <= 0 or (time.time() - self.last_apply >= 1 / self.frequency):
            units = self._get_target_units(unit_manager)
            for unit in units.values():
                if self._in_range(unit.xc, unit.yc) and unit.alive:
                    #print("unit in range")
                    if self.frequency == 0:
                        self._apply_to_unit(unit)
                    elif self.frequency > 0:
                        #print("applying effect")
                        self._apply_to_unit(unit)
        if self.frequency > 0 and time.time() - self.last_apply >= 1 / self.frequency:
            self.last_apply = time.time()

    def _reveal_sprites(self, index=0):
        if index < len(self.sprite_ids):
            self.canvas.itemconfig(self.sprite_ids[index], state="normal")
            self.canvas.after(100, lambda: self._reveal_sprites(index + 1))

    def _render_visual(self):
        sprite_y = list(EFFECT_TYPES.keys()).index(self.name) * UNIT_SIZE
        sprite_img = EFFECT_SPRITES.crop((0, sprite_y, UNIT_SIZE, sprite_y + UNIT_SIZE))
        self.sprite_ids = []
        self.sprite_positions = []
        if self.type == "bubble":
            sprite_img = sprite_img.resize((int(self.radius * 2), int(self.radius * 2)), Image.Resampling.LANCZOS)
            self.sprite = ImageTk.PhotoImage(sprite_img)
            sprite_id = self.canvas.create_image(self.x, self.y, image=self.sprite, anchor=tk.CENTER)
            self.sprite_ids = [sprite_id]
            self.sprite_positions = [(self.x, self.y)]
        elif self.type == "scatter":
            self.sprite = ImageTk.PhotoImage(sprite_img)
            for _ in range(self.count):
                offset_x = random.uniform(-self.radius, self.radius)
                offset_y = random.uniform(-self.radius, self.radius)
                sprite_x = self.x + offset_x
                sprite_y = self.y + offset_y
                self.sprite_positions.append((sprite_x, sprite_y))
                sprite_id = self.canvas.create_image(
                    sprite_x, sprite_y,
                    image=self.sprite, anchor=tk.CENTER, state="hidden"
                )
                self.sprite_ids.append(sprite_id)
            self._reveal_sprites()
        elif self.type == "line":
            self.sprite = ImageTk.PhotoImage(sprite_img.resize((int(self.radius), int(self.radius)), Image.Resampling.LANCZOS))
            if self.end_x is not None and self.end_y is not None:
                dx = self.end_x - self.x
                dy = self.end_y - self.y
                length = math.sqrt(dx**2 + dy**2)
                if length > 0:
                    ux = dx / length
                    uy = dy / length
                else:
                    ux = 1
                    uy = 0
            else:
                ux = 1
                uy = 0
            for i in range(self.count):
                sprite_x = self.x + self.radius * i * ux
                sprite_y = self.y + self.radius * i * uy
                self.sprite_positions.append((sprite_x, sprite_y))
                sprite_id = self.canvas.create_image(
                    sprite_x, sprite_y, image=self.sprite, anchor=tk.CENTER, state="hidden"
                )
                self.sprite_ids.append(sprite_id)
            self._reveal_sprites()

    def clear(self):
        self._remove_visual()

    def _remove_visual(self):
        for sprite_id in self.sprite_ids:
            self.canvas.delete(sprite_id)
        self.sprite_ids = []
        self.sprite = None

    def check_bullet_hit(self, x0, y0, x1, y1, shooter_team):
        if self.effect == "sm" and self.active and self.setup_phase == False:
            minx, maxx = sorted([x0, x1])
            miny, maxy = sorted([y0, y1])
            if (minx <= self.x + self.radius and maxx >= self.x - self.radius and
                miny <= self.y + self.radius and maxy >= self.y - self.radius):
                return True  # Bullet blocked
        return False

class EffectsManager:
    def __init__(self, canvas, unit_manager):
        self.canvas = canvas
        self.unit_manager = unit_manager
        self.effects = []

    def setCanvas(self, canvas):
        self.canvas = canvas

    def setUnitManager(self, manager):
        unit_manager = manager

    def add_effect(self, effect_type, x=None, y=None, team="green", orientation="horizontal", end_x=None, end_y=None):
        effect_data = EFFECT_TYPES[effect_type]
        effect = Effect(
                        self.canvas,
                        effect_data["name"],
                        effect_data["type"],
                        effect_data["target"],
                        effect_data["effect"],
                        effect_data["magnitude_type"],
                        effect_data["magnitude"],
                        effect_data["frequency"],
                        effect_data["duration"],
                        effect_data["cost"],
                        effect_data["delay"],
                        effect_data["radius"],
                        effect_data["count"],
                        x=x, y=y,
                        orientation=orientation,
                        end_x=end_x, end_y=end_y,
                        team=team)
        if effect.type == "bubble" and effect.count != 1:
            effect.count = 1  # Enforce count=1 for bubble
        self.effects.append(effect)
        effect.apply()

    def start_battle(self):
        for effect in self.effects:
            effect.start_battle(self.unit_manager)

    def end_battle(self):
        for effect in self.effects:
            effect.clear()
            self.effects.remove(effect)

    def update(self):
        for effect in self.effects[:]:
            effect.update(self.unit_manager)
            if not effect.active and not effect.setup_phase and not effect.charging_up:
                #print("removing effect")
                self.effects.remove(effect)

    def check_bullet_hit(self, x0, y0, x1, y1, shooter_team):
        for effect in self.effects:
            if effect.check_bullet_hit(x0, y0, x1, y1, shooter_team):
                return True
        return False

# Effect types
#Frequency of 0 indicates an effect that occurs once on collision
#valid targets are "bullets", "enemy", "allied", and "both"
EFFECT_TYPES = {
    "Shield": {
        "name": "Shield",
        "type": "bubble",
        "target": "bullets",
        "effect": "sm",  # Step magnitude (bullet speed)
        "magnitude_type": "multiplier",
        "magnitude": 0,  # Stops bullets
        "frequency": 0,
        "duration": 15,
        "cost": 60,
        "delay": 3,
        "radius": 30,  # Sprite size
        "count": 1
    },
    "Airstrike": {
        "name": "Airstrike",
        "type": "scatter",
        "target": "both",
        "effect": "HP",
        "magnitude_type": "scalar",
        "magnitude": -120,
        "frequency": 0,
        "duration": 6,
        "cost": 40,
        "delay": 10,
        "radius": 80,  # Distribution area
        "count": 40
    },
    "Napalm": {
        "name": "Napalm",
        "type": "line",
        "target": "both",
        "effect": "HP",
        "magnitude_type": "scalar",
        "magnitude": -15,
        "frequency": 0.3,
        "duration": 20,
        "cost": 50,
        "delay": 6,
        "radius": 16,  # Sprite size
        "count": 10
    },
    "Damage Boost": {
        "name": "Damage Boost",
        "type": "bubble",
        "target": "both",
        "effect": "damage",
        "magnitude_type": "multiplier",
        "magnitude": 1.5,
        "frequency": 0,
        "duration": 10,
        "cost": 75,
        "delay": 2,
        "radius": 25,
        "count": 1
    },
    "Slow Field": {
        "name": "Slow Field",
        "type": "bubble",
        "target": "both",
        "effect": "speed",
        "magnitude_type": "multiplier",
        "magnitude": 0.5,
        "frequency": 0,
        "duration": 15,
        "cost": 40,
        "delay": 5,
        "radius": 300,
        "count": 1
    },
    "Med Camp": {
        "name": "Med Camp",
        "type": "scatter",
        "target": "allied",
        "effect": "HP",
        "magnitude_type": "scalar",
        "magnitude": 5,
        "frequency": 0.5,
        "duration": 20,
        "cost": 20,
        "delay": 0,
        "radius": 45,
        "count": 15
    }
}

effects_manager = EffectsManager(None, None)  # Canvas set in Batfield.py
