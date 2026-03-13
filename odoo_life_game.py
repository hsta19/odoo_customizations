from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import unlit_shader
import random

app = Ursina(title='Odoo Life', borderless=False)
window.color = Color(0.15, 0.22, 0.35, 1)
US = unlit_shader

# ── Color helper ─────────────────────────────────────
def C(r, g, b, a=1.0):
    return Color(r/255, g/255, b/255, a)

def box(pos, sc, col, solid=False, parent=scene):
    e = Entity(model='cube', position=pos, scale=sc, color=col,
               shader=US, collider='box' if solid else None, parent=parent)
    return e

# ── Palette ──────────────────────────────────────────
PURPLE   = C(114, 46, 209)
HEAD_COL = C(220, 180, 140)
MGR_COL  = C(200, 160, 50)
DEPT_COL = {
    'Sales': C(60,  100, 180),
    'BSA':   C(40,  130, 120),
    'FSS':   C(160, 90,  40),
    'HR':    C(140, 60,  180),
}

# ════════════════════════════════════════════════════
# GAME STATE GLOBALS
# ════════════════════════════════════════════════════
game_state   = 'create'   # create / work / evening / home / bar
current_floor = 1          # 1 or 2 (within work state)

# ── Player Stats ─────────────────────────────────────
stats = {
    'name':   'Player',
    'dept':   'Sales',
    'xp':     0,
    'level':  1,
    'money':  500,
    'energy': 100,
    'mood':   70,
}
LEVEL_TITLES  = {1:'Junior', 2:'Mid-level', 3:'Senior', 4:'Lead'}
XP_PER_LEVEL  = [0, 100, 300, 600]

# ── Day / Time ────────────────────────────────────────
day          = 1
hour         = 9.0
day_names    = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
WORK_START   = 9.0
WORK_END     = 18.0
TIME_SPEED   = 60       # 1 real sec = 1 in-game minute
evening_triggered = False

# ── Task State ────────────────────────────────────────
sitting_at_desk   = False
task_panel        = None
task_active       = False
desk_work_timer   = 0.0   # in-game minutes since last task
TASK_INTERVAL     = 2.0   # real seconds between tasks while sitting

TASKS = {
    'Sales': [
        {'text': 'Follow up with a client',    'xp': 40, 'money': 15},
        {'text': 'Update the CRM pipeline',    'xp': 35, 'money': 12},
        {'text': 'Send a proposal email',       'xp': 50, 'money': 20},
        {'text': 'Qualify a new lead',          'xp': 45, 'money': 18},
        {'text': 'Log a call in the CRM',       'xp': 25, 'money':  8},
    ],
    'BSA': [
        {'text': 'Write a functional spec',      'xp': 50, 'money': 20},
        {'text': 'Map a business process',       'xp': 45, 'money': 18},
        {'text': 'Review user requirements',     'xp': 40, 'money': 15},
        {'text': 'Update project documentation', 'xp': 30, 'money': 10},
        {'text': 'Facilitate a client workshop', 'xp': 60, 'money': 25},
    ],
    'FSS': [
        {'text': 'Close a support ticket',       'xp': 35, 'money': 12},
        {'text': 'Configure an Odoo module',     'xp': 50, 'money': 20},
        {'text': 'Respond to a client query',    'xp': 30, 'money': 10},
        {'text': 'Reproduce a reported bug',     'xp': 45, 'money': 18},
        {'text': 'Write a how-to guide',         'xp': 40, 'money': 15},
    ],
}

current_task       = None

# ── Friendship ───────────────────────────────────────
friendship = {}
bar_talked_tonight = set()  # NPC names talked to at bar this evening

# ── Map entity groups ─────────────────────────────────
floor1_entities = []
floor2_entities = []
home_entities   = []
bar_entities    = []

# ── Spawn points ─────────────────────────────────────
SPAWN = {
    'floor1': Vec3(12, 1.5, 5),
    'floor2': Vec3(10, 13.5, 13),   # Fix 1: raised so player falls and lands properly
    'home':   Vec3(8,  1.5, 6),
    'bar':    Vec3(12, 1.5, 3),
}

# ════════════════════════════════════════════════════
# ROOM BUILDER
# ════════════════════════════════════════════════════
def make_room(ox, oy, oz, w, d, h, fc, wc, cc, accent=True, group=None):
    cx, cz = ox+w/2, oz+d/2
    ents = [
        box((cx, oy+0.15,  cz), (w, 0.3,  d), fc, True),
        box((cx, oy+h+0.15,cz), (w, 0.3,  d), cc),
        box((cx, oy+h/2,   oz), (w, h,  0.3), wc, True),
        box((cx, oy+h/2, oz+d), (w, h,  0.3), wc, True),
        box((ox, oy+h/2,   cz), (0.3, h, d),  wc, True),
        box((ox+w,oy+h/2,  cz), (0.3, h, d),  wc, True),
    ]
    if accent:
        ents.append(box((cx, oy+h-0.3, oz+d-0.2), (w, 0.4, 0.1), PURPLE))
    # ceiling light strips (two rows)  -- Change 4
    for lz_off in (d*0.3, d*0.7):
        ents.append(box((cx, oy+h-0.05, oz+lz_off), (w*0.7, 0.08, 0.4), C(255,250,220)))
    if group is not None:
        group.extend(ents)
    return ents

# ════════════════════════════════════════════════════
# FLOOR 1: LOBBY + CAFETERIA  (y=0)
# ════════════════════════════════════════════════════
def _add1(e):
    floor1_entities.append(e)
    return e

Y1 = 0
make_room(0, Y1, 0, 50, 26, 6, C(55,55,70), C(70,70,95), C(110,110,130), group=floor1_entities)

floor1_entities += [
    box((12, Y1+0.9, 20),  (7,   0.9, 1.8), C(80,50,30),   True),
    box((12, Y1+1.4, 20),  (7.3, 0.06,2),   C(110,70,40)),
    box((12, Y1+2.8, 25.7),(9,  1.2,  0.1), PURPLE),
]
for xi in (4, 7, 10, 13):
    floor1_entities += [
        box((xi, Y1+0.45, 8), (0.8,0.08,0.8), C(60,60,200), True),
        box((xi, Y1+0.85, 8.4),(0.8,0.7,0.08),C(60,60,200)),
    ]
for px, pz in ((2,22),(22,22)):
    floor1_entities.append(box((px, Y1+0.9, pz), (0.7,1.8,0.7), C(40,120,40), True))

# Divider
floor1_entities += [
    box((25, Y1+3, 3),  (0.3, 6, 6),  C(80,80,110), True),
    box((25, Y1+3, 21), (0.3, 6, 10), C(80,80,110), True),
]

# Cafeteria
floor1_entities += [
    box((38, Y1+1.05,23),(10,1,2),    C(110,85,60),   True),
    box((38, Y1+1.55,23),(10.2,.07,2.2),C(200,185,160)),
]
for fi, fc in enumerate((C(255,200,100),C(180,100,80),C(120,180,80))):
    floor1_entities.append(box((33+fi*3, Y1+1.6,22.5),(2,.05,.8),fc))
for row in range(2):
    for col in range(3):
        tx, tz = 28+col*6, 5+row*6
        floor1_entities.append(box((tx,Y1+0.72,tz),(2.5,.08,2.5),C(200,175,140),True))
        for dx,dz in ((1.3,0),(-1.3,0),(0,1.3),(0,-1.3)):
            floor1_entities.append(box((tx+dx,Y1+0.42,tz+dz),(.6,.08,.6),C(190,80,80),True))

# Cafeteria serving counter (interact point)
CAFETERIA_POS = Vec3(38, Y1+1.5, 23)

# Exit door (south wall, lobby)
floor1_entities.append(box((12, Y1+1.5, 0.5), (1.5, 2.5, 0.3), C(139,90,43), True))
EXIT_DOOR_POS = Vec3(12, Y1+1.5, 1)

# Staircase to Floor 2
for s in range(5):
    floor1_entities.append(
        box((47+s*.5, Y1+0.2+s*.7, 13),(1.5, .3+s*.7, 1.5), C(150,130,110), True)
    )
STAIR_F1 = Vec3(47, 1, 13)
STAIR_F2 = Vec3(47, 11, 13)

# ── Lobby improvements (Change 5) ──────────────────────
# Carpet zone under lobby seating
floor1_entities.append(box((8, Y1+0.31, 10), (20, 0.04, 12), C(70,50,110)))

# Wall windows (north wall, lobby side) - 3 window frames
for wx in (5, 12, 19):
    floor1_entities += [
        box((wx, Y1+3.0, 25.5), (3.5, 3.0, 0.12), C(160,190,220)),  # glass
        box((wx, Y1+3.0, 25.4), (3.7, 3.2, 0.08), C(90,90,120)),    # frame
    ]

# Reception desk nameplate
floor1_entities.append(box((12, Y1+1.48, 18.8), (3, 0.15, 0.08), C(220,200,255)))

# Odoo logo area above reception (purple bar with lighter center)
floor1_entities += [
    box((12, Y1+2.8, 25.65), (9,  1.2, 0.1), PURPLE),
    box((12, Y1+2.8, 25.60), (5,  0.7, 0.08), C(140,80,220)),
]

# Reception computer
floor1_entities += [
    box((12, Y1+1.55, 19.5), (0.7,0.4,0.05), C(20,20,30)),
    box((12, Y1+1.55, 19.48),(0.58,0.3,0.04),C(40,80,150)),
]

# Extra plants (potted, lobby corners)
for px, pz in ((1,1),(23,1),(1,24),(23,24)):
    floor1_entities += [
        box((px, Y1+0.5, pz), (0.8,0.8,0.8), C(80,55,30), True),  # pot
        box((px, Y1+1.2, pz), (0.6,0.9,0.6), C(30,110,30)),         # plant
        box((px, Y1+1.6, pz+0.3),(0.3,0.5,0.3),C(40,130,40)),
    ]

# Ceiling lights floor 1 are added by make_room already

# ── Cafeteria improvements (Change 6) ──────────────────
# Cafeteria wall menu board
floor1_entities += [
    box((38, Y1+4.0, 25.6), (14, 2.5, 0.1), C(40,60,40)),   # green chalkboard
    box((38, Y1+4.0, 25.5), (12, 2.0, 0.08), C(55,80,55)),   # inner
]
# Cafeteria serving station shelves
for sx in (31, 35, 39, 43):
    floor1_entities.append(box((sx, Y1+2.0, 23.8), (2.5, 0.08, 0.6), C(140,100,60)))

# Trash bin near exit of cafeteria
floor1_entities.append(box((26, Y1+0.6, 3), (0.5,1.0,0.5), C(50,60,50), True))

# ════════════════════════════════════════════════════
# FLOOR 2: DEPARTMENTS  (y=10)
# ════════════════════════════════════════════════════
Y2 = 10
make_room(0, Y2, 0, 56, 26, 6, C(42,45,58), C(58,62,78), C(90,95,115), group=floor2_entities)

# Fix 1: extra invisible solid safety floor after make_room
floor2_entities.append(box((28, Y2+0.5, 13), (56, 0.2, 26), C(0,0,0,0), True))

for ox, col in ((0,C(45,52,78)),(14,C(42,62,65)),(28,C(62,55,45)),(42,C(55,45,70))):
    floor2_entities.append(box((ox+7, Y2+0.32, 13),(14,.06,26),col))

for name, ox in [('SALES',0),('BSA',14),('FSS',28),('HR',42)]:
    floor2_entities.append(box((ox+7, Y2+3.8, 0.25),(10,.45,.1), PURPLE))

for dx in (14, 28, 42):
    floor2_entities.append(box((dx, Y2+1.5, 13), (.2, 3, 20), C(130,140,160,.5)))

for s in range(5):
    floor2_entities.append(
        box((47+s*.5, Y2+0.2+s*.7, 13),(1.5,.3+s*.7,1.5),C(150,130,110),True)
    )

# ── Better desks (Change 3) ──────────────────────────
def make_desk(x, z, y=Y2, empty=False, group=None):
    desk_col = C(90,65,35) if empty else C(130,95,50)
    ents = []
    # desktop surface
    ents.append(box((x, y+0.78, z), (2.1, 0.08, 1.1), desk_col, True))
    # desk legs (4 corners)
    for lx, lz in ((-0.9,-0.4),(0.9,-0.4),(-0.9,0.4),(0.9,0.4)):
        ents.append(box((x+lx, y+0.38, z+lz), (0.1,0.76,0.1), C(70,50,25), True))
    if not empty:
        # monitor stand
        ents.append(box((x, y+0.84, z+0.35), (0.08,0.28,0.08), C(40,40,40)))
        # monitor screen (dark with blue glow tint)
        ents.append(box((x, y+1.22, z+0.38), (0.85,0.5,0.06), C(20,20,35)))
        # screen glow (slightly lighter blue inner)
        ents.append(box((x, y+1.22, z+0.36), (0.72,0.38,0.04), C(40,80,160)))
        # keyboard
        ents.append(box((x, y+0.82, z-0.05), (0.8,0.03,0.35), C(60,60,65)))
        # mouse
        ents.append(box((x+0.55, y+0.82, z+0.05), (0.12,0.03,0.2), C(50,50,55)))
        # coffee mug
        ents.append(box((x-0.7, y+0.9, z+0.2), (0.15,0.22,0.15), C(200,80,40)))
        # mug top (darker opening)
        ents.append(box((x-0.7, y+1.01, z+0.2), (0.13,0.04,0.13), C(30,15,5)))
        # chair
        ents.append(box((x, y+0.42, z-0.65), (0.75, 0.07, 0.7), C(45,45,55), True))
        ents.append(box((x, y+0.82, z-0.95), (0.75, 0.65, 0.08), C(45,45,55)))
        # chair legs
        for clx, clz in ((-0.3,-0.25),(0.3,-0.25),(-0.3,0.25),(0.3,0.25)):
            ents.append(box((x+clx, y+0.18, z-0.65+clz),(0.07,0.42,0.07),C(60,60,70),True))
    else:
        # empty desk: blank mousepad, no monitor
        ents.append(box((x, y+0.82, z-0.05), (1.5,0.03,0.75), C(210,210,220)))
        # still has a chair
        ents.append(box((x, y+0.42, z-0.65), (0.75,0.07,0.7), C(45,45,55), True))
        ents.append(box((x, y+0.82, z-0.95), (0.75,0.65,0.08), C(45,45,55)))
        for clx, clz in ((-0.3,-0.25),(0.3,-0.25),(-0.3,0.25),(0.3,0.25)):
            ents.append(box((x+clx, y+0.18, z-0.65+clz),(0.07,0.42,0.07),C(60,60,70),True))
    if group is not None:
        group.extend(ents)
    return ents

# ── Better manager area (Change 8) ───────────────────
def make_manager_area(ox, y=Y2, group=None):
    cx = ox + 7
    ents = [
        # glass partition walls (slightly tinted)
        box((cx,     y+2.0, 22.5), (11.5, 3.5, 0.15), C(180,200,230, 0.4)),
        box((ox+0.8, y+2.0, 20.5), (0.15, 3.5, 4.5),  C(180,200,230, 0.4)),
        box((ox+13.2,y+2.0, 20.5), (0.15, 3.5, 4.5),  C(180,200,230, 0.4)),
        # carpet inside manager area
        box((cx, y+0.33, 21.5),(11, 0.05, 6), C(80,60,100)),
    ]
    ents += make_desk(cx, 21, y)
    if group is not None:
        group.extend(ents)

DESK_ROWS = [(2,6),(6,6),(10,6),(2,13),(6,13)]
EMPTY_DESK = (10,13)

# Player desk positions per dept
PLAYER_DESK_POS = {
    'Sales': Vec3(10,  Y2+1.5, 13),
    'BSA':   Vec3(24,  Y2+1.5, 13),
    'FSS':   Vec3(38,  Y2+1.5, 13),
    'HR':    Vec3(52,  Y2+1.5, 13),
}
DEPT_OX = {'Sales':0,'BSA':14,'FSS':28,'HR':42}

for dept, dept_ox in DEPT_OX.items():
    for (lx, lz) in DESK_ROWS:
        make_desk(dept_ox+lx, lz, group=floor2_entities)
    make_desk(dept_ox + EMPTY_DESK[0], EMPTY_DESK[1], empty=True, group=floor2_entities)
    make_manager_area(dept_ox, group=floor2_entities)

# ── Dept improvements (Change 7) ─────────────────────
# Wall-mounted screens above each dept sign (large monitor look)
for ox, dcol in ((0,DEPT_COL['Sales']),(14,DEPT_COL['BSA']),(28,DEPT_COL['FSS']),(42,DEPT_COL['HR'])):
    floor2_entities += [
        box((ox+7, Y2+4.5, 0.3), (11, 2.2, 0.12), C(20,20,30)),   # screen bezel
        box((ox+7, Y2+4.5, 0.25),(9.5,1.7, 0.08), dcol),            # screen content (dept color)
    ]

# Desk lamps on manager desks
for ox in (0, 14, 28, 42):
    cx = ox + 7
    floor2_entities += [
        box((cx+0.7, Y2+0.88, 21.3),(0.06,0.5,0.06), C(180,180,180)),  # lamp post
        box((cx+0.7, Y2+1.15, 21.2),(0.3,0.08,0.25), C(255,240,180)),  # lamp shade
    ]

# Whiteboard on back wall (manager area) per dept
for ox in (0, 14, 28, 42):
    floor2_entities += [
        box((ox+7, Y2+3.5, 25.6),(10, 2.5, 0.12), C(240,240,245)),  # whiteboard
        box((ox+7, Y2+3.5, 25.5),( 9, 2.2, 0.08), C(255,255,255)),  # surface
    ]

# ════════════════════════════════════════════════════
# HOME MAP  (small apartment)
# ════════════════════════════════════════════════════
HX, HY, HZ = 200, 0, 0   # offset so it doesn't overlap

make_room(HX, HY, HZ, 16, 12, 4, C(200,190,170), C(180,170,150), C(230,220,200),
          accent=False, group=home_entities)

# ── Home improvements (Change 9) ─────────────────────
# Rug
home_entities.append(box((HX+8, HY+0.32, HZ+7), (10, 0.04, 7), C(140,80,80)))

# Bed frame (wood), mattress, pillow, blanket
home_entities += [
    box((HX+3, HY+0.2,  HZ+9),   (4.0, 0.35, 2.5), C(100,70,35), True),  # bed frame
    box((HX+3, HY+0.55, HZ+9),   (3.6, 0.3,  2.2), C(220,215,230)),       # mattress
    box((HX+3, HY+0.72, HZ+9),   (3.4, 0.18, 2.0), C(180,160,200)),       # blanket
    box((HX+3, HY+0.78, HZ+10.2),(3.0, 0.22, 0.5), C(240,235,255)),       # pillow
    # bedside table
    box((HX+5.2, HY+0.5, HZ+9),  (0.7,0.8,0.7), C(110,75,35), True),
    box((HX+5.2, HY+0.92,HZ+9),  (0.75,0.06,0.75),C(130,90,45)),
    # alarm clock on bedside
    box((HX+5.2, HY+1.0, HZ+9),  (0.25,0.2,0.12),C(200,50,50)),
]
BED_POS = Vec3(HX+3, HY+1.5, HZ+9)

# Couch (L-shape feel) + side table
home_entities += [
    box((HX+9,  HY+0.3, HZ+8),   (3.5,0.55,1.6),  C(140,90,50),  True),   # couch base
    box((HX+9,  HY+0.72,HZ+8),   (3.5,0.3, 1.6),  C(180,120,70)),          # cushion top
    box((HX+9,  HY+0.72,HZ+9.0), (3.5,0.5, 0.18), C(160,105,60)),          # back rest
    box((HX+7.2,HY+0.5, HZ+8),   (0.18,0.65,1.4), C(130,85,45)),           # left arm
    box((HX+10.8,HY+0.5,HZ+8),   (0.18,0.65,1.4), C(130,85,45)),           # right arm
    # side table with lamp
    box((HX+13, HY+0.5, HZ+8),   (0.9,0.8,0.9),   C(90,65,35),   True),
    box((HX+13, HY+0.92,HZ+8),   (0.95,0.06,0.95),C(110,80,40)),
    box((HX+13, HY+1.0, HZ+8),   (0.08,0.55,0.08),C(160,140,100)),
    box((HX+13, HY+1.6, HZ+8),   (0.5,0.12,0.5),  C(255,230,150)),
]
PHONE_POS = Vec3(HX+13, HY+1.5, HZ+8)

# TV on wall
home_entities += [
    box((HX+8, HY+2.0, HZ+11.8),(7,  2.2, 0.12), C(20,20,25)),
    box((HX+8, HY+2.0, HZ+11.7),(6.2,1.8, 0.08), C(15,25,60)),
    box((HX+8, HY+0.9, HZ+11.8),(0.2,1.5,0.2),   C(30,30,30)),   # TV stand pole
]

# Apartment door (with frame)
home_entities += [
    box((HX+8, HY+1.2, HZ+0.5),  (2.2,2.6,0.25), C(110,75,35)),           # door frame
    box((HX+8, HY+1.15,HZ+0.45), (1.8,2.4,0.15), C(139,95,50), True),     # door
    box((HX+9.0,HY+1.1,HZ+0.38),(0.1,0.15,0.12), C(200,170,50)),           # handle
]
HOME_DOOR_POS = Vec3(HX+8, HY+1.5, HZ+1)

# Kitchen counter (far right)
home_entities += [
    box((HX+14.5,HY+0.7, HZ+6.5),(1.0,1.1,3.5), C(170,150,130), True),
    box((HX+14.5,HY+1.27,HZ+6.5),(1.1,0.07,3.7),C(200,195,185)),
]

# ════════════════════════════════════════════════════
# BAR MAP
# ════════════════════════════════════════════════════
BX, BY, BZ = 300, 0, 0

make_room(BX, BY, BZ, 24, 16, 4, C(30,20,15), C(50,35,20), C(60,45,30),
          accent=False, group=bar_entities)

# ── Bar improvements (Change 10) ─────────────────────
# Mood lighting strips along top of walls
for bz_pos in (BZ+0.3, BZ+15.7):
    bar_entities.append(box((BX+12, BY+3.7, bz_pos),(22,0.2,0.15),C(180,20,80)))

# Bar counter (L-shape with detail)
bar_entities += [
    box((BX+12, BY+0.85, BZ+13.5),(20,0.9,1.6),  C(80,50,25),   True),  # base
    box((BX+12, BY+1.36, BZ+13.5),(20.2,0.1,1.8),C(130,95,55)),          # top
    box((BX+12, BY+2.0,  BZ+14.5),(20,1.5,0.15), C(60,40,20)),           # back wall
]
BAR_COUNTER_POS = Vec3(BX+12, BY+1.5, BZ+12.5)

# Bottle shelf behind bar
bar_entities.append(box((BX+12, BY+2.9, BZ+14.8),(18,0.08,0.6),C(100,70,40)))
for bx_off, bcol in enumerate([C(200,60,40),C(40,100,180),C(60,160,60),
                                 C(180,140,40),C(120,40,160),C(200,100,40)]):
    bar_entities.append(box((BX+4+bx_off*2.5, BY+3.15, BZ+14.8),(0.2,0.55,0.2),bcol))

# Bar stools along counter front
for bx_st in range(6):
    sx = BX+3 + bx_st*3
    bar_entities += [
        box((sx, BY+0.7,  BZ+11.5),(0.55,0.08,0.55),C(60,40,20),True),  # seat
        box((sx, BY+0.35, BZ+11.5),(0.08,0.7, 0.08),C(80,55,30),True),  # post
    ]

# Tables with better detail
for ti, tx in enumerate((BX+4, BX+12, BX+20)):
    tbl_col = (C(100,70,45), C(90,65,40), C(110,75,50))[ti]
    bar_entities += [
        box((tx, BY+0.7,  BZ+6),(2.2,0.1,2.2), tbl_col, True),     # top
        box((tx, BY+0.35, BZ+6),(0.15,0.7,0.15),C(70,50,30),True),  # center pole
        box((tx, BY+0.08, BZ+6),(1.4,0.1,1.4),  C(70,50,30),True),  # base
    ]
    # Chairs around table
    for sx, sz in ((-1.4,0),(1.4,0),(0,-1.4),(0,1.4)):
        bar_entities += [
            box((tx+sx,BY+0.42,BZ+6+sz),(0.65,0.07,0.6),C(50,35,20),True),
            box((tx+sx,BY+0.7, BZ+6+sz+0.3*(-1 if sz>=0 else 1)),(0.6,0.55,0.07),C(50,35,20)),
            box((tx+sx,BY+0.2, BZ+6+sz),(0.5, 0.07,0.4),C(40,28,15),True),
        ]

BAR_TABLE_POSITIONS = [Vec3(BX+4,BY+1.5,BZ+6), Vec3(BX+12,BY+1.5,BZ+6), Vec3(BX+20,BY+1.5,BZ+6)]

# Bar door with frame
bar_entities += [
    box((BX+12, BY+1.3, BZ+0.5),(2.2,2.6,0.25),C(80,55,25)),
    box((BX+12, BY+1.25,BZ+0.45),(1.8,2.3,0.15),C(100,65,30),True),
    box((BX+13.0,BY+1.1,BZ+0.38),(0.1,0.15,0.12),C(200,170,50)),
]
BAR_DOOR_POS = Vec3(BX+12, BY+1.5, BZ+1)

# Neon sign on back wall
bar_entities += [
    box((BX+12, BY+3.2, BZ+15.7),(8,0.6,0.1),C(200,20,80)),
    box((BX+12, BY+3.2, BZ+15.6),(7,0.4,0.08),C(255,100,150)),
]

# ════════════════════════════════════════════════════
# NPC SYSTEM
# ════════════════════════════════════════════════════
npcs = []
bar_npcs = []   # subset currently at bar

# ── Better NPC bodies (Change 2) ─────────────────────
def spawn_npc(name, role, dept, x, z, y, dialogue, relationship=False):
    pos = Vec3(x, y+1.0, z)
    col = MGR_COL if 'Manager' in role else DEPT_COL[dept]
    # torso
    body  = box(pos, (0.5, 0.7, 0.3), col, True)
    # head
    head  = box(pos + Vec3(0, 0.65, 0), (.36,.36,.36), HEAD_COL)
    # eyes (two small dark boxes on head front)
    eye_l = box(pos + Vec3(-0.1, 0.72, -0.19), (.09,.07,.05), C(30,30,30))
    eye_r = box(pos + Vec3( 0.1, 0.72, -0.19), (.09,.07,.05), C(30,30,30))
    # legs
    leg_l = box(pos + Vec3(-0.13, -0.55, 0), (.18, 0.5, 0.22), C(60,60,80), True)
    leg_r = box(pos + Vec3( 0.13, -0.55, 0), (.18, 0.5, 0.22), C(60,60,80), True)
    # arms
    arm_l = box(pos + Vec3(-0.35, 0.1, 0), (.14, 0.5, 0.2), col)
    arm_r = box(pos + Vec3( 0.35, 0.1, 0), (.14, 0.5, 0.2), col)
    label = Text(text=name, world_space=True,
                 position=pos + Vec3(0, 1.3, 0),
                 scale=6, origin=(0,0), color=Color(1,1,1,1))
    friendship[name] = 0
    data = {
        'name': name, 'role': role, 'dept': dept,
        'pos':  pos,  'dialogue': dialogue,
        'relationship': relationship,
        'body': body, 'head': head, 'label': label,
        'parts': [body, head, eye_l, eye_r, leg_l, leg_r, arm_l, arm_r],
    }
    npcs.append(data)
    floor2_entities.extend([body, head, eye_l, eye_r, leg_l, leg_r, arm_l, arm_r])
    return data

# ── SALES ────────────────────────────────────────────
spawn_npc('Alex Kim',    'Sales Rep',     'Sales',  2,  6, Y2,
    {0:["Hey! Quota is looking great this month."]})
spawn_npc('Mia Torres',  'Sales Rep',     'Sales',  6,  6, Y2,
    {0:["Hi, welcome to the team!"],
     1:["Good to see you again. Settling in?","Feel free to ask me anything."],
     2:["You're getting the hang of it!","Pro tip: always CC your manager."],
     3:["Honestly, you're one of the good ones.","I know the pipeline inside-out."],
     4:["We should grab lunch sometime.","I've got your back on that project."]},
    True)
spawn_npc('Jake Osei',   'Sales Rep',     'Sales', 10,  6, Y2,
    {0:["Closing deals, one at a time."]})
spawn_npc('Priya Nair',  'Sales Rep',     'Sales',  2, 13, Y2,
    {0:["Sales dashboards are honestly beautiful."],
     1:["Hit me up if you want tips on clients.","I track every metric religiously."],
     2:["Our close rate is up this quarter!","Check the CRM for the latest leads."],
     3:["You remind me of myself starting out.","Here's how I manage my pipeline..."],
     4:["You're basically part of my squad now.","Let's strategize on that big account."]},
    True)
spawn_npc('Leo Chan',    'Sales Rep',     'Sales',  6, 13, Y2,
    {0:["Running late on a follow-up, brb."]})
spawn_npc('Sandra Bloom','Sales Manager', 'Sales',  7, 21, Y2,
    {0:["Welcome to the Sales team!"],
     1:["Let me know if you need anything.","Numbers are looking good."],
     2:["I see potential in you.","Keep those conversion rates up."],
     3:["Honestly, you're one of my top picks.","Here's what I look for in talent..."],
     4:["I'm pushing for your promotion.","Between us — big client coming soon."]},
    True)

# ── BSA ──────────────────────────────────────────────
spawn_npc('Ravi Patel',  'Business Analyst','BSA', 16,  6, Y2,
    {0:["Documentation never sleeps."]})
spawn_npc('Chloe Martin','Business Analyst','BSA', 20,  6, Y2,
    {0:["Requirements gathering is an art."],
     1:["Want to review a spec together?","I love a good flowchart."],
     2:["You write clean requirements.","Let me share my template with you."],
     3:["We work really well together.","Here's how I handle scope creep..."],
     4:["You're my go-to for workshops now.","We should co-author the next spec."]},
    True)
spawn_npc('Tom Reyes',   'Business Analyst','BSA', 24,  6, Y2,
    {0:["Gap analysis? On it."]})
spawn_npc('Sara Wolfe',  'Business Analyst','BSA', 16, 13, Y2,
    {0:["I live in spreadsheets."],
     1:["Let me know if you need a process mapped.","Excel is my second language."],
     2:["Your process diagrams are great.","I'll teach you my BPMN shortcuts."],
     3:["I can always count on your analysis.","Here's the stakeholder map I use..."],
     4:["We make a great analytical team.","I'll put you on my next workshop."]},
    True)
spawn_npc('Ben Foster',  'Business Analyst','BSA', 20, 13, Y2,
    {0:["User stories are my love language."]})
spawn_npc('Diana Cross', 'BSA Manager',    'BSA', 21, 21, Y2,
    {0:["Welcome to the BSA floor!"],
     1:["We keep things structured here.","Any questions, just ask."],
     2:["Your documentation is getting better.","I appreciate your thoroughness."],
     3:["You've got good analytical instincts.","Let me show you the project board."],
     4:["You're BSA material for sure.","I'm recommending you for the big project."]},
    True)

# ── FSS ──────────────────────────────────────────────
spawn_npc('Nina Park',   'Functional Support','FSS', 30,  6, Y2,
    {0:["Ticket resolved. Next!"]})
spawn_npc('Omar Diaz',   'Functional Support','FSS', 34,  6, Y2,
    {0:["I know Odoo modules like the back of my hand."],
     1:["Need help with a feature? I got you.","Every module has its quirks."],
     2:["You're picking up Odoo fast.","Here's a hidden config trick..."],
     3:["I trust your instincts on support cases.","Let me walk you through the APIs."],
     4:["You're basically an Odoo expert now.","Let's tackle that complex ticket together."]},
    True)
spawn_npc('Yuki Abe',    'Functional Support','FSS', 38,  6, Y2,
    {0:["Config or customization? That is the question."]})
spawn_npc('Finn Kelly',  'Functional Support','FSS', 30, 13, Y2,
    {0:["Just fixed something I did not know was broken."],
     1:["Ping me if you get stuck.","I've seen every error code twice."],
     2:["You debug like a pro.","Here's how I reproduce tricky bugs..."],
     3:["We make a good support duo.","I'll loop you in on the hard tickets."],
     4:["Honestly you're the best on the team.","Let's write a guide together."]},
    True)
spawn_npc('Ana Silva',   'Functional Support','FSS', 34, 13, Y2,
    {0:["Functional support is honestly underrated."]})
spawn_npc('Marcus Reid', 'Support Manager',  'FSS', 35, 21, Y2,
    {0:["Hey, welcome to FSS!"],
     1:["We move fast here.","Proud of this team."],
     2:["Your response times are great.","Keep that SLA green."],
     3:["I want you leading the next onboarding.","Real talk — you've impressed me."],
     4:["You're my top candidate for team lead.","Here's what's coming next quarter..."]},
    True)

# ── HR ───────────────────────────────────────────────
spawn_npc('Grace Tan',   'HR Manager',    'HR',   49, 21, Y2,
    {0:["Welcome to Odoo!"],
     1:["How are you settling in?","Open door — always here."],
     2:["Let me know if you need anything from HR.","We care about culture here."],
     3:["You've been a great addition to the team.","Here's a tip on your next review..."],
     4:["I'll be writing you a glowing review.","Between us — there's a raise coming."]},
    True)

# ── Bar NPC placeholders (reuse some npcs) ───────────
bar_npc_entities = []  # visual entities placed at bar tables

# ════════════════════════════════════════════════════
# PLAYER
# ════════════════════════════════════════════════════
player = FirstPersonController(position=SPAWN['floor1'],
                               speed=5, mouse_sensitivity=Vec2(50,50))
player.camera_pivot.y = 1.5

# ════════════════════════════════════════════════════
# HUD
# ════════════════════════════════════════════════════
hud_stats = Text(text='', position=(-0.85, 0.47), origin=(-0.5, 0.5),
                 scale=1.3, color=Color(1,1,1,1), background=True)
hud_clock = Text(text='', position=(0.85, 0.47), origin=(0.5, 0.5),
                 scale=1.3, color=Color(1,1,1,1), background=True)
hud_hint  = Text(text='', position=(0, -0.38), origin=(0,0),
                 scale=1.6, color=Color(1,1,1,1), background=True, visible=False)
hud_keys  = Text(text='WASD Move  |  Mouse Look  |  E Interact  |  Q Quit',
                 position=(0,-0.47), origin=(0,0), scale=1.1,
                 color=Color(1,1,1,1), background=True)
hud_floor = Text(text='', position=(-0.85, 0.38), origin=(-0.5, 0.5),
                 scale=1.2, color=Color(1,1,1,1), background=True)

# ── HUD improvements (Change 11) ─────────────────────
def update_hud():
    lvl   = stats['level']
    title = LEVEL_TITLES[lvl]
    # ASCII bar helpers
    def bar(val, mx=100, w=10):
        filled = int(val/mx*w)
        return '[' + '#'*filled + '-'*(w-filled) + ']'
    hud_stats.text = (f"Mood {bar(stats['mood'])} {stats['mood']}   "
                      f"Energy {bar(stats['energy'])} {stats['energy']}   "
                      f"${stats['money']}   {stats['xp']}xp Lv{lvl} {title}")
    h = int(hour)
    m = int((hour - h) * 60)
    ampm = 'AM' if h < 12 else 'PM'
    h12  = h % 12 or 12
    dow  = day_names[(day-1) % 7]
    hud_clock.text = f"{h12}:{m:02d} {ampm}  Day {day} {dow}"
    hud_floor.text = ('Floor 1' if current_floor==1 else 'Floor 2') if game_state in ('work','evening') else game_state.upper()

def check_level_up():
    for lvl in (2, 3, 4):
        if stats['level'] < lvl and stats['xp'] >= XP_PER_LEVEL[lvl-1]:
            stats['level'] = lvl
            show_notification(f"Level Up! You are now {LEVEL_TITLES[lvl]}!")

# ════════════════════════════════════════════════════
# NOTIFICATION / DIALOGUE UI
# ════════════════════════════════════════════════════
notification_panel = None
dialogue_open      = False
dialogue_panel     = None
nearest_npc        = None
phone_menu_open    = False
phone_panel        = None
near_exit          = False
near_stairs        = False
near_bed           = False
near_phone         = False
near_home_door     = False
near_bar_counter   = False
near_bar_door      = False
near_cafeteria     = False
near_player_desk   = False

def show_notification(msg, duration=3.0):
    global notification_panel
    if notification_panel:
        destroy(notification_panel)
    notification_panel = Entity(parent=camera.ui, model='quad',
                                scale=(.7,.12), position=(0,.2),
                                color=C(20,20,40,230), z=-1)
    Text(parent=notification_panel, text=msg,
         position=(0,0), origin=(0,0), scale=2.0, color=Color(1,1,0.5,1))
    invoke(lambda: destroy(notification_panel) if notification_panel else None,
           delay=duration)

def hearts(name):
    lvl = friendship.get(name, 0)
    return '[' + '*'*lvl + '-'*(5-lvl) + ']'

def open_dialogue(npc):
    global dialogue_open, dialogue_panel
    dialogue_open = True
    mouse.locked  = False
    mouse.visible = True
    hud_hint.visible = False

    lvl  = friendship.get(npc['name'], 0)
    dial = npc['dialogue']
    # Get lines for current friendship level (fallback to 0)
    lines = dial.get(lvl, dial.get(0, ['...']))
    line  = random.choice(lines)

    if npc['relationship']:
        friendship[npc['name']] = min(5, lvl + 1)
        stats['mood'] = min(100, stats['mood'] + 3)

    rel_tag  = f"  {hearts(npc['name'])}" if npc['relationship'] else ''
    dialogue_panel = Entity(parent=camera.ui, model='quad',
                            scale=(.75,.3), position=(0,-.15),
                            color=Color(.04,.04,.1,.92), z=-1)
    Text(parent=dialogue_panel,
         text=f"{npc['name']}  ·  {npc['role']}  ·  {npc['dept']}{rel_tag}",
         position=(0,.36), origin=(0,0), scale=2.0,
         color=Color(180/255,100/255,255/255,1))
    Text(parent=dialogue_panel,
         text=f'"{line}"', position=(0,.06), origin=(0,0),
         scale=2.0, color=Color(1,1,1,1))
    Text(parent=dialogue_panel,
         text='[ E ] Close',
         position=(0,-.38), origin=(0,0),
         scale=1.5, color=Color(.7,.7,.7,1))

def close_dialogue():
    global dialogue_open, dialogue_panel
    if dialogue_panel:
        destroy(dialogue_panel)
        dialogue_panel = None
    dialogue_open = False
    mouse.locked  = True
    mouse.visible = False

# ════════════════════════════════════════════════════
# TASK SYSTEM
# ════════════════════════════════════════════════════
def pop_task():
    global task_panel, task_active, current_task
    if task_panel or not sitting_at_desk:
        return
    dept  = stats['dept']
    pool  = TASKS.get(dept, TASKS['Sales'])
    current_task = random.choice(pool)
    task_active  = True
    mouse.locked = False
    mouse.visible= True

    task_panel = Entity(parent=camera.ui, model='quad',
                        scale=(.6,.22), position=(0,.1),
                        color=C(10,30,20,230), z=-1)
    Text(parent=task_panel,
         text=f"Task: {current_task['text']}",
         position=(0,.28), origin=(0,0), scale=1.9, color=Color(1,1,0.3,1))
    Text(parent=task_panel,
         text=f"Reward: +{current_task['xp']} XP   +${current_task['money']}",
         position=(0,.02), origin=(0,0), scale=1.7, color=Color(0.6,1,0.6,1))
    Text(parent=task_panel,
         text='[ E ] Accept    [ X ] Skip',
         position=(0,-.28), origin=(0,0), scale=1.6, color=Color(.8,.8,.8,1))

def accept_task():
    global task_panel, task_active, current_task
    if not task_active or not current_task:
        return
    mult = 0.5 if stats['energy'] <= 0 else 1.0
    stats['xp']    += int(current_task['xp']    * mult)
    stats['money'] += int(current_task['money'] * mult)
    stats['energy'] = max(0, stats['energy'] - 3)
    check_level_up()
    dismiss_task()
    show_notification(f"+{int(current_task['xp']*mult)} XP  +${int(current_task['money']*mult)}")

def dismiss_task():
    global task_panel, task_active, current_task
    if task_panel:
        destroy(task_panel)
        task_panel = None
    task_active  = False
    current_task = None
    if sitting_at_desk:
        mouse.locked  = True
        mouse.visible = False

# ════════════════════════════════════════════════════
# PHONE MENU  (home couch)
# ════════════════════════════════════════════════════
def open_phone_menu():
    global phone_menu_open, phone_panel
    phone_menu_open = True
    mouse.locked    = False
    mouse.visible   = True
    rel_npcs = [n for n in npcs if n['relationship']]

    phone_panel = Entity(parent=camera.ui, model='quad',
                         scale=(.65, min(.7, .1 + len(rel_npcs)*.08)),
                         position=(0,0), color=C(10,10,30,240), z=-1)
    Text(parent=phone_panel, text='Phone — Who do you want to reach?',
         position=(0,.38), origin=(0,0), scale=1.9, color=Color(1,1,0.5,1))
    for i, npc in enumerate(rel_npcs):
        y = .22 - i*.09
        Text(parent=phone_panel,
             text=f"{npc['name']}  {hearts(npc['name'])}",
             position=(-0.02, y), origin=(0,0), scale=1.5, color=Color(1,1,1,1))
        btn = Button(parent=phone_panel, text='Text',
                     position=(.22, y), scale=(.08,.04),
                     color=C(50,100,50), highlight_color=C(80,160,80),
                     text_color=Color(1,1,1,1))
        btn.on_click = lambda n=npc: phone_text(n)
    Text(parent=phone_panel, text='[ ESC ] Close',
         position=(0,-.38), origin=(0,0), scale=1.4, color=Color(.6,.6,.6,1))

def phone_text(npc):
    friendship[npc['name']] = min(5, friendship.get(npc['name'],0) + 1)
    stats['mood'] = min(100, stats['mood'] + 5)
    close_phone_menu()
    lvl   = friendship[npc['name']]
    lines = npc['dialogue'].get(lvl, npc['dialogue'].get(0,['...']))
    show_notification(f"{npc['name']}: \"{random.choice(lines)}\"", 4.0)

def close_phone_menu():
    global phone_menu_open, phone_panel
    if phone_panel:
        destroy(phone_panel)
        phone_panel = None
    phone_menu_open = False
    mouse.locked    = True
    mouse.visible   = False

# ════════════════════════════════════════════════════
# MAP VISIBILITY  (Change 12)
# ════════════════════════════════════════════════════
def show_map(name):
    for group, gname in [(floor1_entities,'floor1'),(floor2_entities,'floor2'),
                          (home_entities,'home'),(bar_entities,'bar')]:
        vis = (gname == name) or (name == 'floor2' and gname == 'floor1')
        for e in group:
            e.enabled = vis
    for n in npcs:
        vis = (name in ('floor1','floor2'))
        for part in n.get('parts', [n['body'], n['head']]):
            part.enabled = vis
        n['label'].enabled = vis

# ════════════════════════════════════════════════════
# STATE TRANSITIONS
# ════════════════════════════════════════════════════
def go_to_work():
    global game_state, evening_triggered
    game_state        = 'work'
    evening_triggered = False
    show_map('floor1')
    player.position   = Vec3(*SPAWN['floor1'])
    update_hud()

def trigger_end_of_work():
    global game_state, evening_triggered
    if evening_triggered:
        return
    evening_triggered = True
    game_state = 'evening'
    show_notification("Work day over! Head to the exit door to go home.", 5.0)
    mouse.locked  = False
    mouse.visible = True

def go_home():
    global game_state, bar_talked_tonight
    game_state        = 'home'
    bar_talked_tonight= set()
    show_map('home')
    player.position   = Vec3(*SPAWN['home'])
    mouse.locked  = True
    mouse.visible = False

def go_bar():
    global game_state
    game_state = 'bar'
    show_map('bar')
    player.position = Vec3(*SPAWN['bar'])
    spawn_bar_npcs()
    mouse.locked  = True
    mouse.visible = False

def sleep_in_bed():
    global day, hour, game_state, evening_triggered
    stats['energy'] = 100
    stats['mood']   = min(100, stats['mood'] + 10)
    day            += 1
    hour            = WORK_START
    evening_triggered = False
    show_notification(f"Good morning! Day {day} begins.", 3.0)
    invoke(go_to_work, delay=3.0)

# ════════════════════════════════════════════════════
# BAR NPC SPAWNING
# ════════════════════════════════════════════════════
_bar_npc_ents = []

def spawn_bar_npcs():
    global _bar_npc_ents
    for e in _bar_npc_ents:
        destroy(e)
    _bar_npc_ents.clear()
    candidates = random.sample(npcs, min(4, len(npcs)))
    for i, npc in enumerate(candidates):
        tbl = BAR_TABLE_POSITIONS[i % 3]
        ox  = random.uniform(-0.5, 0.5)
        oz  = random.uniform(-0.5, 0.5)
        pos = tbl + Vec3(ox, 0, oz)
        col = MGR_COL if 'Manager' in npc['role'] else DEPT_COL[npc['dept']]
        # torso
        body  = box(pos, (0.5, 0.7, 0.3), col, True)
        # head
        head  = box(pos+Vec3(0, 0.65, 0), (.36,.36,.36), HEAD_COL)
        # eyes
        eye_l = box(pos + Vec3(-0.1, 0.72, -0.19), (.09,.07,.05), C(30,30,30))
        eye_r = box(pos + Vec3( 0.1, 0.72, -0.19), (.09,.07,.05), C(30,30,30))
        # legs
        leg_l = box(pos + Vec3(-0.13, -0.55, 0), (.18, 0.5, 0.22), C(60,60,80), True)
        leg_r = box(pos + Vec3( 0.13, -0.55, 0), (.18, 0.5, 0.22), C(60,60,80), True)
        # arms
        arm_l = box(pos + Vec3(-0.35, 0.1, 0), (.14, 0.5, 0.2), col)
        arm_r = box(pos + Vec3( 0.35, 0.1, 0), (.14, 0.5, 0.2), col)
        lbl   = Text(text=npc['name'], world_space=True,
                     position=pos+Vec3(0,1.3,0), scale=6,
                     origin=(0,0), color=Color(1,1,1,1))
        _bar_npc_ents += [body, head, eye_l, eye_r, leg_l, leg_r, arm_l, arm_r]
        bar_entities  += [body, head, eye_l, eye_r, leg_l, leg_r, arm_l, arm_r]
        # store bar position on npc temp
        npc['bar_pos'] = pos

def nearest_bar_npc():
    p    = player.position
    best = None
    bd   = 2.5
    for npc in npcs:
        bp = npc.get('bar_pos')
        if bp:
            d = (p - bp).length()
            if d < bd:
                bd, best = d, npc
    return best

# ════════════════════════════════════════════════════
# UPDATE LOOP
# ════════════════════════════════════════════════════
_desk_timer = 0.0

def update():
    global nearest_npc, near_stairs, near_exit, near_bed
    global near_phone, near_home_door, near_bar_counter, near_bar_door
    global near_cafeteria, near_player_desk, _desk_timer, current_floor
    global hour

    p = player.position

    if game_state in ('create',):
        return

    update_hud()

    # Time advance
    if game_state == 'work':
        hour += time.dt * (TIME_SPEED / 3600)
        if hour >= WORK_END:
            trigger_end_of_work()
        # Energy drain while sitting
        if sitting_at_desk:
            stats['energy'] = max(0, stats['energy'] - time.dt * (2/3600) * TIME_SPEED)

    # Floor detection (work state)
    if game_state in ('work','evening'):
        current_floor = 2 if p.y > 6 else 1

    if dialogue_open or task_active or phone_menu_open:
        hud_hint.visible = False
        return

    # ── Proximity checks ─────────────────────────────
    near_exit        = False
    near_stairs      = False
    near_bed         = False
    near_phone       = False
    near_home_door   = False
    near_bar_counter = False
    near_bar_door    = False
    near_cafeteria   = False
    near_player_desk = False
    nearest_npc      = None

    # NPC proximity (work floors)
    if game_state in ('work','evening'):
        best_d = 2.8
        for npc in npcs:
            d = (p - npc['pos']).length()
            if d < best_d:
                best_d, nearest_npc = d, npc

        near_stairs = (p - STAIR_F1).length() < 3 or (p - STAIR_F2).length() < 3

        if game_state == 'evening':
            near_exit = (p - EXIT_DOOR_POS).length() < 2.5

        if game_state == 'work' and current_floor == 2:
            desk_pos = PLAYER_DESK_POS.get(stats['dept'])
            if desk_pos and (p - desk_pos).length() < 2.5:
                near_player_desk = True

        if current_floor == 1:
            near_cafeteria = (p - CAFETERIA_POS).length() < 3.0

    if game_state == 'home':
        near_bed      = (p - BED_POS).length()       < 2.5
        near_phone    = (p - PHONE_POS).length()     < 2.5
        near_home_door= (p - HOME_DOOR_POS).length() < 2.5

    if game_state == 'bar':
        near_bar_counter = (p - BAR_COUNTER_POS).length() < 3.0
        near_bar_door    = (p - BAR_DOOR_POS).length()    < 2.5
        bn = nearest_bar_npc()
        if bn:
            nearest_npc = bn

    # ── Desk work timer ──────────────────────────────
    if sitting_at_desk and game_state == 'work':
        _desk_timer += time.dt
        if _desk_timer >= TASK_INTERVAL:
            _desk_timer = 0.0
            pop_task()

    # ── Hint text ────────────────────────────────────
    hint = ''
    if nearest_npc:
        hint = f"[ E ] Talk to {nearest_npc['name']}"
    elif near_exit:
        hint = '[ E ] Exit to Home'
    elif near_stairs:
        dest = 'Floor 1' if current_floor == 2 else 'Floor 2'
        hint = f'[ E ] Go to {dest}'
    elif near_player_desk:
        hint = '[ E ] Sit at your desk' if not sitting_at_desk else '[ E ] Stand up'
    elif near_cafeteria:
        hint = '[ E ] Buy lunch (+20 energy, -$5)'
    elif near_bed:
        hint = '[ E ] Sleep (advance to next work day)'
    elif near_phone:
        hint = '[ E ] Use phone'
    elif near_home_door:
        hint = '[ E ] Go to the bar'
    elif near_bar_counter:
        hint = '[ E ] Buy a drink (+15 mood, +10 energy, -$8)'
    elif near_bar_door:
        hint = '[ E ] Go home'

    hud_hint.text    = hint
    hud_hint.visible = bool(hint)

# ════════════════════════════════════════════════════
# INPUT HANDLER
# ════════════════════════════════════════════════════
def input(key):
    global sitting_at_desk, _desk_timer

    if key in ('escape',):
        if dialogue_open:
            close_dialogue(); return
        if task_active:
            dismiss_task();   return
        if phone_menu_open:
            close_phone_menu(); return

    if key == 'q' and not dialogue_open and not task_active and not phone_menu_open:
        application.quit()

    if key == 'x' and task_active:
        dismiss_task()
        return

    if key == 'e':
        if dialogue_open:
            close_dialogue(); return
        if task_active:
            accept_task();    return
        if phone_menu_open:
            close_phone_menu(); return

        if nearest_npc:
            # bar NPC: only once per evening
            if game_state == 'bar':
                nm = nearest_npc['name']
                if nm not in bar_talked_tonight:
                    bar_talked_tonight.add(nm)
                    friendship[nm] = min(5, friendship.get(nm,0)+1)
                    stats['mood']  = min(100, stats['mood']+5)
                open_dialogue(nearest_npc)
            else:
                open_dialogue(nearest_npc)
            return

        if near_exit and game_state == 'evening':
            go_home(); return

        if near_stairs and game_state in ('work','evening'):
            if current_floor == 1:
                player.position = Vec3(47, Y2+4, 13)   # Fix 1: higher landing on floor 2
            else:
                player.position = Vec3(47, Y1+1.5, 13)
            return

        if near_player_desk and game_state == 'work':
            sitting_at_desk = not sitting_at_desk
            _desk_timer = 0.0
            if not sitting_at_desk:
                dismiss_task()
            player.speed = 0 if sitting_at_desk else 5
            show_notification('Sitting at desk — tasks incoming!' if sitting_at_desk else 'Stood up.')
            return

        if near_cafeteria and game_state == 'work':
            if stats['money'] >= 5:
                stats['money'] -= 5
                stats['energy'] = min(100, stats['energy'] + 20)
                show_notification('+20 Energy from lunch! -$5')
            else:
                show_notification('Not enough money for lunch.')
            return

        if near_bed and game_state == 'home':
            sleep_in_bed(); return

        if near_phone and game_state == 'home':
            open_phone_menu(); return

        if near_home_door and game_state == 'home':
            go_bar(); return

        if near_bar_counter and game_state == 'bar':
            if stats['money'] >= 8:
                stats['money'] -= 8
                stats['mood']   = min(100, stats['mood']   + 15)
                stats['energy'] = min(100, stats['energy'] + 10)
                show_notification('+15 Mood  +10 Energy  -$8')
            else:
                show_notification('Not enough money for a drink.')
            return

        if near_bar_door and game_state == 'bar':
            go_home(); return

# ════════════════════════════════════════════════════
# CHARACTER CREATION SCREEN
# ════════════════════════════════════════════════════
player.enabled = False
mouse.locked   = False
mouse.visible  = True

# Hide all maps until game starts  (Change 12: use parts loop)
for e in floor1_entities + floor2_entities + home_entities + bar_entities:
    e.enabled = False
for n in npcs:
    for part in n.get('parts', [n['body'], n['head']]):
        part.enabled = False
    n['label'].enabled = False

cc_panel = Entity(parent=camera.ui, model='quad',
                  scale=(.6,.55), color=Color(.04,.04,.1,.95), z=-1)
Text(parent=cc_panel, text='ODOO LIFE',
     position=(0,.36), origin=(0,0), scale=4.5,
     color=Color(114/255,46/255,209/255,1))
Text(parent=cc_panel, text='Create your character',
     position=(0,.22), origin=(0,0), scale=2.0,
     color=Color(.8,.8,.8,1))
Text(parent=cc_panel, text='Name:',
     position=(-.22,.08), origin=(0,0), scale=1.8,
     color=Color(1,1,1,1))
name_field = InputField(parent=cc_panel, position=(0.06,.08),
                        scale=(.3,.045), default_value='YourName')
Text(parent=cc_panel, text='Department:',
     position=(0,-.06), origin=(0,0), scale=1.8,
     color=Color(1,1,1,1))

selected_dept = ['Sales']
dept_btns     = []

def select_dept(d):
    selected_dept[0] = d
    for b, bd in dept_btns:
        b.color = PURPLE if bd == d else C(50,50,70)

for i, d in enumerate(('Sales','BSA','FSS')):
    xi = -0.18 + i * 0.18
    b  = Button(parent=cc_panel, text=d,
                position=(xi, -.15), scale=(.14,.05),
                color=PURPLE if i==0 else C(50,50,70),
                highlight_color=C(140,80,230),
                text_color=Color(1,1,1,1))
    b.on_click = lambda dept=d: select_dept(dept)
    dept_btns.append((b, d))

def start_game():
    global game_state
    stats['name'] = name_field.text or 'Player'
    stats['dept'] = selected_dept[0]
    destroy(cc_panel)
    player.enabled = True
    game_state = 'work'
    show_map('floor1')
    player.position = Vec3(*SPAWN['floor1'])
    mouse.locked  = True
    mouse.visible = False
    update_hud()

start_btn = Button(parent=cc_panel, text='Start Game',
                   position=(0,-.3), scale=(.26,.06),
                   color=PURPLE, highlight_color=C(140,80,230),
                   text_color=Color(1,1,1,1))
start_btn.on_click = start_game

app.run()
