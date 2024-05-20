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
TROOP_TYPES = { #when making a troop type, the range must be divisible by the bullet speed to avoid overrange.
    "Canon": {
        "range": 200.0, #pixels
        "shotcolor": "blue",
        "damage": 20.0,
        "rate": 3.0, #seconds between shots
        "shotcount": 1,
        "spread": 5.0, #size of shot cone (degrees)
        "HP": 130.0,
        "speed": 1.5, #this is movement speed
        "bulletspeed": 50, 
        "simulshots": 1, #simultaneous shots. 1=wait for each bullet to hit before firing again.
        "cost": 56
        },
    "Chaingun":{
        "range": 150.0,
        "shotcolor": "orange",
        "damage": 3.0,
        "rate": 0.2,
        "shotcount": 1,
        "spread": 10.0,
        "HP": 105.0,
        "speed": 2,
        "bulletspeed": 50,
        "simulshots": 2,
        "cost": 42
        },
    "Missile":{
        "range": 300.0,
        "shotcolor": "red",
        "damage": 15.0,
        "rate": 8.0,
        "shotcount": 10,
        "spread": 20.0, 
        "HP": 100.0,
        "speed": 0.5,
        "bulletspeed": 15,
        "simulshots": 1,
        "cost": 41
        },
    "Laser":{
        "range": 250.0,
        "shotcolor": "purple",
        "damage": 1.0,
        "rate": 0.1,
        "shotcount": 1,
        "spread": 0.0, 
        "HP": 80.0,
        "speed": 1,
        "bulletspeed": 100,
        "simulshots": 3,
        "cost": 63
        },
    "shotgun":{
        "range": 100.0,
        "shotcolor": "pink",
        "damage": 3.0,
        "rate": 2.0,
        "shotcount": 20,
        "spread": 50.0, 
        "HP": 70.0,
        "speed": 2.5,
        "bulletspeed": 40,
        "simulshots": 1,
        "cost": 25
        },
    "homebase":{
        "range": 0.0,
        "shotcolor": "black",
        "damage": 0.0,
        "rate": 9999.0,
        "shotcount": 0,
        "spread": 0.0, 
        "HP": 500.0,
        "speed": 0.0,
        "bulletspeed": 1,
        "simulshots": 0,
        "cost": 9999
        }
    }

redUnits = []
greenUnits = []
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

    def __del__(self):
        self.executor.shutdown()

    def unit_AI(self):
        if self.alive:
            self.check_for_targets()
            if (not self.target_in_range) and (self.target_unit is not None):
                #print(self.target_in_range)
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
            self.executor.shutdown(wait=True)
    
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
        self.canvas.update()
        self.lock.release()
        #if self.target_id is not None:
            #self.canvas.delete(self.target_id)
            #self.target_id = None

    def check_for_targets(self):
        global greenUnits, redUnits, WINNER_DECLARED
        if self.team_color == "Green":
            units = redUnits
        else:
            units = greenUnits
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
                    print(self.team_color, "wins!")
            #if the target is in range, shoot it
            if (self.target_unit is not None) and (self.simulshots > 0):
                distance = ((self.xc - self.target_unit.xc) ** 2 + (self.yc - self.target_unit.yc) ** 2) ** 0.5
                if distance < (shoot_range-UNIT_SIZE):
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
        #print(vx*steps, vy*steps, distance)
        self.simulshots -= 1
        #animate the bullets
        self.grow_bullets(bullet_id, steps, x0, y0)
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
                            self.canvas.update()
                            #self.lock.release()
                            time.sleep(0.01)  # Adjust speed here
                        else:
                            #bullet hit = true. don't check this bullet anymore
                            bullet[4] = True
                            xmag = vx*b + bullet[1]*d
                            ymag = vy*b + bullet[2]*d
                            #use the unit vector to get the distance we should render the bullet
                            #self.lock.acquire()
                            self.canvas.coords(bullet[0], x0, y0, x0 + xmag, y0 + ymag)
                            self.canvas.update()
                            #self.lock.release() 
            time.sleep(0.2) #show the bullet a little longer for the user to see it.
            #self.lock.acquire()
            for bullet in bullet_id:
                self.canvas.delete(bullet[0])  # Remove the bullet line after animation
                self.canvas.update()
            #self.lock.release()
            del bullet_id
        except Exception as e:
            print(e)
        self.simulshots += 1
        return
        
    def check_bullet_hit(self, x0, y0, x1, y1):
        global redUnits, greenUnits
        minx = min(x0, x1)
        maxx = max(x0, x1)
        miny = min(y0, y1)
        maxy = max(y0, y1)
        
        if self.team_color == "Green":
            #print("gs")
            for unit in redUnits:
                #bullets pass over dead units.
                if unit.alive:
                    if (minx <= unit.x+UNIT_SIZE and maxx >= unit.x and miny <= unit.y+UNIT_SIZE and maxy >= unit.y):
                        d = ((x0 - unit.xc) ** 2 + (y0 - unit.yc) ** 2) ** 0.5
                        #self.lock.acquire()
                        #unit.remainingHP -= TROOP_TYPES[self.troop_type]["damage"]
                        #unit.hb_size = unit.hb_max * unit.remainingHP/TROOP_TYPES[unit.troop_type]["HP"]
                        #self.canvas.delete(self.healthbar)
                        unit.HPMod(0-TROOP_TYPES[self.troop_type]["damage"])
                        #self.lock.release()

                        return d
        elif self.team_color == "Red":
            for unit in greenUnits:
                if unit.alive:
                    if (minx <= unit.x+UNIT_SIZE and maxx >= unit.x and miny <= unit.y+UNIT_SIZE and maxy >= unit.y):
                        d = ((x0 - unit.xc) ** 2 + (y0 - unit.yc) ** 2) ** 0.5
                        unit.HPMod(0-TROOP_TYPES[self.troop_type]["damage"])
                        return d
        return 0

    
def update_all_units(units):
    global WINNER_DECLARED
    some_unit_alive = False
    for unit in units:
        if unit.alive:
            some_unit_alive = True
            unit.unit_AI()
    if not some_unit_alive and not WINNER_DECLARED:
        print("It's a draw!")
        WINNER_DECLARED = True

def main():
    global greenUnits, redUnits, WINNER_DECLARED, NUMBER_OF_UNITS, SYMMETRICAL_TEAMS
    root = tk.Tk()
    root.title("Tank Battles!")

    canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="white")
    canvas.pack()

    def makeNewUnits():
        units = []
        for _ in range(NUMBER_OF_UNITS):
            troop_type = random.choice(list(TROOP_TYPES.keys()))
            x = random.randint(UNIT_SIZE, int(WIDTH/2 - UNIT_SIZE))
            y = random.randint(UNIT_SIZE, HEIGHT - UNIT_SIZE)
            greenUnits.append(Unit(canvas, x, y, troop_type, "Green"))
            if SYMMETRICAL_TEAMS:
                redUnits.append(Unit(canvas, WIDTH-x-UNIT_SIZE, y, troop_type, "Red"))
        if not SYMMETRICAL_TEAMS:
            for _ in range(NUMBER_OF_UNITS):
                troop_type = random.choice(list(TROOP_TYPES.keys()))
                x = random.randint(int(WIDTH/2), WIDTH - UNIT_SIZE)
                y = random.randint(UNIT_SIZE, HEIGHT - UNIT_SIZE)
                redUnits.append(Unit(canvas, x, y, troop_type, "Red"))
        units = greenUnits + redUnits
        random.shuffle(units)
        return units

    units = makeNewUnits()

    def reset_units(event):
        nonlocal units, restart_button
        global WINNER_DECLARED, greenUnits, redUnits
        for unit in units:
            del unit
        #    unit.join_unit_threads()
        del units, greenUnits, redUnits
        canvas.update()
        greenUnits = []
        redUnits = []
        WINNER_DECLARED = False
        canvas.delete("all")
        restart_button = canvas.create_rectangle(5,5,100,25, fill='silver', tags='restart_button', state='hidden')
        canvas.tag_bind('restart_button', '<Button-1>', reset_units)
        units = makeNewUnits()
        canvas.update()
    
    restart_button = canvas.create_rectangle(5,5,100,25, fill='silver', tags='restart_button', state='hidden')
    canvas.tag_bind('restart_button', '<Button-1>', reset_units)
    
    def update_frame():
        global WINNER_DECLARED
        if not WINNER_DECLARED:
            update_all_units(units)
        else:
            canvas.itemconfigure(restart_button, state='normal')
            canvas.update()
        root.after(int(1000 / FPS), update_frame)
            

    update_frame()

    def close_window():
        """Closes the window and exits the program."""
        root.destroy()
    root.protocol("<Destroy>", close_window)
    root.mainloop()

if __name__ == "__main__":
    main()#this is so dumb
