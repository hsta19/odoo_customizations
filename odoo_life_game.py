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
office_entities = []
home_entities   = []
bar_entities    = []

# ── Spawn points ─────────────────────────────────────
SPAWN = {
    'floor1': Vec3(10, 1.5, 6),    # lobby
    'floor2': Vec3(10, 1.5, 6),    # keep for compat, same as floor1
    'home':   Vec3(8,  1.5, 6),
    'bar':    Vec3(12, 1.5, 3),
}

COFFEE_POS  = Vec3(46.5, 1.5, 10)
VENDING_POS = Vec3(60,   1.5, 10)
COUCH_POS   = Vec3(53,   1.5, 9.5)

Y0 = 0

PLAYER_DESK_POS = {
    'Sales': Vec3(11,  Y0+1.5, 28),
    'BSA':   Vec3(29,  Y0+1.5, 28),
    'FSS':   Vec3(46,  Y0+1.5, 28),
    'HR':    Vec3(60.5,Y0+1.5, 26),
}

# ════════════════════════════════════════════════════
# BUILDING HELPERS
# ════════════════════════════════════════════════════
ROOM_H = 4.5
DOOR_W = 3.5

def build_room(x1, z1, x2, z2, y, h, fc, wc, cc,
               door_south=None, door_north=None,
               door_west=None,  door_east=None,
               group=None):
    """Build a box room. door_* = centre coordinate of doorway gap."""
    cx, cz = (x1+x2)/2, (z1+z2)/2
    w, d   = x2-x1, z2-z1
    ents   = []

    # Thick invisible collision floor
    thick = Entity(model='cube', position=(cx, y-1.5, cz),
                   scale=(w+0.5, 3.5, d+0.5), collider='box')
    thick.visible = False
    ents.append(thick)

    # Visible floor + ceiling
    ents.append(box((cx, y+0.15,    cz), (w, 0.30, d), fc))
    ents.append(box((cx, y+h+0.15,  cz), (w, 0.30, d), cc))

    # Ceiling light strips
    for lz in (z1+d*0.3, z1+d*0.7):
        ents.append(box((cx, y+h-0.08, lz), (w*0.65, 0.07, 0.35), C(255,250,220)))

    # Baseboard trim
    tc = Color(min(wc.r*1.25,1), min(wc.g*1.25,1), min(wc.b*1.25,1), 1)
    ents += [
        box((cx,      y+0.35, z1+0.18), (w,    0.22, 0.10), tc),
        box((cx,      y+0.35, z2-0.18), (w,    0.22, 0.10), tc),
        box((x1+0.18, y+0.35, cz),      (0.10, 0.22, d),    tc),
        box((x2-0.18, y+0.35, cz),      (0.10, 0.22, d),    tc),
    ]

    def seg_h(xa, xb, zp):
        if xb > xa+0.25:
            ents.append(box(((xa+xb)/2, y+h/2, zp), (xb-xa, h, 0.30), wc, True))
    def seg_v(za, zb, xp):
        if zb > za+0.25:
            ents.append(box((xp, y+h/2, (za+zb)/2), (0.30, h, zb-za), wc, True))

    def wall_h(zp, dc):
        if dc is None:
            seg_h(x1, x2, zp)
        else:
            d1, d2 = dc-DOOR_W/2, dc+DOOR_W/2
            seg_h(x1, d1, zp); seg_h(d2, x2, zp)
            ents.append(box((dc, y+h-0.22, zp), (DOOR_W, 0.42, 0.30), wc))
    def wall_v(xp, dc):
        if dc is None:
            seg_v(z1, z2, xp)
        else:
            d1, d2 = dc-DOOR_W/2, dc+DOOR_W/2
            seg_v(z1, d1, xp); seg_v(d2, z2, xp)
            ents.append(box((xp, y+h-0.22, dc), (0.30, 0.42, DOOR_W), wc))

    wall_h(z1, door_south)
    wall_h(z2, door_north)
    wall_v(x1, door_west)
    wall_v(x2, door_east)

    if group is not None:
        group.extend(ents)
    return ents

# ════════════════════════════════════════════════════
# CORRIDOR  (z=12-16, x=-1-69)
# ════════════════════════════════════════════════════
CORR_FC = C(55, 58, 72)
CORR_WC = C(68, 72, 90)
CORR_CC = C(90, 94, 114)

# Floor + ceiling
office_entities += [
    box((34, Y0+0.15,   14), (72, 0.30, 4), CORR_FC),
    box((34, Y0+ROOM_H+0.15, 14), (72, 0.30, 4), CORR_CC),
]
# Thick floor for corridor
_ct = Entity(model='cube', position=(34, Y0-1.5, 14), scale=(72, 3.5, 5), collider='box')
_ct.visible = False
office_entities.append(_ct)
# End walls
office_entities += [
    box((-1,  Y0+ROOM_H/2, 14), (0.30, ROOM_H, 4), CORR_WC, True),
    box((69,  Y0+ROOM_H/2, 14), (0.30, ROOM_H, 4), CORR_WC, True),
]
# Ceiling lights
for _lx in range(5, 68, 10):
    office_entities.append(box((_lx, Y0+ROOM_H-0.08, 14), (2.5, 0.07, 0.35), C(255,250,220)))

# ── Corridor wall decorations ────────────────────────
# Room name signs above doorways on SOUTH wall (z=12, north-facing rooms)
for _rname, _rcx in [('LOBBY',10),('CAFETERIA',32),('BREAK ROOM',53)]:
    office_entities.append(box((_rcx, Y0+ROOM_H-0.28, 12.2), (len(_rname)*0.55+1.2, 0.44, 0.12), PURPLE))
    _sl = Text(text=_rname, world_space=True,
               position=Vec3(_rcx, Y0+ROOM_H-0.28, 11.9),
               scale=10, origin=(0,0), color=Color(1,1,1,1))
    office_entities.append(_sl)

# Room name signs above doorways on NORTH wall (z=16, south-facing rooms)
for _rname, _rcx in [('SALES',8.5),('BSA',26),('FSS',43.5),('HR',60.5)]:
    office_entities.append(box((_rcx, Y0+ROOM_H-0.28, 15.8), (len(_rname)*0.55+1.2, 0.44, 0.12), PURPLE))
    _sl = Text(text=_rname, world_space=True,
               position=Vec3(_rcx, Y0+ROOM_H-0.28, 16.1),
               scale=10, origin=(0,0), color=Color(1,1,1,1))
    office_entities.append(_sl)

# Odoo posters on corridor walls (purple framed prints)
for _px, _pz, _pw in [(4,12.2,3.5),(17,12.2,3.5),(40,12.2,4),(20,15.8,3.5),(36,15.8,3.5),(50,15.8,3.5)]:
    office_entities += [
        box((_px, Y0+2.2, _pz), (_pw,   2.2,  0.10), C(80,50,140)),
        box((_px, Y0+2.2, _pz), (_pw-0.4,1.8, 0.08), C(114,46,209)),
    ]

# ════════════════════════════════════════════════════
# LOBBY  (x=0-20, z=0-12)  door_north cx=10
# ════════════════════════════════════════════════════
build_room(0,0, 20,12, Y0, ROOM_H,
           C(55,55,70), C(70,72,95), C(105,108,128),
           door_north=10, group=office_entities)

# Reception desk
office_entities += [
    box((10, Y0+0.9,  9),   (7,   0.9, 1.8), C(80,50,30),  True),
    box((10, Y0+1.4,  9),   (7.3, 0.06,2.0), C(110,70,40)),
    box((10, Y0+1.55, 9.5), (0.7, 0.4, 0.05),C(20,20,30)),
    box((10, Y0+1.55, 9.48),(0.58,0.3, 0.04),C(40,80,150)),
]
# Reception nameplate
office_entities.append(box((10, Y0+1.48, 7.8), (3, 0.14, 0.08), C(220,200,255)))

# Lobby Odoo sign
office_entities += [
    box((10, Y0+3.2, 11.7), (9.5, 1.0, 0.12), PURPLE),
    box((10, Y0+3.2, 11.6), (5.5, 0.65,0.09), C(140,80,220)),
]
_ls = Text(text='ODOO LIFE', world_space=True,
           position=Vec3(10, Y0+3.2, 11.4),
           scale=16, origin=(0,0), color=Color(1,1,1,1))
office_entities.append(_ls)

# Waiting chairs
for _xi in (3, 6, 14, 17):
    office_entities += [
        box((_xi, Y0+0.45, 4), (0.8,0.08,0.8), C(60,60,200), True),
        box((_xi, Y0+0.85, 4.4),(0.8,0.7, 0.08),C(60,60,200)),
    ]
# Carpet
office_entities.append(box((10, Y0+0.31, 6), (18, 0.04, 10), C(65,48,105)))
# Corner plants
for _px, _pz in ((1,1),(18,1),(1,10),(18,10)):
    office_entities += [
        box((_px, Y0+0.5, _pz), (0.8,0.8,0.8), C(80,55,30), True),
        box((_px, Y0+1.2, _pz), (0.6,0.9,0.6), C(30,110,30)),
        box((_px, Y0+1.65,_pz+0.3),(0.35,0.55,0.35),C(40,130,40)),
    ]

EXIT_DOOR_POS = Vec3(10, Y0+1.5, 0.5)
office_entities += [
    box((10, Y0+1.2, 0.4),  (2.2, 2.6,  0.25), C(100,68,30)),
    box((10, Y0+1.15,0.35), (1.8, 2.35, 0.15), C(139,95,50), True),
    box((11, Y0+1.1, 0.28), (0.1, 0.15, 0.12), C(200,170,50)),
]

# ════════════════════════════════════════════════════
# CAFETERIA  (x=21-43, z=0-12)  door_north cx=32
# ════════════════════════════════════════════════════
build_room(21,0, 43,12, Y0, ROOM_H,
           C(58,52,45), C(78,70,60), C(110,100,88),
           door_north=32, group=office_entities)

# Serving counter
office_entities += [
    box((35, Y0+1.05, 9),(10,1.0, 2.0), C(110,85,60), True),
    box((35, Y0+1.55, 9),(10.2,0.07,2.2),C(200,185,160)),
]
for _fi, _fc in enumerate((C(255,200,100),C(180,100,80),C(120,180,80))):
    office_entities.append(box((30+_fi*3, Y0+1.6, 8.5),(2,0.05,0.8),_fc))
# Shelves above counter
for _sx in (28,32,36,40):
    office_entities.append(box((_sx, Y0+2.4, 10.5),(3,0.08,0.7),C(140,100,60)))

# Menu board on back wall
office_entities += [
    box((32, Y0+3.5, 11.8),(18, 2.5, 0.12), C(35,55,35)),
    box((32, Y0+3.5, 11.7),(16, 2.1, 0.08), C(50,75,50)),
]
_ms = Text(text='CAFETERIA', world_space=True,
           position=Vec3(32, Y0+3.5, 11.5),
           scale=13, origin=(0,0), color=Color(0.8,1,0.8,1))
office_entities.append(_ms)

# Dining tables
for _row in range(2):
    for _col in range(3):
        _tx, _tz = 24+_col*5, 2+_row*5
        office_entities.append(box((_tx,Y0+0.72,_tz),(2.5,0.08,2.5),C(200,175,140),True))
        for _dx,_dz in ((1.3,0),(-1.3,0),(0,1.3),(0,-1.3)):
            office_entities.append(box((_tx+_dx,Y0+0.42,_tz+_dz),(0.6,0.08,0.6),C(180,75,75),True))

CAFETERIA_POS = Vec3(35, Y0+1.5, 9)

# ════════════════════════════════════════════════════
# BREAK ROOM  (x=44-62, z=0-12)  door_north cx=53
# ════════════════════════════════════════════════════
build_room(44,0, 62,12, Y0, ROOM_H,
           C(50,60,55), C(65,78,70), C(95,110,100),
           door_north=53, group=office_entities)

# Couch
office_entities += [
    box((53, Y0+0.3, 9.5),  (6,   0.55, 1.8), C(80,100,90),  True),
    box((53, Y0+0.72,9.5),  (6,   0.3,  1.8), C(100,125,115)),
    box((53, Y0+0.72,10.5), (6,   0.5,  0.18),C(90,112,105)),
    box((49.8,Y0+0.5,9.5),  (0.18,0.65, 1.6), C(75,95,88)),
    box((56.2,Y0+0.5,9.5),  (0.18,0.65, 1.6), C(75,95,88)),
]
COUCH_POS = Vec3(53, Y0+1.5, 9.5)

# Coffee machine
office_entities += [
    box((46.5,Y0+1.2, 10.5),(1.0, 2.0, 0.9), C(30,30,35), True),
    box((46.5,Y0+1.5, 10.0),(0.7, 0.4, 0.3), C(50,50,60)),
    box((46.5,Y0+1.55,10.0),(0.4, 0.15,0.2), C(20,20,22)),
    box((46.5,Y0+1.75,10.0),(0.3, 0.05,0.15),C(210,80,40)),
]
COFFEE_POS = Vec3(46.5, Y0+1.5, 10)

# Vending machine
office_entities += [
    box((60,  Y0+1.5, 10.5),(1.2, 2.8, 0.9), C(40,60,120), True),
    box((60,  Y0+1.5, 10.1),(0.9, 2.0, 0.3), C(20,35,80)),
    box((60,  Y0+1.5, 10.0),(0.8, 1.8, 0.2), C(30,50,110)),
]
for _vy in range(5):
    for _vx in range(2):
        _vc = (C(220,60,60),C(60,180,60),C(60,120,220),C(220,180,40),C(180,60,220))[_vy]
        office_entities.append(box((59.7+_vx*0.4, Y0+0.7+_vy*0.38, 10.05),(0.28,0.25,0.1),_vc))
VENDING_POS = Vec3(60, Y0+1.5, 10)

# Side table + mugs
office_entities += [
    box((50, Y0+0.6, 8),(1.0, 1.0, 1.0), C(70,90,80), True),
    box((50, Y0+1.1, 8),(1.1, 0.06,1.1), C(90,110,100)),
    box((50, Y0+1.2, 8),(0.2, 0.25,0.2), C(200,80,40)),
]

# Break room sign
_brs = Text(text='BREAK ROOM', world_space=True,
            position=Vec3(53, Y0+3.8, 11.5),
            scale=12, origin=(0,0), color=Color(0.85,1,0.9,1))
office_entities.append(_brs)

# ════════════════════════════════════════════════════
# DESK BUILDER (for dept rooms)
# ════════════════════════════════════════════════════
def make_desk(x, z, y=Y0, empty=False, group=None):
    dc   = C(90,65,35) if empty else C(130,95,50)
    ents = [box((x, y+0.78, z), (2.1,0.08,1.1), dc, True)]
    for _lx,_lz in ((-0.9,-0.4),(0.9,-0.4),(-0.9,0.4),(0.9,0.4)):
        ents.append(box((x+_lx,y+0.38,z+_lz),(0.1,0.76,0.1),C(70,50,25),True))
    if not empty:
        ents += [
            box((x,     y+0.84, z+0.35),(0.08,0.28,0.08),C(40,40,40)),
            box((x,     y+1.22, z+0.38),(0.85,0.50,0.06),C(20,20,35)),
            box((x,     y+1.22, z+0.36),(0.72,0.38,0.04),C(40,80,160)),
            box((x,     y+0.82, z-0.05),(0.80,0.03,0.35),C(60,60,65)),
            box((x+0.55,y+0.82, z+0.05),(0.12,0.03,0.2),C(50,50,55)),
            box((x-0.70,y+0.90, z+0.2), (0.15,0.22,0.15),C(200,80,40)),
            box((x-0.70,y+1.01, z+0.2), (0.13,0.04,0.13),C(30,15,5)),
            box((x,     y+0.42, z-0.65),(0.75,0.07,0.70),C(45,45,55),True),
            box((x,     y+0.82, z-0.95),(0.75,0.65,0.08),C(45,45,55)),
        ]
    else:
        ents += [
            box((x, y+0.82, z-0.05),(1.5,0.03,0.75),C(210,210,220)),
            box((x, y+0.42, z-0.65),(0.75,0.07,0.70),C(45,45,55),True),
            box((x, y+0.82, z-0.95),(0.75,0.65,0.08),C(45,45,55)),
        ]
    for _clx,_clz in ((-0.3,-0.25),(0.3,-0.25),(-0.3,0.25),(0.3,0.25)):
        ents.append(box((x+_clx,y+0.18,z-0.65+_clz),(0.07,0.42,0.07),C(60,60,70),True))
    if group is not None:
        group.extend(ents)
    return ents

# ════════════════════════════════════════════════════
# SALES DEPT  (x=0-17, z=16-36)  door_south cx=8.5
# ════════════════════════════════════════════════════
build_room(0,16, 17,36, Y0, ROOM_H,
           C(45,52,78), C(58,64,90), C(88,95,118),
           door_south=8.5, group=office_entities)
office_entities.append(box((8.5, Y0+3.8, 16.25),(10,0.45,0.12),PURPLE))
_ds = Text(text='SALES', world_space=True,
           position=Vec3(8.5,Y0+3.8,16.0),scale=14,origin=(0,0),color=Color(1,1,1,1))
office_entities.append(_ds)
# NPC desks
for _lx,_lz in ((3,22),(7,22),(11,22),(3,28),(7,28)):
    make_desk(_lx,_lz,Y0,group=office_entities)
# Player desk
make_desk(11,28,Y0,empty=True,group=office_entities)
# Manager desk
make_desk(8.5,33,Y0,group=office_entities)
# Dept carpet strip
office_entities.append(box((8.5,Y0+0.32,26),(15,0.04,18),C(40,48,72)))

# ════════════════════════════════════════════════════
# BSA DEPT  (x=18-34, z=16-36)  door_south cx=26
# ════════════════════════════════════════════════════
build_room(18,16, 34,36, Y0, ROOM_H,
           C(42,62,65), C(55,78,80), C(85,112,115),
           door_south=26, group=office_entities)
office_entities.append(box((26,Y0+3.8,16.25),(10,0.45,0.12),PURPLE))
_db = Text(text='BSA', world_space=True,
           position=Vec3(26,Y0+3.8,16.0),scale=14,origin=(0,0),color=Color(1,1,1,1))
office_entities.append(_db)
for _lx,_lz in ((21,22),(25,22),(29,22),(21,28),(25,28)):
    make_desk(_lx,_lz,Y0,group=office_entities)
make_desk(29,28,Y0,empty=True,group=office_entities)
make_desk(26,33,Y0,group=office_entities)
office_entities.append(box((26,Y0+0.32,26),(14,0.04,18),C(38,58,60)))

# ════════════════════════════════════════════════════
# FSS DEPT  (x=35-52, z=16-36)  door_south cx=43.5
# ════════════════════════════════════════════════════
build_room(35,16, 52,36, Y0, ROOM_H,
           C(62,55,45), C(80,70,58), C(115,102,85),
           door_south=43.5, group=office_entities)
office_entities.append(box((43.5,Y0+3.8,16.25),(10,0.45,0.12),PURPLE))
_df = Text(text='FSS', world_space=True,
           position=Vec3(43.5,Y0+3.8,16.0),scale=14,origin=(0,0),color=Color(1,1,1,1))
office_entities.append(_df)
for _lx,_lz in ((38,22),(42,22),(46,22),(38,28),(42,28)):
    make_desk(_lx,_lz,Y0,group=office_entities)
make_desk(46,28,Y0,empty=True,group=office_entities)
make_desk(43.5,33,Y0,group=office_entities)
office_entities.append(box((43.5,Y0+0.32,26),(15,0.04,18),C(58,50,40)))

# ════════════════════════════════════════════════════
# HR DEPT  (x=53-68, z=16-30)  door_south cx=60.5
# ════════════════════════════════════════════════════
build_room(53,16, 68,30, Y0, ROOM_H,
           C(55,45,70), C(70,58,90), C(105,88,130),
           door_south=60.5, group=office_entities)
office_entities.append(box((60.5,Y0+3.8,16.25),(8,0.45,0.12),PURPLE))
_dh = Text(text='HR', world_space=True,
           position=Vec3(60.5,Y0+3.8,16.0),scale=14,origin=(0,0),color=Color(1,1,1,1))
office_entities.append(_dh)
make_desk(60.5,26,Y0,group=office_entities)
# Small couch + plant in HR
office_entities += [
    box((55,Y0+0.4,28),(2.5,0.5,1.2),C(120,90,150),True),
    box((55,Y0+0.7,28),(2.5,0.25,1.2),C(150,115,180)),
    box((57.5,Y0+0.8,22),(0.6,1.4,0.6),C(40,120,40),True),
    box((57.5,Y0+1.6,22),(0.5,0.7,0.5),C(50,140,50)),
]

# ════════════════════════════════════════════════════
# HOME MAP  (small apartment)
# ════════════════════════════════════════════════════
HX, HY, HZ = 200, 0, 0   # offset so it doesn't overlap

def make_room(ox, oy, oz, w, d, h, fc, wc, cc, accent=True, group=None):
    cx, cz = ox+w/2, oz+d/2
    ents = [
        box((cx, oy+0.15,  cz), (w, 0.3,  d), fc, True),   # visible floor
        box((cx, oy+h+0.15,cz), (w, 0.3,  d), cc),
        box((cx, oy+h/2,   oz), (w, h,  0.3), wc, True),
        box((cx, oy+h/2, oz+d), (w, h,  0.3), wc, True),
        box((ox, oy+h/2,   cz), (0.3, h, d),  wc, True),
        box((ox+w,oy+h/2,  cz), (0.3, h, d),  wc, True),
    ]
    # Thick invisible collision floor — prevents falling through on teleport
    thick = Entity(model='cube', position=(cx, oy-2, cz),
                   scale=(w+1, 5, d+1), collider='box')
    thick.visible = False
    ents.append(thick)
    if accent:
        ents.append(box((cx, oy+h-0.3, oz+d-0.2), (w, 0.4, 0.1), PURPLE))
    # Ceiling light strips
    for lz_off in (d*0.3, d*0.7):
        ents.append(box((cx, oy+h-0.05, oz+lz_off), (w*0.7, 0.08, 0.4), C(255,250,220)))
    # Baseboard trim along floor edges
    ents += [
        box((cx,  oy+0.35, oz+0.18), (w,   0.3, 0.12), C(min(wc.r*1.3,1), min(wc.g*1.3,1), min(wc.b*1.3,1))),
        box((cx,  oy+0.35, oz+d-0.18),(w,  0.3, 0.12), C(min(wc.r*1.3,1), min(wc.g*1.3,1), min(wc.b*1.3,1))),
        box((ox+0.18, oy+0.35, cz),(0.12, 0.3, d),     C(min(wc.r*1.3,1), min(wc.g*1.3,1), min(wc.b*1.3,1))),
        box((ox+w-0.18,oy+0.35,cz),(0.12, 0.3, d),     C(min(wc.r*1.3,1), min(wc.g*1.3,1), min(wc.b*1.3,1))),
    ]
    if group is not None:
        group.extend(ents)
    return ents

make_room(HX, HY, HZ, 16, 12, 4, C(200,190,170), C(180,170,150), C(230,220,200),
          accent=False, group=home_entities)

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
    office_entities.extend([body, head, eye_l, eye_r, leg_l, leg_r, arm_l, arm_r])
    return data

# ── SALES ────────────────────────────────────────────
spawn_npc('Alex Kim',    'Sales Rep',    'Sales',  3,  22, Y0,
    {0:["Hey! Quota is looking great this month."]})
spawn_npc('Mia Torres',  'Sales Rep',    'Sales',  7,  22, Y0,
    {0:["Hi, welcome to the team!"],
     1:["Good to see you again. Settling in?","Feel free to ask me anything."],
     2:["You're getting the hang of it!","Pro tip: always CC your manager."],
     3:["Honestly, you're one of the good ones.","I know the pipeline inside-out."],
     4:["We should grab lunch sometime.","I've got your back on that project."]},
    True)
spawn_npc('Jake Osei',   'Sales Rep',    'Sales', 11,  22, Y0,
    {0:["Closing deals, one at a time."]})
spawn_npc('Priya Nair',  'Sales Rep',    'Sales',  3,  28, Y0,
    {0:["Sales dashboards are honestly beautiful."],
     1:["Hit me up if you want tips on clients.","I track every metric religiously."],
     2:["Our close rate is up this quarter!","Check the CRM for the latest leads."],
     3:["You remind me of myself starting out.","Here's how I manage my pipeline..."],
     4:["You're basically part of my squad now.","Let's strategize on that big account."]},
    True)
spawn_npc('Leo Chan',    'Sales Rep',    'Sales',  7,  28, Y0,
    {0:["Running late on a follow-up, brb."]})
spawn_npc('Sandra Bloom','Sales Manager','Sales',  8.5,33, Y0,
    {0:["Welcome to the Sales team!"],
     1:["Let me know if you need anything.","Numbers are looking good."],
     2:["I see potential in you.","Keep those conversion rates up."],
     3:["Honestly, you're one of my top picks.","Here's what I look for in talent..."],
     4:["I'm pushing for your promotion.","Between us — big client coming soon."]},
    True)

# ── BSA ──────────────────────────────────────────────
spawn_npc('Ravi Patel',  'Business Analyst','BSA', 21, 22, Y0,
    {0:["Documentation never sleeps."]})
spawn_npc('Chloe Martin','Business Analyst','BSA', 25, 22, Y0,
    {0:["Requirements gathering is an art."],
     1:["Want to review a spec together?","I love a good flowchart."],
     2:["You write clean requirements.","Let me share my template with you."],
     3:["We work really well together.","Here's how I handle scope creep..."],
     4:["You're my go-to for workshops now.","We should co-author the next spec."]},
    True)
spawn_npc('Tom Reyes',   'Business Analyst','BSA', 29, 22, Y0,
    {0:["Gap analysis? On it."]})
spawn_npc('Sara Wolfe',  'Business Analyst','BSA', 21, 28, Y0,
    {0:["I live in spreadsheets."],
     1:["Let me know if you need a process mapped.","Excel is my second language."],
     2:["Your process diagrams are great.","I'll teach you my BPMN shortcuts."],
     3:["I can always count on your analysis.","Here's the stakeholder map I use..."],
     4:["We make a great analytical team.","I'll put you on my next workshop."]},
    True)
spawn_npc('Ben Foster',  'Business Analyst','BSA', 25, 28, Y0,
    {0:["User stories are my love language."]})
spawn_npc('Diana Cross', 'BSA Manager',    'BSA', 26, 33, Y0,
    {0:["Welcome to the BSA floor!"],
     1:["We keep things structured here.","Any questions, just ask."],
     2:["Your documentation is getting better.","I appreciate your thoroughness."],
     3:["You've got good analytical instincts.","Let me show you the project board."],
     4:["You're BSA material for sure.","I'm recommending you for the big project."]},
    True)

# ── FSS ──────────────────────────────────────────────
spawn_npc('Nina Park',  'Functional Support','FSS', 38, 22, Y0,
    {0:["Ticket resolved. Next!"]})
spawn_npc('Omar Diaz',  'Functional Support','FSS', 42, 22, Y0,
    {0:["I know Odoo modules like the back of my hand."],
     1:["Need help with a feature? I got you.","Every module has its quirks."],
     2:["You're picking up Odoo fast.","Here's a hidden config trick..."],
     3:["I trust your instincts on support cases.","Let me walk you through the APIs."],
     4:["You're basically an Odoo expert now.","Let's tackle that complex ticket together."]},
    True)
spawn_npc('Yuki Abe',   'Functional Support','FSS', 46, 22, Y0,
    {0:["Config or customization? That is the question."]})
spawn_npc('Finn Kelly', 'Functional Support','FSS', 38, 28, Y0,
    {0:["Just fixed something I did not know was broken."],
     1:["Ping me if you get stuck.","I've seen every error code twice."],
     2:["You debug like a pro.","Here's how I reproduce tricky bugs..."],
     3:["We make a good support duo.","I'll loop you in on the hard tickets."],
     4:["Honestly you're the best on the team.","Let's write a guide together."]},
    True)
spawn_npc('Ana Silva',  'Functional Support','FSS', 42, 28, Y0,
    {0:["Functional support is honestly underrated."]})
spawn_npc('Marcus Reid','Support Manager',  'FSS', 43.5,33,Y0,
    {0:["Hey, welcome to FSS!"],
     1:["We move fast here.","Proud of this team."],
     2:["Your response times are great.","Keep that SLA green."],
     3:["I want you leading the next onboarding.","Real talk — you've impressed me."],
     4:["You're my top candidate for team lead.","Here's what's coming next quarter..."]},
    True)

# ── HR ───────────────────────────────────────────────
spawn_npc('Grace Tan',  'HR Manager',    'HR',  60.5,26, Y0,
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
# HUD  — clean corporate top bar
# ════════════════════════════════════════════════════
_BAR_Y   = 0.455   # vertical centre of top bar
_BAR_H   = 0.090   # bar height

# Full-width dark background
Entity(parent=camera.ui, model='quad',
       scale=(2.0, _BAR_H), position=(0, _BAR_Y),
       color=C(10, 8, 22, 228), z=1)
# Thin purple rule at very top
Entity(parent=camera.ui, model='quad',
       scale=(2.0, 0.004), position=(0, _BAR_Y + _BAR_H/2 - 0.002),
       color=PURPLE, z=0)
# Thin separator at bottom of bar
Entity(parent=camera.ui, model='quad',
       scale=(2.0, 0.002), position=(0, _BAR_Y - _BAR_H/2 + 0.001),
       color=C(50, 40, 80, 180), z=0)

# ── Left: MOOD bar ──────────────────────────────────
_ML = -0.87   # mood left edge
Text(text='MOOD', parent=camera.ui,
     position=(_ML, _BAR_Y+0.018), origin=(-0.5,0),
     scale=1.05, color=C(200,100,130,255))
Entity(parent=camera.ui, model='quad',          # track
       scale=(0.095, 0.011), position=(_ML+0.0475, _BAR_Y+0.001),
       color=C(35,20,30,200), z=0)
_mood_fill = Entity(parent=camera.ui, model='quad',
                    scale=(0.095, 0.011), position=(_ML+0.0475, _BAR_Y+0.001),
                    color=C(210,65,105), z=-0.1)
_mood_val = Text(text='', parent=camera.ui,
                 position=(_ML+0.103, _BAR_Y+0.018), origin=(-0.5,0),
                 scale=1.15, color=Color(1,1,1,1))

# Vertical divider
Entity(parent=camera.ui, model='quad',
       scale=(0.002, 0.062), position=(-0.73, _BAR_Y),
       color=C(55,45,85,180), z=0)

# ── ENERGY bar ──────────────────────────────────────
_EL = -0.72
Text(text='ENERGY', parent=camera.ui,
     position=(_EL, _BAR_Y+0.018), origin=(-0.5,0),
     scale=1.05, color=C(80,190,120,255))
Entity(parent=camera.ui, model='quad',
       scale=(0.095, 0.011), position=(_EL+0.0475, _BAR_Y+0.001),
       color=C(20,32,24,200), z=0)
_energy_fill = Entity(parent=camera.ui, model='quad',
                      scale=(0.095, 0.011), position=(_EL+0.0475, _BAR_Y+0.001),
                      color=C(50,190,100), z=-0.1)
_energy_val = Text(text='', parent=camera.ui,
                   position=(_EL+0.103, _BAR_Y+0.018), origin=(-0.5,0),
                   scale=1.15, color=Color(1,1,1,1))

# Vertical divider
Entity(parent=camera.ui, model='quad',
       scale=(0.002, 0.062), position=(-0.565, _BAR_Y),
       color=C(55,45,85,180), z=0)

# ── Centre: name / money / xp / level ───────────────
_CX = -0.545
hud_name_txt = Text(text='', parent=camera.ui,
                    position=(_CX, _BAR_Y+0.018), origin=(-0.5,0),
                    scale=1.35, color=Color(1,1,1,1))
hud_money_xp = Text(text='', parent=camera.ui,
                    position=(_CX, _BAR_Y+0.000), origin=(-0.5,0),
                    scale=1.1, color=C(220,185,60,255))

# Vertical divider right of centre
Entity(parent=camera.ui, model='quad',
       scale=(0.002, 0.062), position=(0.42, _BAR_Y),
       color=C(55,45,85,180), z=0)

# ── Right: clock + location ──────────────────────────
hud_clock = Text(text='', parent=camera.ui,
                 position=(0.87, _BAR_Y+0.018), origin=(0.5,0),
                 scale=1.3, color=Color(1,1,0.75,1))
hud_floor = Text(text='', parent=camera.ui,
                 position=(0.87, _BAR_Y+0.000), origin=(0.5,0),
                 scale=1.1, color=C(160,135,210,255))

# ── Bottom hint ──────────────────────────────────────
_hint_bg = Entity(parent=camera.ui, model='quad',
                  scale=(0.60, 0.044), position=(0, -0.40),
                  color=C(10,8,22,210), z=1, visible=False)
Entity(parent=_hint_bg, model='quad',          # left accent bar
       scale=(0.012, 1.0), position=(-0.494, 0),
       color=PURPLE, z=-0.1)
hud_hint = Text(text='', parent=camera.ui,
                position=(0, -0.400), origin=(0,0),
                scale=1.5, color=Color(1,1,1,1), visible=False)

hud_keys = Text(text='WASD  Move   |   Mouse  Look   |   E  Interact   |   Q  Quit',
                position=(0, -0.465), origin=(0,0), scale=1.05,
                color=Color(0.45,0.45,0.55,1))

# kept for legacy refs (unused visually now)
hud_stats = Text(text='', visible=False)

def _set_bar(fill_ent, left_x, bar_w, val_0_1):
    w = max(0.001, bar_w * val_0_1)
    fill_ent.scale_x = w
    fill_ent.x       = left_x + w / 2

def _get_room(pos):
    x, z = pos.x, pos.z
    if 12 <= z <= 16: return 'Corridor'
    if z < 12:
        if  0 <= x <= 20: return 'Lobby'
        if 21 <= x <= 43: return 'Cafeteria'
        if 44 <= x <= 62: return 'Break Room'
    if z > 16:
        if  0 <= x <= 17: return 'Sales'
        if 18 <= x <= 34: return 'BSA'
        if 35 <= x <= 52: return 'FSS'
        if 53 <= x <= 68: return 'HR'
    return 'Office'

def update_hud():
    lvl   = stats['level']
    title = LEVEL_TITLES[lvl]
    _set_bar(_mood_fill,   _ML, 0.095, stats['mood']   / 100)
    _set_bar(_energy_fill, _EL, 0.095, stats['energy'] / 100)
    _mood_val.text   = str(stats['mood'])
    _energy_val.text = str(stats['energy'])
    hud_name_txt.text = f"{stats['name']}  —  Lv{lvl} {title}"
    hud_money_xp.text = f"${stats['money']}    {stats['xp']} xp"
    h    = int(hour)
    m    = int((hour - h) * 60)
    ampm = 'AM' if h < 12 else 'PM'
    h12  = h % 12 or 12
    dow  = day_names[(day-1) % 7]
    hud_clock.text = f"{h12}:{m:02d} {ampm}   Day {day} {dow}"
    loc = _get_room(player.position) if game_state in ('work','evening') else game_state.capitalize()
    hud_floor.text = loc

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
near_bed           = False
near_phone         = False
near_home_door     = False
near_bar_counter   = False
near_bar_door      = False
near_cafeteria     = False
near_player_desk   = False
near_coffee        = False
near_vending       = False
near_couch_break   = False

def show_notification(msg, duration=3.0):
    global notification_panel
    if notification_panel:
        destroy(notification_panel)
    notification_panel = Entity(parent=camera.ui, model='quad',
                                scale=(.62, .058), position=(0, .22),
                                color=C(10, 8, 22, 235), z=-1)
    # Left accent bar
    Entity(parent=notification_panel, model='quad',
           scale=(0.014, 1.0), position=(-0.493, 0),
           color=PURPLE, z=-0.1)
    # Bottom rule
    Entity(parent=notification_panel, model='quad',
           scale=(1.0, 0.04), position=(0, -0.48),
           color=PURPLE, z=-0.1)
    Text(parent=notification_panel, text=msg,
         position=(0.01, 0), origin=(0, 0), scale=1.85,
         color=Color(1, 1, 1, 1))
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
    hud_hint.visible = False; _hint_bg.visible = False

    lvl  = friendship.get(npc['name'], 0)
    dial = npc['dialogue']
    # Get lines for current friendship level (fallback to 0)
    lines = dial.get(lvl, dial.get(0, ['...']))
    line  = random.choice(lines)

    if npc['relationship']:
        friendship[npc['name']] = min(5, lvl + 1)
        stats['mood'] = min(100, stats['mood'] + 3)

    dept_col = DEPT_COL.get(npc['dept'], PURPLE)
    # panel: 0.84 wide, 0.34 tall — portrait on left, content on right
    dialogue_panel = Entity(parent=camera.ui, model='quad',
                            scale=(.84, .34), position=(0, -.15),
                            color=C(10, 8, 22, 245), z=-1)
    # Thin purple rule at top
    Entity(parent=dialogue_panel, model='quad',
           scale=(1.0, 0.012), position=(0, 0.494),
           color=PURPLE, z=-0.1)
    # ── Portrait block (left 22% of panel) ──────────
    Entity(parent=dialogue_panel, model='quad',
           scale=(0.22, 1.0), position=(-0.39, 0.0),
           color=dept_col, z=-0.1)
    # dept colour inner shadow
    Entity(parent=dialogue_panel, model='quad',
           scale=(0.19, 0.96), position=(-0.39, 0.0),
           color=C(int(dept_col.r*200), int(dept_col.g*200), int(dept_col.b*200), 60), z=-0.2)
    # Initial letter
    Text(parent=dialogue_panel,
         text=npc['name'][0], position=(-0.39, 0.10), origin=(0,0),
         scale=6.0, color=Color(1,1,1,0.95))
    # Dept label at bottom of portrait
    Text(parent=dialogue_panel,
         text=npc['dept'], position=(-0.39, -0.36), origin=(0,0),
         scale=1.4, color=Color(1,1,1,0.75))
    # ── Content (right side, x from -0.25 to +0.48) ─
    CX = -0.24   # left-align anchor for content
    Text(parent=dialogue_panel,
         text=npc['name'], position=(CX, 0.32), origin=(-0.5, 0),
         scale=2.5, color=Color(1, 1, 1, 1))
    Text(parent=dialogue_panel,
         text=npc['role'], position=(CX, 0.15), origin=(-0.5, 0),
         scale=1.5, color=Color(180/255, 140/255, 255/255, 1))
    if npc['relationship']:
        Text(parent=dialogue_panel,
             text=hearts(npc['name']), position=(CX, 0.02), origin=(-0.5, 0),
             scale=1.45, color=C(215, 80, 110, 255))
    # Divider
    Entity(parent=dialogue_panel, model='quad',
           scale=(0.68, 0.005), position=(0.12, -0.08),
           color=C(55, 45, 90, 200), z=-0.1)
    # Quote
    Text(parent=dialogue_panel,
         text=f'"{line}"', position=(CX, -0.22), origin=(-0.5, 0),
         scale=1.85, color=Color(1, 1, 1, 1))
    # Close hint
    Text(parent=dialogue_panel,
         text='E — Close', position=(0.46, -0.45), origin=(0.5, 0),
         scale=1.35, color=Color(0.45, 0.45, 0.55, 1))

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
                        scale=(.65,.28), position=(0,.1),
                        color=C(6,22,12,240), z=-1)
    # Green top stripe
    Entity(parent=task_panel, model='quad',
           scale=(1, 0.1), position=(0, 0.46),
           color=C(30,140,60,230), z=-0.1)
    Text(parent=task_panel,
         text='NEW TASK', position=(0, .42), origin=(0,0),
         scale=2.0, color=Color(0.4,1,0.5,1))
    Text(parent=task_panel,
         text=current_task['text'],
         position=(0, .16), origin=(0,0), scale=2.0, color=Color(1,1,1,1))
    Entity(parent=task_panel, model='quad',
           scale=(0.85,0.008), position=(0,0.04),
           color=C(40,100,50,200), z=-0.1)
    Text(parent=task_panel,
         text=f"+{current_task['xp']} XP     +${current_task['money']}",
         position=(0,-.1), origin=(0,0), scale=1.9, color=Color(0.5,1,0.4,1))
    Text(parent=task_panel,
         text='[ E ] Accept          [ X ] Skip',
         position=(0,-.38), origin=(0,0), scale=1.55, color=Color(.7,.7,.7,1))

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
# MAP VISIBILITY
# ════════════════════════════════════════════════════
def show_map(name):
    for group, gname in [(office_entities,'office'),
                          (home_entities,'home'),(bar_entities,'bar')]:
        vis = (gname == name)
        for e in group:
            e.enabled = vis
    for n in npcs:
        vis = (name == 'office')
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
    show_map('office')
    player.position   = Vec3(10, 1.5, 6)
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
    global nearest_npc, near_exit, near_bed
    global near_phone, near_home_door, near_bar_counter, near_bar_door
    global near_cafeteria, near_player_desk, _desk_timer
    global near_coffee, near_vending, near_couch_break
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

    if dialogue_open or task_active or phone_menu_open:
        hud_hint.visible = False; _hint_bg.visible = False
        return

    # ── Proximity checks ─────────────────────────────
    near_exit        = False
    near_bed         = False
    near_phone       = False
    near_home_door   = False
    near_bar_counter = False
    near_bar_door    = False
    near_cafeteria   = False
    near_player_desk = False
    near_coffee      = False
    near_vending     = False
    near_couch_break = False
    nearest_npc      = None

    # NPC proximity (work floors)
    if game_state in ('work','evening'):
        best_d = 2.8
        for npc in npcs:
            d = (p - npc['pos']).length()
            if d < best_d:
                best_d, nearest_npc = d, npc

        if game_state == 'evening':
            near_exit = (p - EXIT_DOOR_POS).length() < 2.5

        if game_state == 'work':
            desk_pos = PLAYER_DESK_POS.get(stats['dept'])
            if desk_pos and (p - desk_pos).length() < 2.5:
                near_player_desk = True

        near_cafeteria = (p - CAFETERIA_POS).length() < 3.0

        if game_state == 'work':
            near_coffee      = (p - COFFEE_POS).length()  < 2.5
            near_vending     = (p - VENDING_POS).length() < 2.5
            near_couch_break = (p - COUCH_POS).length()   < 2.5

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
    elif near_player_desk:
        hint = '[ E ] Sit at your desk' if not sitting_at_desk else '[ E ] Stand up'
    elif near_cafeteria:
        hint = '[ E ] Buy lunch (+20 energy, -$5)'
    elif near_coffee:
        hint = '[ E ] Get coffee (+20 energy, -$3)'
    elif near_vending:
        hint = '[ E ] Vending machine (+15 mood, -$2)'
    elif near_couch_break:
        hint = '[ E ] Rest on couch (+25 energy) [risky]'
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

    hud_hint.text      = hint
    hud_hint.visible   = bool(hint)
    _hint_bg.visible   = bool(hint)

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

        if near_player_desk and game_state == 'work':
            sitting_at_desk = not sitting_at_desk
            _desk_timer = 0.0
            if not sitting_at_desk:
                dismiss_task()
            player.speed = 0 if sitting_at_desk else 5
            show_notification('Sitting at desk — tasks incoming!' if sitting_at_desk else 'Stood up.')
            return

        if near_coffee and game_state == 'work':
            if stats['money'] >= 3:
                stats['money'] -= 3
                stats['energy'] = min(100, stats['energy'] + 20)
                show_notification('Coffee! +20 Energy  -$3')
            else:
                show_notification('Not enough money.')
            return

        if near_vending and game_state == 'work':
            if stats['money'] >= 2:
                stats['money'] -= 2
                stats['mood'] = min(100, stats['mood'] + 15)
                show_notification('Snack! +15 Mood  -$2')
            else:
                show_notification('Not enough money.')
            return

        if near_couch_break and game_state == 'work':
            stats['energy'] = min(100, stats['energy'] + 25)
            # 40% chance of being caught by a manager or HR
            import random as _r
            MANAGERS = {
                'Sales': 'Sandra Bloom', 'BSA': 'Diana Cross',
                'FSS': 'Marcus Reid',    'HR':  'Grace Tan',
            }
            if _r.random() < 0.40:
                dept_mgr = MANAGERS.get(stats['dept'], 'Sandra Bloom')
                catchers = list({dept_mgr, 'Grace Tan'})
                caught_by = _r.choice(catchers)
                for n in npcs:
                    if n['name'] == caught_by and n['relationship']:
                        friendship[caught_by] = max(0, friendship.get(caught_by,0) - 1)
                show_notification(f'Caught napping by {caught_by}!  -1 relationship', 4.0)
            else:
                show_notification('+25 Energy  (nobody saw you)')
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

# Hide all maps until game starts
for e in office_entities + home_entities + bar_entities:
    e.enabled = False
for n in npcs:
    for part in n.get('parts', [n['body'], n['head']]):
        part.enabled = False
    n['label'].enabled = False

cc_panel = Entity(parent=camera.ui, model='quad',
                  scale=(.65,.68), color=C(8,6,22,248), z=-1)
# Purple top bar
Entity(parent=cc_panel, model='quad', scale=(1,.12),
       position=(0,.46), color=PURPLE, z=-0.1)
Text(parent=cc_panel, text='ODOO LIFE',
     position=(0,.46), origin=(0,0), scale=5.0,
     color=Color(1,1,1,1))
Text(parent=cc_panel, text='Your Odoo career starts here',
     position=(0,.34), origin=(0,0), scale=1.8,
     color=Color(180/255,140/255,255/255,1))

# Divider
Entity(parent=cc_panel, model='quad', scale=(0.88,.006),
       position=(0,.27), color=C(80,50,140,200), z=-0.1)

Text(parent=cc_panel, text='Your Name',
     position=(-.3,.18), origin=(0,0), scale=1.7,
     color=Color(.7,.7,.8,1))
name_field = InputField(parent=cc_panel, position=(0.08,.18),
                        scale=(.34,.048), default_value='YourName')

Text(parent=cc_panel, text='Choose Your Department',
     position=(0,.05), origin=(0,0), scale=1.75,
     color=Color(.7,.7,.8,1))

DEPT_DESC = {
    'Sales': 'Close deals & grow revenue',
    'BSA':   'Analyse & document processes',
    'FSS':   'Support & configure Odoo',
}
selected_dept = ['Sales']
dept_btns     = []
dept_desc_txt = Text(parent=cc_panel,
                     text=DEPT_DESC['Sales'],
                     position=(0,-.18), origin=(0,0), scale=1.5,
                     color=Color(.6,.8,.6,1))

def select_dept(d):
    selected_dept[0] = d
    dept_desc_txt.text = DEPT_DESC[d]
    for b, bd in dept_btns:
        b.color          = DEPT_COL[bd]
        b.text_color     = Color(1,1,1,1) if bd == d else Color(.6,.6,.6,1)
        b.scale_y        = .065 if bd == d else .055

for i, d in enumerate(('Sales','BSA','FSS')):
    xi = -0.20 + i * 0.20
    b  = Button(parent=cc_panel, text=d,
                position=(xi, -.07), scale=(.16,.055),
                color=DEPT_COL[d] if i==0 else C(50,50,70),
                highlight_color=C(140,80,230),
                text_color=Color(1,1,1,1) if i==0 else Color(.6,.6,.6,1))
    b.on_click = lambda dept=d: select_dept(dept)
    dept_btns.append((b, d))

def start_game():
    global game_state
    stats['name'] = name_field.text or 'Player'
    stats['dept'] = selected_dept[0]
    destroy(cc_panel)
    player.enabled = True
    game_state = 'work'
    show_map('office')
    player.position = Vec3(10, 1.5, 6)
    mouse.locked  = True
    mouse.visible = False
    update_hud()

start_btn = Button(parent=cc_panel, text='Start Game  ->',
                   position=(0,-.35), scale=(.30,.07),
                   color=PURPLE, highlight_color=C(140,80,230),
                   text_color=Color(1,1,1,1))
start_btn.on_click = start_game

app.run()
