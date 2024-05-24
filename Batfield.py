import tkinter as tk
from bfield_unit import Unit, allUnits, TROOP_TYPES, WINNER_DECLARED, TEAM_COLORS, UNIT_SIZE
import math
from tkinter.font import Font
from PIL import Image, ImageTk
from tkinter import messagebox
import time
import random


# Define global variables
WIDTH = 1024
HEIGHT = 768
FPS = 30  # Maximum frame rate
ylp = [1, 6, 10, 20, 25, 70, 75, 85, 88, 99] #percent y offsets for common elements
# 0 hb top, 1 bot, 2 flank top, 3 bot, 4 home top, 5 bot, 6 flank top, 7 bot, 8 ctl top, 9 bot

Flank_Unlock_Cost = 50
PLAYER_START_HP = 5000
CASH_PER_ROUND = 200
AI_CASH_HANDICAP = 20

#lists to carry the units on the battlefield
units = []
selected_troop_to_buy = None
#greenUnits and redUnits are borrowed from the unit file

# Initialize tkinter window
root = tk.Tk()
root.title("They're tanks, my dude.")
canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="white")
canvas.pack()


allUnits.setCanvas(canvas)

big_number_font = Font(weight='bold', size=60)
normal_font = Font(size = 10)

#useful object types####################################################
class Player:
    def __init__(self, canvas, healthbar, hbc, human = False):
        global PLAYER_START_HP
        self.hp = PLAYER_START_HP #sum of surviving enemy unit health subtracted from player health
        self.cash = 0 #cash is issued at setup for round 1
        self.canvas = canvas
        self.healthbar = healthbar
        self.hbc = hbc
        self.human = human
        self.alive = True

    def reinitialize(self):
        self.hp = PLAYER_START_HP
        self.cash = 0
        self.alive = True
        self.canvas.coords(self.healthbar, self.hbc[0],self.hbc[1],self.hbc[2], self.hbc[3])
        self.canvas.itemconfig(self.healthbar, state="normal")
        self.canvas.update()
        
    
    def loseHP(self, modifier):
        #returns true if player still alive, else false
        self.hp -= modifier
        if self.hp <= 0:
            self.canvas.itemconfig(self.healthbar, state="hidden")
            self.alive = False
            return self.alive
        else:
            self.canvas.coords(self.healthbar, self.hbc[0],self.hbc[1],self.hbc[0]+(self.hbc[2]-self.hbc[0])*self.hp/PLAYER_START_HP, self.hbc[3])
            self.canvas.update()
            self.alive = True
            return self.alive

    def changeCash(self, modifier):
        global cashtext
        
        #if sufficient cash, modifies cash and returns true. If not, just returns false.
        if (modifier < 0) and (self.cash < (0-modifier)):
            global WIDTH, HEIGHT
            self.canvas.after(50, lambda x=cashtextloc[0], y=cashtextloc[1]+15, mytext="Not enough money!", duration=2000: quick_message(x,y,mytext,duration))
            return False
        else:
            self.cash += modifier
            if self.human:
                self.canvas.itemconfig(cashtext, text="$"+str(self.cash))
            self.canvas.update()
            return True
        #update cash display

class Field_Region:
    #this is a square on the field where troops can be placed
    def __init__(self, canvas, x1, y1, x2, y2, team_color, click_callback, unlocked=True):
        #contains info about a region where the player can put troops
        #click callback should be a function that retrieves the mouse coords from the click event and drops a tank at them
        self.canvas = canvas
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.xc = ((max(x2,x1)-min(x2,x1))/2)+min(x2,x1)
        self.yc = ((max(y2,y1)-min(y2,y1))/2)+min(y2,y1)
        self.team_color = team_color
        self.click_callback = click_callback
        self.unlocked=unlocked
        if team_color == "green":
            self.interior = "PaleGreen"
        else:
            self.interior = "misty rose"
        self.rectangle = self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.interior)
        if click_callback is not None:
            self.canvas.tag_bind(self.rectangle, '<Button-1>', lambda event : self.click_callback(event))
        canvas.update()
    def bindCallback(mycallback):
        self.canvas.tag_bind(self.rectangle, '<Button-1>', lambda event : mycallback(event))
        canvas.update()
    def hide(self): #hide the placement area, like when the game starts
        self.canvas.itemconfigure(self.rectangle, state='hidden')
        canvas.update()
    def show(self):
        self.canvas.itemconfigure(self.rectangle, state='normal')
        canvas.update()


#Buttonkind#############################################
class Shop_Troop_Button:
    #a rectangle with the troop icon on it, and a tooltip for the troop info
    def __init__(self, canvas, x1, y1, x2, y2, troop_type, buytroop_func):
        global UNIT_SIZE, TROOP_TYPES
        self.troop_type = troop_type
        self.canvas = canvas
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.bwidth = x2-x1
        self.bheight = y2-y1
        self.xc = ((x2-x1)/2)+x1
        self.yc = ((y2-y1)/2)+y1
        self.buytroop_func = buytroop_func
        self.waittime = 100     #miliseconds
        self.wraplength = 180   #pixels
        self.wait_id = None
        self.tw = None
        #make the button rectangle
        self.button_id = self.canvas.create_rectangle(x1, y1, x2, y2, fill='gray', outline='black')
        self.canvas.tag_bind(self.button_id, "<Button-1>", self.button_click)
        self.canvas.tag_bind(self.button_id, "<Enter>", self.enter)
        self.canvas.tag_bind(self.button_id, "<Leave>", self.leave)
        #make a troop icon on it
        sprite_y = list(TROOP_TYPES.keys()).index(troop_type) * UNIT_SIZE
        self.unitsprite = ImageTk.PhotoImage(TEAM_COLORS["Green"].crop((0, sprite_y, UNIT_SIZE, sprite_y + UNIT_SIZE)))
        self.button_image = canvas.create_image(self.xc, self.yc, image=self.unitsprite, anchor=tk.CENTER)
        canvas.tag_bind(self.button_image, "<Button-1>", self.button_click)
        self.canvas.tag_bind(self.button_image, "<Enter>", self.enter)
        self.canvas.tag_bind(self.button_image, "<Leave>", self.leave)
        #make tooltip stuff
        self.tooltip_text = f"{troop_type}\n"
        for attr, value in TROOP_TYPES[troop_type].items():
            if attr != "simulshots":#this attribute name is embarrassing and I can't think of a better one.
                self.tooltip_text += f"{attr}: {value}\n"
        canvas.update()

    def button_click(self, event):
        self.leave()
        troop = self.troop_type
        self.set_selected()
        self.buytroop_func(troop)
        canvas.update()

    def set_selected(self, selected=True):
        if selected:
            self.canvas.itemconfig(self.button_id, outline='black')
        else:
            self.canvas.itemconfig(self.button_id, outline='light gray')

    def show(self):
        self.canvas.itemconfig(self.button_id, state="normal")
        self.canvas.itemconfig(self.button_image, state="normal")
        canvas.update()
        
    def hide(self):
        self.canvas.itemconfig(self.button_id, state="hidden")
        self.canvas.itemconfig(self.button_image, state="hidden")
        canvas.update()
        
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
        x = window_x + self.x2 + 10
        y = window_y + self.y1 - 100
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


class generic_Button:
    def __init__(self, canvas, x1, y1, x2, y2, text, callback):
        global normal_font
        self.canvas = canvas
        self.font = normal_font  
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.xc = ((x2-x1)/2)+x1
        self.yc = ((y2-y1)/2)+y1
        self.callback = callback
        self.text = text
        
        self.button_id = self.canvas.create_rectangle(x1, y1, x2, y2, fill='light gray', outline='green')
        self.canvas.tag_bind(self.button_id, "<Button-1>", lambda event: self.callback(event))
        # Create text object on the canvas
        self.text_id = self.canvas.create_text(self.xc, self.yc, text=self.text, font=self.font,anchor=tk.CENTER, fill='black')
        self.canvas.tag_bind(self.text_id, "<Button-1>", lambda event: self.callback(event))
        self.canvas.update()

    def hide(self):
        canvas.itemconfig(self.text_id, state="hidden")
        canvas.itemconfig(self.button_id, state="hidden")
    def show(self):
        canvas.itemconfig(self.text_id, state="normal")
        canvas.itemconfig(self.button_id, state="normal")


#Functions used by generic_Button###################################
def ready_countdown(num=3):
    global countdown_text
    num -= 1
    canvas.itemconfig(countdown_text, text=str(num))
    canvas.update()
    while num > 0:
        time.sleep(1)
        num -= 1
        canvas.itemconfig(countdown_text, text=str(num))
        canvas.update()
    root.after(1000, ai_opponent)
    return
            
def ready_pb_click(event):
    global root, countdown_text, readyButton, buy_NFlank_Btn, buy_SFlank_Btn
    answer = messagebox.askyesno("Really ready?", "All done placing troops?")
    if answer:
        readyButton.hide()
        for pb in buyTroopButtons:
            pb.hide()
        buy_NFlank_Btn.hide()
        buy_SFlank_Btn.hide()
        selected_troop_to_buy = None
        canvas.itemconfig(countdown_text, text="3")
        canvas.itemconfig(countdown_text, state="normal")
        root.after(1000, ready_countdown)
    
def Nflank_unlock_click(event):
    global canvas, Flank_Unlock_Cost, greenPlayer, buy_NFlank_Btn, greenFlankN
    answer = messagebox.askyesno("Really buy?", "Do you want to pay $\""+str(Flank_Unlock_Cost)+" to use the flank?")
    if answer:
        if greenPlayer.changeCash(0-Flank_Unlock_Cost):
            greenFlankN.unlocked = True
            buy_NFlank_Btn.hide()
            greenFlankN.show()

def Sflank_unlock_click(event):
    global canvas, Flank_Unlock_Cost, greenPlayer, buy_SFlank_Btn, greenFlankS
    answer = messagebox.askyesno("Really buy?", "Do you want to pay $\""+str(Flank_Unlock_Cost)+" to use the flank?")
    if answer:
        if greenPlayer.changeCash(0-Flank_Unlock_Cost):
            greenFlankS.unlocked = True
            buy_SFlank_Btn.hide()
            greenFlankS.show()            
                
#click functions
def buy_troop_button_press(trooptype):
    #Select a troop type to buy from the shop
    global selected_troop_to_buy
    #shop buttons. selects a unit to place on the map. buy when placed.
    
    for btn in buyTroopButtons:
        if not (btn.troop_type == trooptype):
            
            btn.set_selected(False)
    selected_troop_to_buy = trooptype
    
def place_buy_unit(event):
    #having selected a troop type already, select a location to put it on the map
    global canvas, selected_troop_to_buy, allUnits
    # Place a troop of the specified type at the given position on the grid
    # subtract greenbacks
    if selected_troop_to_buy is not None:
        answer = messagebox.askyesno("Really buy?", "Do you want to buy and place a \""+str(selected_troop_to_buy)+"\"?")
        if answer:
            if greenPlayer.changeCash(0-TROOP_TYPES[selected_troop_to_buy]["cost"]):
                #center a new unit on the click
                allUnits.add_green(event.x-(UNIT_SIZE/2), event.y-(UNIT_SIZE/2), selected_troop_to_buy)
    pass


#other useful functions...
def quick_message(x,y,mytext, duration=2000):
    #make a tooltip type message anywhere
    global canvas
    window_x = canvas.winfo_rootx()
    window_y = canvas.winfo_rooty()
    x = window_x + x
    y = window_y + y
    # creates a toplevel window
    tw = tk.Toplevel(canvas)
    # Leaves only the label and removes the app window
    tw.wm_overrideredirect(True)
    tw.wm_geometry("+%d+%d" % (x, y))
    label = tk.Label(tw, text=mytext, justify='left',
                   background="#ffffff", relief='solid', borderwidth=1,
                   wraplength = 180)
    label.pack(ipadx=1)
    canvas.after(duration, lambda pop=tw: hide_quick_message(pop))

def hide_quick_message(tw):
    #hide a tooltip
    te = tw
    tw= None
    if te:
        te.destroy()

#Instances of the above types################################################
# UI objects

ylayout = [HEIGHT*ypct/100 for ypct in ylp] #percent y offsets for common elements
smallxoffset = WIDTH/100 #percent of window
bigxoffset = WIDTH*3/100 #percent of window
x_end = WIDTH/2-smallxoffset

#green player's cash is the only one seen, because red is an AI.
cashtextloc = [WIDTH/2, ylayout[0]+(ylayout[1]-ylayout[0])/2]
cashtext = canvas.create_text(cashtextloc[0], cashtextloc[1], text="$"+str(CASH_PER_ROUND), font=normal_font,anchor=tk.CENTER, fill='black')
cashtextwidth = normal_font.measure("$00000")

#left side
greenHealthbar = canvas.create_rectangle(smallxoffset, ylayout[0], x_end-(cashtextwidth/2), ylayout[1], fill='green')
redFlankN = Field_Region(canvas, smallxoffset, ylayout[2], x_end, ylayout[3], 'red', None)
greenHome = Field_Region(canvas, bigxoffset, ylayout[4], x_end, ylayout[5], 'green', place_buy_unit)
redFlankS = Field_Region(canvas, smallxoffset, ylayout[6], x_end, ylayout[7], 'red', None)
#right side
redHealthbar = canvas.create_rectangle(WIDTH-smallxoffset, ylayout[0], WIDTH-x_end+(cashtextwidth/2), ylayout[1], fill='red')
greenFlankN = Field_Region(canvas, WIDTH-x_end, ylayout[2], WIDTH-smallxoffset, ylayout[3], 'green', place_buy_unit)
redHome = Field_Region(canvas, WIDTH-x_end, ylayout[4], WIDTH-bigxoffset, ylayout[5], 'red', None)
greenFlankS = Field_Region(canvas, WIDTH-x_end, ylayout[6],WIDTH-smallxoffset , ylayout[7], 'green', place_buy_unit)

#Player objects
#make sure the coordinates passed here are the same as in the healthbar instantiation above
greenPlayer = Player(canvas, greenHealthbar, [smallxoffset, ylayout[0], x_end-(cashtextwidth/2), ylayout[1]], True)
redPlayer = Player(canvas, redHealthbar, [WIDTH-smallxoffset, ylayout[0], WIDTH-x_end+(cashtextwidth/2), ylayout[1]])

#unit placement on flank has to be unlocked in-game
greenFlankN.hide() 
greenFlankS.hide()

#class Shop_Troop_Button:
#    #a rectangle with the troop icon on it, and a tooltip for the troop info
#    def __init__(self, canvas, x1, y1, x2, y2, troop_type, buytroop_func):
#shop buttons for the setup phase
#change the buttonspace to make room for more buttons if needed
bspace = [smallxoffset, ylayout[8], WIDTH-smallxoffset, ylayout[9]] #x1, y1, x2, y2
buttonwidth = (bspace[2]-bspace[0])/(len(TROOP_TYPES.keys())) #The right-hand button will be "ready"
buyTroopButtons = []
for i in range(len(TROOP_TYPES.keys())-1): #less 2 for the homebase, and to make room for a "done" button
    buyTroopButtons.append(Shop_Troop_Button(canvas, bspace[0]+(i*buttonwidth), bspace[1], bspace[0]+((i+1)*buttonwidth),bspace[3],list(TROOP_TYPES.keys())[i],buy_troop_button_press))

#misc shop buttons
readyButton = generic_Button(canvas, bspace[0]+(buttonwidth*(len(TROOP_TYPES.keys())-1)), bspace[1], bspace[0]+(buttonwidth*(len(TROOP_TYPES.keys()))), bspace[3], "Ready", ready_pb_click)
def get_flankbtn_coords(xc, yc, font, fbt):
    lw = font.measure(fbt)+5
    lwc = lw/2
    return [xc-lwc, yc-lwc, xc+lwc, yc+lwc]
flankbuttontext = "Unlock $"+str(Flank_Unlock_Cost)
flankbuttoncoords = get_flankbtn_coords(greenFlankN.xc, greenFlankN.yc, normal_font, flankbuttontext)
buy_NFlank_Btn = generic_Button(canvas, flankbuttoncoords[0], flankbuttoncoords[1], flankbuttoncoords[2], flankbuttoncoords[3], flankbuttontext, Nflank_unlock_click)
flankbuttoncoords = get_flankbtn_coords(greenFlankS.xc, greenFlankS.yc, normal_font, flankbuttontext)
buy_SFlank_Btn = generic_Button(canvas, flankbuttoncoords[0], flankbuttoncoords[1], flankbuttoncoords[2], flankbuttoncoords[3], flankbuttontext, Sflank_unlock_click)

countdown_text = canvas.create_text(WIDTH/2, HEIGHT/2, text="3", font=big_number_font, fill='black', anchor=tk.CENTER, state="hidden")

#GUI Functions##############################################
def setup_battlefield(new_battlefield = False):
    global countdown_text, WINNER_DECLARED, allUnits, greenPlayer, redPlayer, greenHome, redHome, canvas
    canvas.itemconfig(countdown_text, state="hidden")
    canvas.itemconfig(countdown_text, text = "3")
    #clear the screen and delete everything
    if new_battlefield:
        allUnits.clear_units()
        allUnits.add_green(greenHome.xc-(UNIT_SIZE/2), greenHome.yc-(UNIT_SIZE/2), list(TROOP_TYPES.keys())[-1])
        allUnits.add_red(redHome.xc-(UNIT_SIZE/2), redHome.yc-(UNIT_SIZE/2), list(TROOP_TYPES.keys())[-1])
        #initialize the units for each player. Add a homebase unit to each.
        greenFlankS.unlocked = False
        greenFlankS.hide()
        greenFlankN.unlocked = False
        greenFlankN.hide()
        redFlankN.unlocked = False
        redFlankS.unlocked = False
        greenPlayer.reinitialize()
        redPlayer.reinitialize()
    else:
        allUnits.reinitialize_units()
    greenPlayer.changeCash(CASH_PER_ROUND)
    redPlayer.changeCash(CASH_PER_ROUND+AI_CASH_HANDICAP)
    WINNER_DECLARED = False
    #canvas.delete("all")
    canvas.update()
    setup_phase()
    pass



# Player Setup functions
def setup_phase():
    
    global READY, redFlankN, greenHome, redFlankS, redHome, greenFlankN, greenFlankS, buy_NFlank_Btn, buy_SFlank_Btn
    canvas.itemconfig(redFlankN, state='normal')
    canvas.itemconfig(greenHome, state='normal')
    canvas.itemconfig(redFlankS, state='normal')
    canvas.itemconfig(redHome, state='normal')
    if greenFlankN.unlocked:
        canvas.itemconfig(greenFlankN, state='normal')
    else:
        buy_NFlank_Btn.show()
    if greenFlankS.unlocked:
        canvas.itemconfig(greenFlankS, state='normal')
    else:
        buy_SFlank_Btn.show()

    readyButton.show()
    for pb in buyTroopButtons:
        pb.show()
    
    
    # Handle unit purchases and placement.
    # - Show some buttons to purchase units
    # - Show costs and funds for the units
    # - when the "ready" button is pressed, hide all that stuff

def ai_opponent():
    global canvas, redPlayer, redHome, redFlankN, redFlankS, Flank_Unlock_Cost, UNIT_SIZE    # while there's money in the ai opponent bank
    #   spend it on tanks, randomly place on board
    while True:
        #decide whether to buy a flank or a unit
        decision = random.choice(["flank", "troop"])
        if (decision == "flank") and (redPlayer.cash > Flank_Unlock_Cost) and (not (redFlankS.unlocked and redFlankN.unlocked)):
            decision = ["n", "s"]
            if ((decision == "n") and (not redFlankN.unlocked)) or redFlankS.unlocked:
                if redPlayer.changeCash(0-Flank_Unlock_Cost):
                    redFlankN.unlocked = True
                    #print("unlocked North")
            elif not redFlankS.unlocked:
                if redPlayer.changeCash(0-Flank_Unlock_Cost):
                    redFlankS.unlocked = True
                    #print("unlocked South")
        else:
            #if the flanks are already unlocked, or there isn't enough cash for it, try troops.
            #make a list of the troops we can afford.
            troop_choices = [troop for troop, info in TROOP_TYPES.items() if redPlayer.cash > info["cost"]]
            if troop_choices:
                troop_type = random.choice(troop_choices)
                if redPlayer.changeCash(0-TROOP_TYPES[troop_type]["cost"]):
                    troop_type = random.choice(list(troop_choices))
                    #decide which location to put the troops
                    locOptions = [[redHome.x1, redHome.y1, redHome.x2, redHome.y2]]
                    if redFlankS.unlocked:
                        locOptions.append([redFlankS.x1, redFlankS.y1, redFlankS.x2, redFlankS.y2])
                    if redFlankN.unlocked:
                        locOptions.append([redFlankN.x1, redFlankN.y1, redFlankN.x2, redFlankN.y2])
                    
                    #pick an unlocked region and drop a unit in it.
                    loc = random.choice(locOptions)
                    x = random.randint(int(loc[0]), int(loc[2]-UNIT_SIZE))
                    y = random.randint(int(loc[1]), int(loc[3]-UNIT_SIZE))
                    allUnits.add_red(x, y, troop_type)

            else:
                break #no more options for things to buy
        
        
    resolve_battle()

# Battle Resolution functions
def resolve_battle():
    global allUnits
    canvas.itemconfig(countdown_text, state="hidden")
    random.shuffle(units)

    allUnits.reset_shot_times()
    
    def update_frame():
        global WINNER_DECLARED, allUnits
        #list the live tanks; not including the castle
        if len(allUnits.redUnits) > 1:
            live_red_units = [tank for tank in allUnits.redUnits[1:] if tank.alive]
            #live_red_units = [tank for tank in allUnits.redUnits if tank.alive]
        else:
            live_red_units = []
        if len(allUnits.greenUnits) > 1:
            live_green_units = [tank for tank in allUnits.greenUnits[1:] if tank.alive]
            #live_green_units = [tank for tank in allUnits.greenUnits if tank.alive]
        else:
            live_green_units = []

        #print("red ones", allUnits.redUnits)
        #print("green ones", allUnits.greenUnits)

        #check if either player won (index 0 is the castle)
        #win conditions: kill all enemy units, or the enemy castle.
        if (not (allUnits.greenUnits[0].alive or allUnits.redUnits[0].alive)) or (not (live_green_units or live_red_units)):
            #draw conditions: both towers dead, or all tanks dead.
            root.after(int(1000 / FPS), lambda winner="Draw": show_winner(winner))
            return
        elif (not allUnits.greenUnits[0].alive) or (not live_green_units):
            root.after(int(1000 / FPS), lambda winner="Red Wins": show_winner(winner))
            return
        elif (not allUnits.redUnits[0].alive) or (not live_red_units):
            root.after(int(1000 / FPS), lambda winner="Green Wins": show_winner(winner))
            return

        #shuffle the living units
        units_to_check = live_green_units + live_red_units
        random.shuffle(units_to_check)

        #run the unit AI's
        for tank in units_to_check:
            tank.unit_AI()
        #keep doing update_frame until someone wins.
        canvas.update()
        root.after(int(1000/FPS), update_frame)

    if (len(allUnits.greenUnits)>1) or (len(allUnits.redUnits)>1):
        update_frame()
    else:
        show_winner()
            
    # while not check_game_over():
    # .for i in range(len(maxunits)):
    # ..Execute unit AI (first_team[i])
    # ..Execute unit AI (second_team[i])
    # .destroy dead units
    # .delete bullet lines
    pass

def show_winner(winner):
    global countdown_text, redPlayer, greenPlayer, allUnits
    # show who won the battle
    # subtract from player HP
    HPloss = 0
    gameover = False
    if winner == "Green Wins":
        for tank in allUnits.greenUnits[1:]:
            if tank.alive:
                HPloss += tank.remainingHP
        redPlayer.loseHP(HPloss)
        if not redPlayer.alive:
            gameover = True
            winner += " the Game"
    if winner == "Red Wins":
        for tank in allUnits.redUnits[1:]:
            if tank.alive:
                HPloss += tank.remainingHP
        greenPlayer.loseHP(HPloss)
        if not greenPlayer.alive:
            gameover = True
            winner += " the Game"
    
    canvas.itemconfig(countdown_text, text=winner)
    canvas.itemconfig(countdown_text, state="normal")


    # wait a few seconds and then reset the battlefield
    root.after(4000, lambda gameover=gameover: setup_battlefield(gameover))
    pass


# Game initialization
setup_battlefield(True)
# Main game loop (player turns, troop movements, battles, game-over checks)
# Display game-over message and allow players to start a new game



root.mainloop()



