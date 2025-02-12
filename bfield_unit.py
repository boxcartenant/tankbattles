import tkinter as tk
import random
from PIL import Image, ImageTk
from functools import partial
import time
import threading
import concurrent.futures
import math
import copy
from collections import defaultdict


#debugging variables. will be removed in final release.
SYMMETRICAL_TEAMS = False #Set to false if you want random team comp and placement.
NUMBER_OF_UNITS = 100#units per team


# Constants
WINNER_DECLARED = False
WIDTH = 1024
HEIGHT = 768
UNIT_SIZE = 16
FPS = 30  # Maximum frame rate
UNIT_THREAD_COUNT = 2

THIS_IS_A_CLIENT = False #is this a client in a network game?
THIS_IS_A_SERVER = False #is this a server in a network game?


############
#DEVELOPERS: how to add more troop types...
#
# - make another item in TROOP_TYPES; name it and fill the data
# - - make sure the "homebase" is always the last index.
# - add a new sprite to the spritesheet. 
# - - make sure the homebase and dead-tank are the bottom two sprites.
# - update AI_TEAM_COMPS to have the new unit
# Done! It will populate the shop buttons and everything else for you.

#callbacklist = {
# X "ready":net_ready,
# X "unit":net_addunit,
# "die":net_unitdie,
# "target":net_targetunit,
# "shoot":net_fixshot
#}

# canon, chaingun, missile, laser, shotgun, base
AI_TEAM_COMPS = {
    "Mall Cop": (20,20,20,20,20,0),
    "Turtle": (40,10,20,20,10,0),
    "Snapper": (40,20,10,10,20,0),
    "Tosser": (20,5,35,35,5,0),
    "Rusher": (5,35,5,10,35,0),
    "Spread": (5,10,35,5,35,0)
    }
    

TROOP_TYPES = {
    "Canon": {
        "range": 200.0,  # pixels
        "shotcolor": "blue",
        "damage": 20.0,
        "rate": 4.0, # seconds between shots
        "shotcount": 1, # how many bullets come out in one shot
        "spread": 5.0, # size of shot cone (degrees)
        "HP": 130.0,
        "speed": 1.3, # tank movement speed in pixels
        "bulletspeed": 40, 
        "simulshots": 1, # how many times the gun can shoot again while it still has bullets in the air
        "cost": 70
    },
    "Chaingun": {
        "range": 150.0,
        "shotcolor": "orange",
        "damage": 2.0,
        "rate": 0.2,
        "shotcount": 1,
        "spread": 10.0,
        "HP": 80.0,
        "speed": 2.0,
        "bulletspeed": 30,
        "simulshots": 2,
        "cost": 67
    },
    "Missile": {
        "range": 300.0,
        "shotcolor": "red",
        "damage": 15.0,
        "rate": 8.0,
        "shotcount": 10,
        "spread": 20.0, 
        "HP": 40.0,
        "speed": 0.5,
        "bulletspeed": 5,
        "simulshots": 1,
        "cost": 55
    },
    "Laser": {
        "range": 250.0,
        "shotcolor": "purple",
        "damage": 1.2,
        "rate": 0.1,
        "shotcount": 1,
        "spread": 0.0, 
        "HP": 80.0,
        "speed": 1.0,
        "bulletspeed": 50,
        "simulshots": 2,
        "cost": 80
    },
    "Shotgun": {
        "range": 100.0,
        "shotcolor": "pink",
        "damage": 1.0,
        "rate": 2.0,
        "shotcount": 20,
        "spread": 50.0, 
        "HP": 50.0,
        "speed": 2.5,
        "bulletspeed": 30,
        "simulshots": 1,
        "cost": 35
    },
    "Homebase": {
        "range": 400.0,
        "shotcolor": "black",
        "damage": 50.0,
        "rate": 30.0,
        "shotcount": 1,
        "spread": 0.0, 
        "HP": 500.0,
        "speed": 0,
        "bulletspeed": 10,
        "simulshots": 1,
        "cost": 9999
    }
}

class BattleGrid:
    def __init__(self, grid_size = 50):
        global WIDTH, HEIGHT, UNIT_SIZE
        self.grid_size = grid_size
        self.cols = int(math.ceil(WIDTH / grid_size))
        self.rows = int(math.ceil(HEIGHT / grid_size))
        self.grid = defaultdict(set)  # Keys are (grid_x, grid_y), values are sets of Unit objects

    def _get_cell_keys(self, x, y, size):
        """Returns a set of grid keys the unit overlaps based on its top-left (x, y) and size."""
        min_x = int(x // self.grid_size)
        min_y = int(y // self.grid_size)
        max_x = int((x + size) // self.grid_size)
        max_y = int((y + size) // self.grid_size)
        return {(gx, gy) for gx in range(min_x, max_x + 1) for gy in range(min_y, max_y + 1)}

    def update_unit(self, unit):
        """Updates the unit's position in the grid."""
        new_keys = self._get_cell_keys(unit.x, unit.y, UNIT_SIZE)
        old_keys = getattr(unit, 'grid_keys', set())
        
        if new_keys != old_keys:
            for key in old_keys:
                self.grid[key].discard(unit)
            for key in new_keys:
                self.grid[key].add(unit)
            unit.grid_keys = new_keys

    def check_bullet_hit(self, x0, y0, x1, y1,shooter_team):
        """Checks which unit (if any) is hit by a bullet traveling from (x0, y0) to (x1, y1)."""
        minx, maxx = sorted([x0, x1])
        miny, maxy = sorted([y0, y1])
        
        # Determine relevant grid cells
        min_cell_x, max_cell_x = int(minx // self.grid_size), int(maxx // self.grid_size)
        min_cell_y, max_cell_y = int(miny // self.grid_size), int(maxy // self.grid_size)
        
        checked_units = set()
        hit_unit = None
        lowd = float('inf')
        d = 0

        for gx in range(min_cell_x, max_cell_x + 1):
            for gy in range(min_cell_y, max_cell_y + 1):
                for unit in self.grid.get((gx, gy), []):
                    if unit in checked_units or unit.team_color == shooter_team:
                        continue
                    checked_units.add(unit)
                    
                    # Bounding box check
                    if minx <= unit.x + UNIT_SIZE and maxx >= unit.x and miny <= unit.y + UNIT_SIZE and maxy >= unit.y:
                        d = ((x0 - unit.xc) ** 2 + (y0 - unit.yc) ** 2) ** 0.5
                        if d < lowd:
                            lowd = d
                            hit_unit = unit
        
        return d,hit_unit
    
    def clear_grid(self):
        """Removes all units from the grid."""
        self.grid.clear()

class UnitManager():
    def __init__(self):
        self.battlefield = BattleGrid()
        self.greenUnits = {}
        self.redUnits = {}
        self.liveUnits = []
        self.liveGreenUnits = {}
        self.liveRedUnits = {}
        self.netHandler = None
        self.unitnum = 0 #increments to make a unique name/handle for each unit
        self.prefix = "um" #for "unit manager"
        self.lock = threading.Lock()
        
    def setCanvas(self, canvas):
        self.canvas = canvas

    def setNetHandler(self, netHandler):
        global THIS_IS_A_SERVER, THIS_IS_A_CLIENT
        self.netHandler = netHandler
        if netHandler.isServer:
            THIS_IS_A_SERVER = True
            self.prefix += "h"
            print("UnitManager: I'm the server")
        elif netHandler.isClient:
            THIS_IS_A_CLIENT = True
            self.prefix += "c"
            print("UnitManager: I'm the client")
        
    def add_unit(self, x, y, troop_type, team_color, handle = None):
        if handle is None:
            with self.lock:
                self.unitnum += 1
                handle = self.prefix+str(self.unitnum) #"um" for "unit manager". I might implement other name schemes from other places.
        if team_color.lower() == "green":
            self.add_green(x, y, troop_type, handle)
        else:
            self.add_red(x, y, troop_type, handle)
        return handle
            
    def add_green(self, x, y, troop_type, handle = None):
        if handle is None:
            with self.lock:
                self.unitnum += 1
                handle = self.prefix+str(self.unitnum)
        with self.lock:
            thisUnit = Unit(self.canvas, x, y, troop_type, "Green", handle, self)
            self.greenUnits[handle] = thisUnit
            self.liveGreenUnits[handle] = thisUnit
            self.liveUnits.append(thisUnit)
            random.shuffle(self.liveUnits)
            self.battlefield.update_unit(thisUnit)
        return handle

    def add_red(self, x, y, troop_type, handle = None):
        if handle is None:
            with self.lock:
                self.unitnum += 1
                handle = self.prefix+str(self.unitnum)
        with self.lock:
            thisUnit = Unit(self.canvas, x, y, troop_type, "Red", handle, self)
            self.redUnits[handle] = thisUnit
            self.liveRedUnits[handle] = thisUnit
            self.liveUnits.append(thisUnit)
            random.shuffle(self.liveUnits)
            self.battlefield.update_unit(thisUnit)
        return handle

    def reinitialize_units(self):
        self.battlefield.clear_grid()
        for unit in self.greenUnits.values():
            unit.reinitialize()
            self.liveGreenUnits[unit.handle] = unit
            self.liveUnits.append(unit)
            self.battlefield.update_unit(unit)
        for unit in self.redUnits.values():
            unit.reinitialize()
            self.liveRedUnits[unit.handle] = unit
            self.liveUnits.append(unit)
            self.battlefield.update_unit(unit)
        random.shuffle(self.liveUnits)

    def reset_shot_times(self):
        for unit in self.redUnits.values():
            unit.last_shot_time = time.time()
        for unit in self.greenUnits.values():
            unit.last_shot_time = time.time()

    def net_send(self, msg, payload):
        #if msg == "target":
            #debugvariable = [payload[0].team_color, payload[0].handle, payload[1], [p.handle for p in self.greenUnits], [q.handle for q in self.redUnits]]
            #print("send target set:",debugvariable)
        if self.netHandler:
            self.netHandler.send(msg, payload)

    def kill_unit(self, team_color, handle):
        if team_color.lower() == "green":
            self.greenUnits[handle].die()
        else:
            self.redUnits[handle].die()

    def set_unit_target(self, unit_team_color, unit_handle, target_handle):
        #I'm using copies because I was running into thread errors when I set targets for a lot of units at the start of a late-game round.
        with self.lock:
            mygreens = copy.copy(self.greenUnits)
            myreds = copy.copy(self.redUnits)
        
        #print("received target set:", debugvariable)
        if unit_team_color.lower() == "green":
            mygreens[unit_handle].target_unit = myreds[target_handle]
        else:
            myreds[unit_handle].target_unit = mygreens[target_handle]

    def fixed_shot(self, team_color, handle, bullets):
        #bullets should be a list of tuples, cooresponding to the output of calculate_shot_line, inverted for the client's mirror perspective
        #I'm using copy.copy() because I was running into thread errors when I fired a lot of units at the start of a late-game round.
        if team_color.lower() == "green":
            with self.lock:
                mygreens = copy.copy(self.greenUnits)
            mygreens[handle].executor.submit(mygreens[handle].fixed_shot, bullets)
        else:
            with self.lock:
                myreds = copy.copy(self.redUnits)
            myreds[handle].executor.submit(myreds[handle].fixed_shot, bullets)
        return


    def clear_units(self):
        for unit in self.greenUnits.values():
            unit.die()
            unit.hide()
            del unit
        for unit in self.redUnits.values():
            unit.die()
            unit.hide()
            del unit
        self.greenUnits = {}
        self.redUnits = {}
        self.battlefield.clear_grid()

allUnits = UnitManager()
TEAM_COLORS = {"Green": Image.open("GreenTankSprites.png"), "Red": Image.open("RedTankSprites.png")}

def calculate_shot_line(shooting_unit_x, shooting_unit_y, target_unit_x, target_unit_y, shooting_range, spread_factor):
    global THIS_IS_A_CLIENT
    # Calculate angle to the target
    angle_to_target = math.atan2(target_unit_y - shooting_unit_y, target_unit_x - shooting_unit_x)
    
    # Apply spread factor to the angle (randomize within the spread range)
    if THIS_IS_A_CLIENT:
        #clients should see the offset mirrored.
        spread_angle = angle_to_target + math.radians(-random.uniform(-spread_factor, spread_factor))
    else:
        spread_angle = angle_to_target + math.radians(random.uniform(-spread_factor, spread_factor))
    
    # Calculate endpoint of the line within shooting range
    end_x = shooting_unit_x + shooting_range * math.cos(spread_angle)
    end_y = shooting_unit_y + shooting_range * math.sin(spread_angle)
    
    return end_x, end_y

class Unit:
    def __init__(self, canvas, x, y, troop_type, team_color, handle = None, manager=None):
        global WIDTH, HEIGHT, UNIT_SIZE, WINNER_DECLARED, TEAM_COLORS, UNIT_THREAD_COUNT
        self.startingX = x
        self.startingY = y
        self.lock = threading.Lock()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=UNIT_THREAD_COUNT)
        self.canvas = canvas
        self.x = x
        self.xc = x+UNIT_SIZE/2
        self.y = y
        self.yc = y+UNIT_SIZE/2
        self.v = TROOP_TYPES[troop_type]["speed"]
        self.troop_type = troop_type
        self.team_color = team_color
        self.sprite_sheet = TEAM_COLORS[team_color]
        self.sprite = self.get_sprite()
        self.id = canvas.create_image(x, y, image=self.sprite, anchor=tk.NW)
        self.canvas.tag_bind(self.id, "<Enter>", self.enter)
        self.canvas.tag_bind(self.id, "<Leave>", self.leave)
        self.target_unit = None
        self.futures = [] #future objects as returned by the executor
        self.alive = True
        self.remainingHP = TROOP_TYPES[troop_type]["HP"]
        self.last_shot_time = time.time()
        self.target_in_range = False
        self.hb_max = UNIT_SIZE+4
        self.hb_size = self.hb_max
        self.healthbar = canvas.create_rectangle(x-2, y+UNIT_SIZE, x+UNIT_SIZE+2, y+UNIT_SIZE+4, fill="green")
        self.simulshots = TROOP_TYPES[troop_type]["simulshots"]
        self.waittime = 100     #miliseconds
        self.wraplength = 180   #pixels
        self.wait_id = None
        self.tw = None
        self.tooltip_text = f"{troop_type}\n"
        self.shotnames = []
        self.handle = handle
        self.manager = manager

    def reinitialize(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=UNIT_THREAD_COUNT)
        self.x = self.startingX
        self.xc = self.x+UNIT_SIZE/2
        self.y = self.startingY
        self.yc = self.y+UNIT_SIZE/2
        self.v = TROOP_TYPES[self.troop_type]["speed"]
        self.sprite = self.get_sprite()
        self.canvas.itemconfig(self.id, image=self.sprite)
        self.target_unit = None
        self.alive = True
        self.remainingHP = TROOP_TYPES[self.troop_type]["HP"]
        self.last_shot_time = time.time()
        self.target_in_range = False
        self.hb_max = UNIT_SIZE+4
        self.hb_size = self.hb_max
        self.canvas.itemconfig(self.healthbar, state = 'normal')
        self.canvas.coords(self.healthbar, self.x-2, self.y+UNIT_SIZE, self.x+UNIT_SIZE+2, self.y+UNIT_SIZE+4)
        self.canvas.coords(self.id, round(self.x), round(self.y))
        #self.canvas.delete(self.healthbar)
        #self.canvas.coords(self.healthbar, round(self.x)-2, round(self.y)+UNIT_SIZE, round(self.x)-2+self.hb_size, round(self.y)+UNIT_SIZE+4)
        self.canvas.update()

    def __del__(self):
        self.executor.shutdown(wait=True)
        del self.sprite
        try:
            self.canvas.itemconfig(self.id, state="hidden")
            self.canvas.itemconfig(self.healthbar, state="hidden")
        except Exception as e:
            print(e)

    def hide(self):
        self.canvas.itemconfig(self.healthbar, state='hidden')
        self.canvas.itemconfig(self.id, state='hidden')

    def unit_AI(self):
        global THIS_IS_A_CLIENT
        if self.alive:
            #server sends targets to clients.
            self.check_for_targets()
            #if there's a target, find out if it's in range.
            if (self.target_unit is not None):
                targdistance = ((self.xc - self.target_unit.xc) ** 2 + (self.yc - self.target_unit.yc) ** 2) ** 0.5
                if targdistance >= (TROOP_TYPES[self.troop_type]["range"]-(UNIT_SIZE*2)):
                    self.target_in_range = False
                else:
                    self.target_in_range = True
                #if the target is not in range, move to it.
                if (not self.target_in_range):
                    self.update_position()

    def get_sprite(self):
        sprite_x = 0
        sprite_y = list(TROOP_TYPES.keys()).index(self.troop_type) * UNIT_SIZE
        sprite = self.sprite_sheet.crop((sprite_x, sprite_y, sprite_x + UNIT_SIZE, sprite_y + UNIT_SIZE))
        return ImageTk.PhotoImage(sprite)

    def HPMod(self, modifier):
        #self.lock.acquire()
        self.remainingHP += modifier
        self.hb_size = self.hb_max * self.remainingHP/TROOP_TYPES[self.troop_type]["HP"]
        if self.hb_size < 0:
            self.hb_size = 1
        self.canvas.coords(self.healthbar, round(self.x)-2, round(self.y)+UNIT_SIZE, round(self.x)-2+self.hb_size, round(self.y)+UNIT_SIZE+4)
        if self.remainingHP < 0 and self.alive and (not THIS_IS_A_CLIENT):
            self.die()
        #self.lock.release()

    def die(self):
        if self.alive:
            if THIS_IS_A_SERVER:
                #print("serverunit: sending die")
                self.manager.net_send("die", net_unit_archetype(unit=self))
                #print("serverunit: die sent")
            self.alive = False
            if self.team_color == "Green":
                del self.manager.liveGreenUnits[self.handle]
            else:
                del self.manager.liveRedUnits[self.handle]
            self.manager.liveUnits = list(self.manager.liveGreenUnits.values()) + list(self.manager.liveRedUnits.values())
            random.shuffle(self.manager.liveUnits)
            sprite_x = 0
            sprite_y = len(list(TROOP_TYPES.keys())) * UNIT_SIZE #past the bottom index is a "dead" overlay
            self.sprite = ImageTk.PhotoImage(self.sprite_sheet.crop((sprite_x, sprite_y, sprite_x + UNIT_SIZE, sprite_y + UNIT_SIZE)))
            # Update the canvas item with the new sprite image
            self.canvas.itemconfig(self.id, image=self.sprite)
            self.canvas.itemconfig(self.healthbar, state = 'hidden')
            self.canvas.update()
            #self.executor.shutdown(wait=True)
    
    def update_position(self):
        dx = self.target_unit.xc - self.xc
        dy = self.target_unit.yc - self.yc
        d = ((dx) ** 2 + (dy) ** 2) ** 0.5
        vx = dx/d
        vy = dy/d
        newx = self.x + self.v*vx
        newy = self.y + self.v*vy
        x2 = newx+UNIT_SIZE
        y2 = newy+UNIT_SIZE
        if not(newx < 0 or x2 > WIDTH):
            self.x = newx
            self.xc = self.x+UNIT_SIZE/2
        if not(newy < 0 or y2 > HEIGHT):
            self.y = newy
            self.yc = self.y+UNIT_SIZE/2
        self.manager.battlefield.update_unit(self)
        #I lock the healthbar whenever we move, because sometimes healthbar ghosts were being left behind if a unit was attacked while it moved.
        self.lock.acquire()
        self.canvas.coords(self.id, round(self.x), round(self.y))
        #self.canvas.delete(self.healthbar)
        self.canvas.coords(self.healthbar, round(self.x)-2, round(self.y)+UNIT_SIZE, round(self.x)-2+self.hb_size, round(self.y)+UNIT_SIZE+4)
        #self.canvas.update()
        self.lock.release()
        #if self.target_id is not None:
            #self.canvas.delete(self.target_id)
            #self.target_id = None

    def check_for_targets(self):
        global allUnits, WINNER_DECLARED, THIS_IS_A_SERVER
        if self.team_color == "Green":
            units = allUnits.redUnits.values()
        else:
            units = allUnits.greenUnits.values()
        #shoot at unit firing rate
        current_time = time.time()
        if (current_time - self.last_shot_time) >= TROOP_TYPES[self.troop_type]["rate"]:
            shoot_range = TROOP_TYPES[self.troop_type]["range"]
            #units lock onto the nearest unit and keep following until it dies.
            #find a new target if the current target is empty or dead.
            if (self.target_unit is None) or (not self.target_unit.alive):
                shortest_distance = float('inf')
                self.target_unit = None
                for unit in units:
                    if unit.alive:
                        distance = ((self.xc - unit.xc) ** 2 + (self.yc - unit.yc) ** 2) ** 0.5
                        if distance < shortest_distance:
                            shortest_distance = distance
                            self.target_unit = unit
                #if no target was found, it's because they're all dead.
                if (self.target_unit is None) and (not WINNER_DECLARED):
                    WINNER_DECLARED = True
                    print(self.team_color, "wins!")
                elif self.target_unit:
                    #print("serverunit: setting target:",self.handle, self.target_unit.handle)
                    self.manager.net_send("target", [net_unit_archetype(unit = self),self.target_unit.handle])
            #if the target is in range, shoot it
            if (self.target_unit is not None) and (self.simulshots > 0):
                distance = ((self.xc - self.target_unit.xc) ** 2 + (self.yc - self.target_unit.yc) ** 2) ** 0.5
                if distance < (shoot_range-(UNIT_SIZE*2)):
                    #set target_in_range so we won't move forward anymore
                    self.target_in_range = True

                    self.executor.submit(self.animate_bullet, self.troop_type, self.target_unit, self.xc, self.yc)
                    #self.futures.append(self.executor.submit(self.animate_bullet, self.troop_type, self.target_unit, self.xc, self.yc))
                    
                    #self.threads.append(threading.Thread(target=self.animate_bullet, args=(self.troop_type, self.target_unit, self.xc, self.yc)))
                    #self.threads[-1].start() 
                    #cleaned_futures = []
                    #for future in self.futures:
                    #    if not future.done():
                    #        cleaned_futures.append(future)
                    #self.futures = cleaned_futures
                    self.last_shot_time = current_time
                else:
                    #gotta get closer to hit.
                    self.target_in_range = False
                    #return  # Stop checking for more targets after hitting the first one
    
    def animate_bullet(self, troop_type, target_unit, x0, y0):
        global THIS_IS_A_SERVER
        bullet_id = []
        bulletspeed = TROOP_TYPES[troop_type]["bulletspeed"]
        distance = TROOP_TYPES[troop_type]["range"]
        steps = int(distance / bulletspeed)
        net_bullets = []
        try:
            for i in range(TROOP_TYPES[troop_type]["shotcount"]):
                #get an endpoint for the bullet, accounting for spread
                x1, y1 = calculate_shot_line(x0, y0, target_unit.xc, target_unit.yc, TROOP_TYPES[troop_type]["range"], TROOP_TYPES[troop_type]["spread"])
                #if THIS_IS_A_SERVER:
                #    net_bullets.append([x1,y1])
                #calculate the vector components of the shot line
                dx, dy = x1 - x0, y1 - y0
                #get the unit vector
                vx, vy = dx / distance, dy / distance
                #get the step magnitude
                sm = distance/steps
                #two ways to get the vector magnitude:
                #vox, voy = dx / steps, dy / steps
                #vmx, vmy = vx*sm, vy*sm 
                # Create a line with zero length initially. The bool at the end marks whether the bullet has hit.
                #self.lock.acquire()
                mybid = self.canvas.create_line(x0, y0, x0, y0, fill=TROOP_TYPES[troop_type]["shotcolor"])
                #self.lock.release()
                bullet_id.append([mybid, vx, vy, sm, False, 0, 0])
            self.simulshots -= 1
            #animate the bullets
            #if THIS_IS_A_SERVER:
                #print("serverunit: sending shots")
                #self.manager.net_send("shoot", [net_unit_archetype(unit = self),net_bullets])
                #print("serverunit: shots sent")
            self.grow_bullets(bullet_id, steps, x0, y0)
        except Exception as e:
            print("something broke in animate_bullet:",e)
        return

    def fixed_shot(self, bullets):
        #this is an alternative to animate_bullet. It is intended to be called on clients from the server, to synchronize spread angles.
        bullet_id = []
        bulletspeed = TROOP_TYPES[self.troop_type]["bulletspeed"]
        distance = TROOP_TYPES[self.troop_type]["range"]
        steps = int(distance / bulletspeed)
        x0 = self.xc
        y0 = self.yc
        try:
            for i in range(len(bullets)):
                x1 = bullets[i][0]
                y1 = bullets[i][1]
                #calculate the vector components of the shot line
                dx, dy = x1 - x0, y1 - y0
                #get the unit vector
                vx, vy = dx / distance, dy / distance
                #get the step magnitude
                sm = distance/steps
                #two ways to get the vector magnitude:
                #vox, voy = dx / steps, dy / steps
                #vmx, vmy = vx*sm, vy*sm 
                # Create a line with zero length initially. The bool at the end marks whether the bullet has hit.
                #self.lock.acquire()
                mybid = self.canvas.create_line(x0, y0, x0, y0, fill=TROOP_TYPES[self.troop_type]["shotcolor"])
                #self.lock.release()
                bullet_id.append([mybid, vx, vy, sm, False, 0, 0])
            self.simulshots -= 1
            #animate the bullets
            self.grow_bullets(bullet_id, steps, x0, y0)
        except Exception as e:
            print("something broke in fixed_shot:",e)
        return

    def grow_bullets(self, bullet_id, steps, x0, y0):
        try:
            for b in range(steps):
                for bullet in bullet_id:
                    #did this bullet hit its target yet?
                    if not bullet[4]:
                        #basic attack vector
                        vx = bullet[1]*bullet[3]
                        vy = bullet[2]*bullet[3]
                        #the target's health is depleated inside self.check_bullet_hit
                        d, hitunit = self.manager.battlefield.check_bullet_hit(x0 + vx*b, y0 + vy*b, x0 + vx*(b+1), y0 + vy*(b+1), self.team_color)
                        #d = distance to target if hit, else 0
                        if (d==0):
                            xmag = vx*(b+1)
                            ymag = vy*(b+1)
                            #self.lock.acquire()
                            self.canvas.coords(bullet[0], x0, y0, x0 + xmag, y0 + ymag)
                            #self.canvas.update()
                            #self.lock.release()
                        else:
                            #bullet hit = true. don't check this bullet anymore
                            bullet[4] = True
                            xmag = vx*b + bullet[1]*d
                            ymag = vy*b + bullet[2]*d
                            #use the unit vector to get the distance we should render the bullet
                            #self.lock.acquire()
                            self.canvas.coords(bullet[0], x0, y0, x0 + xmag, y0 + ymag)
                            #self.canvas.update()
                            #self.lock.release()
                        if hitunit is not None:
                            #print(hitunit.remainingHP)
                            hitunit.HPMod(0-TROOP_TYPES[self.troop_type]["damage"])
                            hitunit = None
                time.sleep(0.05)  # Adjust speed here
            time.sleep(0.2) #show the bullet a little longer for the user to see it.
            #self.lock.acquire()
            for bullet in bullet_id:
                self.canvas.delete(bullet[0])  # Remove the bullet line after animation
                #self.canvas.update()
            #self.lock.release()
            del bullet_id
        except Exception as e:
            print("something broke in grow_bullets:",e)
        self.simulshots += 1
        return
        
    def check_bullet_hit(self, x0, y0, x1, y1):
        #this function has been replaced by BattleGrid.check_bullet_hit
        # which in practice is this.manager.battlefield.check_bullet_hit.
        try:
            global allUnits
            minx = min(x0, x1)
            maxx = max(x0, x1)
            miny = min(y0, y1)
            maxy = max(y0, y1)

            lowd = 999999
            hitunit = None
            if self.team_color == "Green":
                #print("gs")
                for unit in allUnits.redUnits.values():
                    #bullets pass over dead units.
                    if unit.alive:
                        if (minx <= unit.x+UNIT_SIZE and maxx >= unit.x and miny <= unit.y+UNIT_SIZE and maxy >= unit.y):
                            d = ((x0 - unit.xc) ** 2 + (y0 - unit.yc) ** 2) ** 0.5
                            if d < lowd:
                                lowd = d
                                hitunit = unit
                            #return d
            elif self.team_color == "Red":
                for unit in allUnits.greenUnits.values():
                    if unit.alive:
                        if (minx <= unit.x+UNIT_SIZE and maxx >= unit.x and miny <= unit.y+UNIT_SIZE and maxy >= unit.y):
                            d = ((x0 - unit.xc) ** 2 + (y0 - unit.yc) ** 2) ** 0.5
                            if d < lowd:
                                lowd = d
                                hitunit = unit
                            #unit.HPMod(0-TROOP_TYPES[self.troop_type]["damage"])
                            #return d
            if hitunit is not None:
                #print(hitunit.remainingHP)
                hitunit.HPMod(0-TROOP_TYPES[self.troop_type]["damage"])
                #self.canvas.after(1, lambda pop=0-TROOP_TYPES[self.troop_type]["damage"]: hitunit.HPMod(pop))
                return lowd
        except Exception as e:
            print("something broke in check_bullet_hit:",e)
        return 0
    
    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.wait_id = self.canvas.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.wait_id
        self.wait_id = None
        if id:
            self.canvas.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        #x, y, cx, cy = self.widget.bbox("insert")
        window_x = self.canvas.winfo_rootx()
        window_y = self.canvas.winfo_rooty()
        x = window_x + self.x + UNIT_SIZE + 10
        y = window_y + self.y + UNIT_SIZE + 10
        # creates a toplevel window
        self.tw = tk.Toplevel(self.canvas)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.tooltip_text, justify='left',
                       background="#ffffff", relief='solid', borderwidth=1,
                       wraplength = self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()

#callbacklist = {"ready":net_ready, "unit":net_addunit, "die":net_unitdie,"target":net_targetunit,"shoot":net_fixshot}
class net_unit_archetype:
    def __init__(self, x=None, y=None, troop_type=None, team_color=None, handle = None, unit = None):
        if unit is None:
            self.x = x
            self.y = y
            self.troop_type = troop_type
            self.team_color = team_color
            self.handle = handle
        else:
            self.x = unit.x
            self.y = unit.y
            self.troop_type = unit.troop_type
            self.team_color = unit.team_color
            self.handle = unit.handle
