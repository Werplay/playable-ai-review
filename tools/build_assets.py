"""Extract Explottens art from the Unity project into the playable's assets/ folder.

Characters are baked as horizontal sprite strips from their Spine animations
(player: flying1, everyone else: idle) rather than single setup-pose frames.
Cells are sized at ~1.35x their on-screen size — anything larger is paid for twice,
once in PNG bytes and again in base64 inflation.
"""
import os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spinestrip

U = '/Users/zeeshan/Desktop/work/Explottens-FtP/ExplottensUnityProject/Assets'
OUT = '/Users/zeeshan/Desktop/work/playable-explottens-survivor/assets'
NE = U + '/SpineObjects/EnemiesCombined/NormalEnemies/'
BO = U + '/SpineObjects/EnemiesCombined/Bots/'
PL = U + '/SpineObjects/Player/UpdatedPlayer/'
os.makedirs(OUT, exist_ok=True)
sizes = {}

def put(im, name, colors=64):
    if colors:
        im = im.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.NONE).convert('RGBA')
    p = os.path.join(OUT, name)
    im.save(p, optimize=True)
    sizes[name] = os.path.getsize(p)

def fit(im, w):
    bb = im.getbbox()
    if bb: im = im.crop(bb)
    return im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)

def flat(rel, name, w, colors=64):
    put(fit(Image.open(U + rel).convert('RGBA'), w), name, colors)

def tp(sheet, sheet_h, x, y, w, h):
    return Image.open(sheet).convert('RGBA').crop((x, sheet_h - y - h, x + w, sheet_h - y))

# ---- animated characters ------------------------------------------------
# (name, skeleton, atlas, animation, frames, cell width, skin)
CHARS = [
    ('player',        PL + 'player.json',      PL + 'player.atlas.txt',       'flying1', 8,  90, 'playerPlane1'),
    ('e_furry',       NE + 'Furry.json',       NE + 'EnemyPlanes.atlas.txt',  'idle', 5,  60, 'default'),
    ('e_feline',      NE + 'Feline.json',      NE + 'EnemyPlanes.atlas.txt',  'idle', 5,  65, 'default'),
    ('e_bomberkitty', NE + 'BomberKitty.json', NE + 'EnemyPlanes.atlas.txt',  'idle', 5,  70, 'default'),
    ('e_razorclaw',   NE + 'RazorClaw.json',   NE + 'EnemyPlanes.atlas.txt',  'idle', 5,  73, 'default'),
    ('e_hammerhead',  NE + 'HammerHead.json',  NE + 'EnemyPlanes.atlas.txt',  'idle', 5, 110, 'default'),
    ('e_speedbug',    BO + 'SpeedBug.json',    BO + 'BugBots.atlas.txt',      'idle', 5,  46, 'default'),
    ('e_helmetbee',   BO + 'HelmetBee.json',   BO + 'BugBots.atlas.txt',      'idle', 5,  46, 'default'),
    ('e_ladybug',     BO + 'LadyBug.json',     BO + 'BugBots.atlas.txt',      'idle', 5,  49, 'default'),
    ('e_boss',        NE + 'vaderboss.json',   NE + 'EnemyPlanes.atlas.txt',  'idle', 4, 200, 'default'),
]

frames_meta = {}
for name, skel, atlas, anim, frames, cw, skin in CHARS:
    im, w, h = spinestrip.strip(skel, atlas, anim, frames, cw, skin)
    put(im, name + '.png')
    frames_meta[name] = (w, h, frames)
    print('%-14s %d frames  cell %dx%d' % (name, frames, w, h))

# ---- collectibles (TexturePacker sheet, bottom-left origin) --------------
C = U + '/Sprites/Collectibles/Collectible.png'
for name, (x, y, w, h), ow in [
    ('gem_green', (436, 214, 59, 65), 26), ('gem_blue', (436, 82, 58, 65), 26),
    ('gem_gold', (436, 149, 59, 63), 26), ('meat', (1, 232, 128, 131), 34)
]:
    put(fit(tp(C, 512, x, y, w, h), ow), name + '.png', 48)

# ---- bullets / weapon projectiles ---------------------------------------
A = '/Resources/Sprites_Res/Arsenal/'
flat(A + 'LongBullet7.png', 'bullet.png', 56, 48)
flat(A + 'LongBullet1.png', 'bullet_long.png', 64, 48)
flat(A + 'bread.png', 'w_croissant.png', 34)
flat(A + 'ball.png', 'w_yarnball.png', 32)
flat(A + 'protonBullet.png', 'w_propeller.png', 34)
flat(A + 'fish.png', 'w_fish.png', 36)
flat('/Sprites/Arsenal/shield.png', 'w_shield.png', 160, 32)

# ---- skill icons --------------------------------------------------------
ICONS = [
    ('multicanon', '/Resources/UI/Item/EquipmentSprites/multiCannonIcon.png'),
    ('croissant',  '/Resources/Sprites_Res/Arsenal/bread.png'),
    ('lightning',  '/Resources/UI/Item/PassiveSprites/LightningIcon.png'),
    ('shield',     '/Resources/UI/Item/PassiveSprites/shield.png'),
    ('propeller',  '/Resources/Sprites_Res/Arsenal/protonBullet.png'),
    ('yarnball',   '/Resources/Sprites_Res/Arsenal/ball.png'),
    ('razorfin',   '/Resources/UI/Item/PassiveSprites/Heal.png'),
    ('warmachine', '/Resources/UI/Item/EquipmentSprites/WarMachineIcon.png'),
    ('attack',     '/Resources/UI/Item/PassiveSprites/attack.png'),
    ('speed',      '/Resources/UI/Item/PassiveSprites/speed.png'),
    ('health',     '/Resources/UI/Item/PassiveSprites/health.png'),
    ('armor',      '/Resources/UI/Item/PassiveSprites/armor.png'),
    ('magnet',     '/Resources/UI/Item/PassiveSprites/HiPowerMagnet.png'),
    ('xp',         '/Resources/UI/Item/PassiveSprites/Experience.png'),
    ('cooldown',   '/Resources/UI/Item/PassiveSprites/Energycube 1.png'),
    ('bulletspeed','/Resources/UI/Item/PassiveSprites/Bulletspeed.png'),
]
for name, rel in ICONS:
    flat(rel, 'i_%s.png' % name, 72, 48)

# ---- hud + background ---------------------------------------------------
for name, rel in [('hud_time', '/Survival/Time_Icon.png'), ('hud_kills', '/Survival/Kills_Icon.png'),
                  ('hud_wave', '/Survival/Wave_Icon.png')]:
    flat(rel, name + '.png', 40, 48)

BGP = U + '/BG/BGDataNew/BGAssets/BGDay/SpriteSheet/BG_Day_SpriteSheet.png'
put(tp(BGP, 1912, 1059, 508, 25, 56).resize((8, 512), Image.LANCZOS), 'sky.png', 0)
flat('/BG/BGDataOld/OtheBackgrounds/BG- Misc/clouds1.png', 'clouds1.png', 560, 32)
flat('/BG/BGDataOld/OtheBackgrounds/BG- Misc/clouds3.png', 'clouds2.png', 560, 32)
put(Image.open(U + '/iTunesArtwork@2x.png').convert('RGBA').resize((180, 180), Image.LANCZOS), 'appicon.png', 96)

for stale in ('coin.png', 'magnet.png', 'chest.png'):
    p = os.path.join(OUT, stale)
    if os.path.exists(p): os.remove(p)

for k in sorted(sizes): print('%8d  %s' % (sizes[k], k))
print('TOTAL %.2f MB' % (sum(sizes.values()) / 1048576))
print('FRAMES', frames_meta)
