import tkinter as tk
import random
from PIL import Image, ImageTk
from functools import partial
import time
import threading
import concurrent.futures
import math

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


############
#DEVELOPERS: how to add more troop types...
#
# - make another item in TROOP_TYPES; name it and fill the data
# - - make sure the "homebase" is always the last index.
# - add a new sprite to the spritesheet. 
# - - make sure the homebase and dead-tank are the bottom two sprites.
# Done! It will populate the shop buttons and everything else for you.

TROOP_TYPES = {
    "Canon": {
        "range": 200.0,  # pixels
        "shotcolor": "blue",
        "damage": 20.0,
        "rate": 4.0,  # seconds between shots
        "shotcount": 1,  # how many bullets come out in one shot
        "spread": 5.0,  # size of shot cone (degrees)
        "HP": 130.0,
        "speed": 1.3,  # tank movement speed in pixels
        "bulletspeed": 40, 
        "simulshots": 1,  # how many times the gun can shoot again while it still has bullets in the air
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
        "damage": 1.0,
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
        "range": 500.0,
        "shotcolor": "black",
        "damage": 30.0,
        "rate": 30.0,
        "shotcount": 1,
        "spread": 0.0, 
        "HP": 500.0,
        "speed": 1e-08,
        "bulletspeed": 10,
        "simulshots": 1,
        "cost": 9999
    }
}



class UnitManager():
    def __init__(self):
        self.greenUnits = []
        self.redUnits = []
        
    def setCanvas(self, canvas):
        self.canvas = canvas
        
    def add_unit(self, x, y, troop_type, team_color):
        if team_color.lower() == "green":
            self.add_green(x, y, troop_type)
        else:
            self.add_red(x, y, troop_type)
            
    def add_green(self, x, y, troop_type):
        self.greenUnits.append(Unit(self.canvas, x, y, troop_type, "Green"))

    def add_red(self, x, y, troop_type):
        self.redUnits.append(Unit(self.canvas, x, y, troop_type, "Red"))

    def reinitialize_units(self):
        for unit in self.greenUnits:
            unit.reinitialize()
        for unit in self.redUnits:
            unit.reinitialize()

    def reset_shot_times(self):
        for unit in self.redUnits:
            unit.last_shot_time = time.time()
        for unit in self.greenUnits:
            unit.last_shot_time = time.time()

    def clear_units(self):
        for unit in self.greenUnits:
            unit.die()
            unit.hide()
            del unit
        for unit in self.redUnits:
            unit.die()
            unit.hide()
            del unit
        self.greenUnits = []
        self.redUnits = []

allUnits = UnitManager()
TEAM_COLORS = {"Green": Image.open("GreenTankSprites.png"), "Red": Image.open("RedTankSprites.png")}

def calculate_shot_line(shooting_unit_x, shooting_unit_y, target_unit_x, target_unit_y, shooting_range, spread_factor):
    # Calculate angle to the target
    angle_to_target = math.atan2(target_unit_y - shooting_unit_y, target_unit_x - shooting_unit_x)
    
    # Apply spread factor to the angle (randomize within the spread range)
    spread_angle = angle_to_target + math.radians(random.uniform(-spread_factor, spread_factor))
    
    # Calculate endpoint of the line within shooting range
    end_x = shooting_unit_x + shooting_range * math.cos(spread_angle)
    end_y = shooting_unit_y + shooting_range * math.sin(spread_angle)
    
    return end_x, end_y

class Unit:
    def __init__(self, canvas, x, y, troop_type, team_color):
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
        if self.alive:
            self.check_for_targets()
            if (not self.target_in_range) and (self.target_unit is not None):
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
        self.canvas.coords(self.healthbar, round(self.x)-2, round(self.y)+UNIT_SIZE, round(self.x)-2+self.hb_size, round(self.y)+UNIT_SIZE+4)
        if self.remainingHP < 0 and self.alive:
            self.die()
        #self.lock.release()

    def die(self):
        if self.alive:
            self.alive = False
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
        global allUnits, WINNER_DECLARED
        if self.team_color == "Green":
            units = allUnits.redUnits
        else:
            units = allUnits.greenUnits
        #shoot at unit firing rate
        current_time = time.time()
        if current_time - self.last_shot_time >= TROOP_TYPES[self.troop_type]["rate"]:
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
                    print("units", units)
                    print(allUnits.greenUnits, allUnits.redUnits)
                    print("mycolor", self.team_color)
                    for unit in units:
                        print(unit.alive)
                    print(self.team_color, "wins!")
            #if the target is in range, shoot it
            if (self.target_unit is not None) and (self.simulshots > 0):
                distance = ((self.xc - self.target_unit.xc) ** 2 + (self.yc - self.target_unit.yc) ** 2) ** 0.5
                if distance < (shoot_range-(UNIT_SIZE*2)):
                    #set target_in_range so we won't move forward anymore
                    self.target_in_range = True
                    self.futures.append(self.executor.submit(self.animate_bullet, self.troop_type, self.target_unit, self.xc, self.yc))

                    #self.threads.append(threading.Thread(target=self.animate_bullet, args=(self.troop_type, self.target_unit, self.xc, self.yc)))
                    #self.threads[-1].start() 
                    cleaned_futures = []
                    for future in self.futures:
                        if not future.done():
                            cleaned_futures.append(future)
                    self.futures = cleaned_futures
                    self.last_shot_time = current_time
                else:
                    #gotta get closer to hit.
                    self.target_in_range = False
                    #return  # Stop checking for more targets after hitting the first one
    
    def animate_bullet(self, troop_type, target_unit, x0, y0):
        bullet_id = []
        bulletspeed = TROOP_TYPES[troop_type]["bulletspeed"]
        distance = TROOP_TYPES[troop_type]["range"]
        steps = int(distance / bulletspeed)
        try:
            for i in range(TROOP_TYPES[troop_type]["shotcount"]):
                #get an endpoint for the bullet, accounting for spread
                x1, y1 = calculate_shot_line(x0, y0, target_unit.xc, target_unit.yc, TROOP_TYPES[troop_type]["range"], TROOP_TYPES[troop_type]["spread"])
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
            self.grow_bullets(bullet_id, steps, x0, y0)
        except Exception as e:
            print("abab",e)
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
                        d = self.check_bullet_hit(x0 + vx*b, y0 + vy*b, x0 + vx*(b+1), y0 + vy*(b+1))
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
                time.sleep(0.05)  # Adjust speed here
            time.sleep(0.2) #show the bullet a little longer for the user to see it.
            #self.lock.acquire()
            for bullet in bullet_id:
                self.canvas.delete(bullet[0])  # Remove the bullet line after animation
                #self.canvas.update()
            #self.lock.release()
            del bullet_id
        except Exception as e:
            print(e)
        self.simulshots += 1
        return
        
    def check_bullet_hit(self, x0, y0, x1, y1):
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
                for unit in allUnits.redUnits:
                    #bullets pass over dead units.
                    if unit.alive:
                        if (minx <= unit.x+UNIT_SIZE and maxx >= unit.x and miny <= unit.y+UNIT_SIZE and maxy >= unit.y):
                            d = ((x0 - unit.xc) ** 2 + (y0 - unit.yc) ** 2) ** 0.5
                            if d < lowd:
                                lowd = d
                                hitunit = unit
                            #return d
            elif self.team_color == "Red":
                for unit in allUnits.greenUnits:
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
            print(e)
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


        
