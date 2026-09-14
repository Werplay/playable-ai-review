"""Extract Explottens art from the Unity project into the playable's assets/ folder.

Enemies are baked as horizontal sprite strips from their `idle` Spine animations rather
than single setup-pose frames. The player is not here: it ships the live skeleton instead,
built by build_spine.py, so it can roll through `flip1` on a direction switch.

Frame count is the animation's own duration x 30: every skeleton here is authored on
a 30fps grid (keyframes all land on 1/30s boundaries, and Spine omits `skeleton.fps`
when it equals its 30 default), so this reproduces the in-game playback rate exactly.

Cell width is the on-screen size, 1:1. The game canvas is CSS-pixel sized, not
device-pixel sized, so anything beyond 1x is invisible and paid for twice - once in
PNG bytes, again in base64 inflation.
"""
import os, re, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spinestrip

U = '/Users/zeeshan/Desktop/work/Explottens-FtP/ExplottensUnityProject/Assets'
OUT = '/Users/zeeshan/Desktop/work/playable-explottens-survivor/assets'
NE = U + '/SpineObjects/EnemiesCombined/NormalEnemies/'
BO = U + '/SpineObjects/EnemiesCombined/Bots/'
EX = U + '/SpineObjects/Arsenal/Explosion/'
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
SPINE_FPS = 30  # authoring rate of every skeleton in this project
OVERSAMPLE = 1.0

# (name, skeleton, atlas, animation, on-screen width, skin)
CHARS = [
    ('e_furry',       NE + 'Furry.json',       NE + 'EnemyPlanes.atlas.txt', 'idle',     44, 'default'),
    ('e_feline',      NE + 'Feline.json',      NE + 'EnemyPlanes.atlas.txt', 'idle',     48, 'default'),
    ('e_bomberkitty', NE + 'BomberKitty.json', NE + 'EnemyPlanes.atlas.txt', 'idle',     52, 'default'),
    ('e_razorclaw',   NE + 'RazorClaw.json',   NE + 'EnemyPlanes.atlas.txt', 'idle',     54, 'default'),
    ('e_hammerhead',  NE + 'HammerHead.json',  NE + 'EnemyPlanes.atlas.txt', 'idle',     81, 'default'),
    ('e_speedbug',    BO + 'SpeedBug.json',    BO + 'BugBots.atlas.txt',     'idle',     34, 'default'),
    ('e_helmetbee',   BO + 'HelmetBee.json',   BO + 'BugBots.atlas.txt',     'idle',     34, 'default'),
    ('e_ladybug',     BO + 'LadyBug.json',     BO + 'BugBots.atlas.txt',     'idle',     36, 'default'),
    # vaderboss ships two idle loops; idle2 is the shorter one, same 30fps, half the bytes
    ('e_boss',        NE + 'vaderboss.json',   NE + 'EnemyPlanes.atlas.txt', 'idle2',   150, 'default'),
    # Enemy death burst. Unity rolls Air2/Aoe/Player (Enemy.SpawnExplosions); two of the
    # three land on explosion4/5, so the playable bakes explosion4 and reuses it.
    ('boom',          EX + 'explosion.json',   EX + 'explosion.atlas.txt',   'explosion4', 80, 'default'),
]

import spineanim, json as _json

frames_meta = {}
for name, skel, atlas, anim, on_screen, skin in CHARS:
    dur = spineanim.duration(_json.load(open(skel, encoding='utf-8')), anim) or 1.0
    frames = max(2, round(dur * SPINE_FPS))
    cw = max(8, round(on_screen * OVERSAMPLE))
    im, w, h = spinestrip.strip(skel, atlas, anim, frames, cw, skin)
    put(im, name + '.png', 48)
    frames_meta[name] = (w, h, frames, round(frames / dur, 2))
    print('%-14s %2d frames  cell %3dx%-3d  %5.1f fps  (draws at %dpx)'
          % (name, frames, w, h, frames / dur, on_screen))

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

# ---- bullet hit spark ----------------------------------------------------
# Unity: PlayerBulletSplash.prefab - a SpriteRenderer driven by Splash.anim, 4 frames
# of the arsenal atlas at 30fps, spawned rotated to the bullet on every enemy hit
# (GameSharedData.RemovePlayerBullet). Each frame carries its own pivot, so the strip
# aligns every frame on its pivot instead of its box - otherwise the burst wanders.
HIT_W = 30  # on-screen width; the prefab draws unscaled, so this is the tuning knob

def unity_sprites(png, names):
    meta = open(png + '.meta', encoding='utf-8').read()
    found = {}
    for blk in meta.split('- serializedVersion:'):
        m = re.search(r'name: (\S+)', blk)
        if not m or m.group(1) not in names: continue
        r = re.search(r'rect:\s*\n\s*serializedVersion: \d+\s*\n\s*x: ([\d.]+)\s*\n'
                      r'\s*y: ([\d.]+)\s*\n\s*width: ([\d.]+)\s*\n\s*height: ([\d.]+)', blk)
        pv = re.search(r'pivot: \{x: ([-\d.]+), y: ([-\d.]+)\}', blk)
        found[m.group(1)] = tuple(float(v) for v in r.groups() + pv.groups())
    return [found[n] for n in names]

hit_src = U + A + 'arsenal.png'
hit_sheet = Image.open(hit_src).convert('RGBA')
cells = []
for x, y, w, h, pvx, pvy in unity_sprites(hit_src, ['bullethit_0000%d' % i for i in (1, 2, 3, 4)]):
    crop = hit_sheet.crop((int(x), int(hit_sheet.height - y - h), int(x + w), int(hit_sheet.height - y)))
    cells.append((crop, pvx * w, (1 - pvy) * h))  # pivot in top-left pixel coords
left = max(px for _, px, _ in cells);  right = max(c.width - px for c, px, _ in cells)
top = max(py for _, _, py in cells);   bot = max(c.height - py for c, _, py in cells)
cw, ch = round(left + right), round(top + bot)
strip = Image.new('RGBA', (cw * len(cells), ch))
for i, (c, px, py) in enumerate(cells):
    strip.alpha_composite(c, (i * cw + round(left - px), round(top - py)))
k = HIT_W / cw
strip = strip.resize((HIT_W * len(cells), max(1, round(ch * k))), Image.LANCZOS)
put(strip, 'hit.png', 48)
frames_meta['hit'] = (HIT_W, strip.height, len(cells), 30.0)


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
    flat(rel, 'i_%s.png' % name, 60, 48)

# ---- hud + background ---------------------------------------------------
for name, rel in [('hud_time', '/Survival/Time_Icon.png'), ('hud_kills', '/Survival/Kills_Icon.png'),
                  ('hud_wave', '/Survival/Wave_Icon.png')]:
    flat(rel, name + '.png', 40, 48)

BGP = U + '/BG/BGDataNew/BGAssets/BGDay/SpriteSheet/BG_Day_SpriteSheet.png'
put(tp(BGP, 1912, 1059, 508, 25, 56).resize((8, 512), Image.LANCZOS), 'sky.png', 0)
flat('/BG/BGDataOld/OtheBackgrounds/BG- Misc/clouds1.png', 'clouds1.png', 560, 32)
flat('/BG/BGDataOld/OtheBackgrounds/BG- Misc/clouds3.png', 'clouds2.png', 560, 32)
put(Image.open(U + '/iTunesArtwork@2x.png').convert('RGBA').resize((140, 140), Image.LANCZOS), 'appicon.png', 96)

for stale in ('coin.png', 'magnet.png', 'chest.png'):
    p = os.path.join(OUT, stale)
    if os.path.exists(p): os.remove(p)

def write_sheet_table(meta):
    """Rewrite the SHEETS literal in src/data.ts so the frame metadata can never
    drift from the PNGs it describes (it silently has, twice)."""
    ts = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'data.ts')
    ts = os.path.normpath(ts)
    src = open(ts, encoding='utf-8').read()
    start = src.index('export const SHEETS: Record<string, Sheet> = {')
    end = src.index('};', start) + 2
    var = {'player': 'player', 'hit': 'hit', 'boom': 'boom'}
    rows = []
    for name, (w, h, frames, fps) in meta.items():
        ident = var.get(name) or 'e' + ''.join(p.capitalize() for p in name[2:].split('_'))
        rows.append("  %s: { url: %s, frameWidth: %d, frameHeight: %d, frames: %d, fps: %s }"
                    % (name, ident, w, h, frames, round(fps, 2)))
    block = ('export const SHEETS: Record<string, Sheet> = {\n'
             + ',\n'.join(rows) + '\n};')
    open(ts, 'w', encoding='utf-8').write(src[:start] + block + src[end:])
    print('wrote SHEETS ->', ts)

write_sheet_table(frames_meta)

for k in sorted(sizes): print('%8d  %s' % (sizes[k], k))
print('TOTAL %.2f MB' % (sum(sizes.values()) / 1048576))
