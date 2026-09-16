"""Trim the Unity player Spine skeleton down to what the playable actually renders.

The shipped skeleton carries seven planes and every weapon/death animation - 3.2MB of
JSON against a 2.2MB, 2048x1024 atlas page. The ad flies plane 1 only, so this keeps
the `default` + `playerPlane1` skins and the handful of animations GameScene plays,
then repacks just the regions those skins reference into one small page.

Format: the Unity skeleton is a Spine 3.7 export, and Phaser ships the 3.8 runtime.
The only breaking JSON change between them that this skeleton hits is `skins`, which
went from a name->slots map to a list of {name, attachments} records, so it is
converted on the way out (see `to_38`).

Scaling: every atlas number (xy/size/orig/offset) is multiplied by SCALE alongside the
image itself. spine-ts derives quad geometry from size/originalWidth ratios, so scaling
both leaves the rendered geometry pixel-identical and only the texture resolution drops
- which is why the skeleton JSON needs no scale fixup.

Usage:  python3 tools/build_spine.py            (needs Python 3 + Pillow)
        python3 tools/build_spine.py --preview  also writes assets/../spine_preview.png,
                                                rendered from the generated files - the
                                                only eyeball check on the repack.
"""
import copy, json, os, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spineanim, spinestrip

U = '/Users/zeeshan/Desktop/work/Explottens-FtP/ExplottensUnityProject/Assets'
PL = U + '/SpineObjects/Player/UpdatedPlayer/'
LI = U + '/Scripts/Skills/Actives/WeaponScripts/Lightning/'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')

PAD = 2          # transparent gutter, stops bilinear filtering bleeding neighbours
COLORS = 64      # palette size for the packed page

# Every skeleton the game runs live. `centre` names the animation whose art bbox is put
# on the origin (the plane rotates about its own position); a skeleton the game places
# by its own origin - Lightning.cs drops the bolt on the target's transform - leaves it
# None. Shockwave Strike is the one effect the baker cannot stand in for: its slot-colour
# fade and 0.83s of jitter live in the skeleton, and a strip of it is either 25 cells of
# a 4360-unit-tall bolt or a visibly cheaper flash.
TARGETS = [
    dict(name='spine_player', skel=PL + 'player.json', atlas=PL + 'player.atlas.txt',
         skins=('default', 'playerPlane1'),
         # flying/idle/flip are what the ad plays; MultiCanon poses the starting weapon's gun
         anims=('flying1', 'idle1', 'flip1', 'dash1', 'MultiCanon'),
         scale=0.5,           # atlas resolution vs. authored size; geometry is unaffected
         centre='flying1', on_screen_w=67),
    dict(name='spine_bolt', skel=LI + 'LightningAttack.json', atlas=LI + 'LightningAttack.atlas.txt',
         skins=('default',), anims=('attack3',), scale=0.36,
         # twelve full-height bolt frames live in this skin and attack3 cycles five
         trim=True, centre=None, on_screen_w=None),
]



def parse_atlas(path):
    """libgdx/Spine v3 atlas -> (page_name, {region: props}). Keeps every property."""
    lines = open(path, encoding='utf-8').read().splitlines()
    page, regions, i = None, {}, 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if not ln.startswith((' ', '\t')) and ln.strip().endswith('.png'):
            page = ln.strip()
            i += 1
            while i < len(lines) and ':' in lines[i] and not lines[i].startswith((' ', '\t')):
                i += 1
            continue
        name, i = ln.strip(), i + 1
        props = {}
        while i < len(lines) and lines[i].startswith((' ', '\t')) and ':' in lines[i]:
            k, v = lines[i].split(':', 1)
            props[k.strip()] = v.strip()
            i += 1
        regions[name] = props
    return page, regions


def centre_root(skel, atlas_path, anim, skin):
    """Shift the root bone so the flying pose's art bbox sits on the skeleton origin.

    The authored root sits off to one side, which would make the plane orbit its own
    position once GameScene rotates it. Baking the offset in here keeps the runtime
    free of a wrapper container.
    """
    pages = spinestrip.parse_atlas(atlas_path)
    base = os.path.dirname(atlas_path)
    imgs = {p: Image.open(os.path.join(base, p)).convert('RGBA') for p in pages}
    dur = spineanim.duration(skel, anim) or 1.0
    pts = []
    for i in range(12):
        sk = copy.deepcopy(skel)
        atts, defs = spineanim.pose(sk, anim, dur * i / 12)
        pts += spinestrip._bounds(spinestrip._collect(sk, pages, imgs, skin, atts, defs))
    cx = (min(x for x, _ in pts) + max(x for x, _ in pts)) / 2
    cy = (min(y for _, y in pts) + max(y for _, y in pts)) / 2
    width = max(x for x, _ in pts) - min(x for x, _ in pts)
    root = skel['bones'][0]
    root['x'] = root.get('x', 0) - cx
    root['y'] = root.get('y', 0) - cy
    return width


def drop_dead_deforms(skel, skins):
    """Deform timelines are keyed by skin; the dropped planes' keys would fail to resolve."""
    for anim in skel['animations'].values():
        if 'deform' in anim:
            anim['deform'] = {k: v for k, v in anim['deform'].items() if k in skins}
            if not anim['deform']:
                del anim['deform']


def to_38(skel):
    """Spine 3.7 JSON -> 3.8.

    Two changes bite this skeleton:
      * `skins` went from a name->slots map to a list of {name, attachments}.
      * an attachment's atlas region moved from `name` to `path`. The 3.8 loader reads
        `path` and otherwise falls back to the attachment's own key, so leaving this
        alone does not error - the plane just silently draws the wrong region, or none.
    """
    for slots in skel['skins'].values():
        for atts in slots.values():
            for att in atts.values():
                if 'name' in att and 'path' not in att:
                    att['path'] = att.pop('name')
    skel['skins'] = [{'name': name, 'attachments': slots} for name, slots in skel['skins'].items()]
    skel['skeleton']['spine'] = '3.8.95'
    return skel


def used_regions(skel):
    """Every atlas region the kept skins can attach, under its atlas name."""
    names = set()
    for skin in skel['skins']:
        for atts in skin['attachments'].values():
            for att_name, att in atts.items():
                names.add(att.get('path') or att.get('name') or att_name)
    return names


def preview(skel37, out_path):
    """Render the generated atlas through the repo's own Spine renderer.

    spinestrip reads the 3.7 shape, so it is handed the skeleton as it stands before
    `to_38` - same bones, same centred root, and crucially the *new* atlas, so a bad
    repack or a bad scale shows up immediately.
    """
    tmp = os.path.join(OUT, '.spine_preview_skel.json')
    json.dump(skel37, open(tmp, 'w'))
    try:
        rows = [spinestrip.strip(tmp, os.path.join(OUT, 'spine_player.atlas'), a, n, 80, 'playerPlane1')[0]
                for a, n in (('flying1', 8), ('flip1', 5))]
    finally:
        os.remove(tmp)
    sheet = Image.new('RGBA', (max(r.width for r in rows), sum(r.height for r in rows)), (90, 150, 200, 255))
    y = 0
    for r in rows:
        sheet.alpha_composite(r, (0, y))
        y += r.height
    sheet.save(out_path)
    print('preview -> %s' % out_path)


def drop_unused_attachments(skel, anims):
    """Keep only what the kept animations can actually put on a slot, plus the setup pose.

    Opt-in per target (`trim`): it is safe where a slot is only ever dressed by an
    attachment timeline, and wrong for the player, whose skins dress most slots through
    the setup pose of a skin the game switches to.
    """
    keep = {s['name']: {s.get('attachment')} for s in skel['slots']}
    for name in anims:
        for slot, timelines in skel['animations'][name].get('slots', {}).items():
            for key in timelines.get('attachment', []):
                keep.setdefault(slot, set()).add(key.get('name'))
    for slots in skel['skins'].values():
        for slot, atts in list(slots.items()):
            slots[slot] = {k: v for k, v in atts.items() if k in keep.get(slot, set())}


def build(t):
    """Repack one skeleton into assets/<name>.{json,atlas,png}."""
    scale, skins, anims = t['scale'], t['skins'], t['anims']
    skel = json.load(open(t['skel'], encoding='utf-8'))
    skel['animations'] = {k: v for k, v in skel['animations'].items() if k in anims}
    skel['skins'] = {k: v for k, v in skel['skins'].items() if k in skins}
    if t.get('trim'):
        drop_unused_attachments(skel, anims)

    width = centre_root(skel, t['atlas'], t['centre'], skins[-1]) if t['centre'] else 0
    drop_dead_deforms(skel, skins)
    skel37 = copy.deepcopy(skel)
    to_38(skel)

    page, regions = parse_atlas(t['atlas'])
    src = Image.open(os.path.join(os.path.dirname(t['atlas']), page)).convert('RGBA')

    wanted = used_regions(skel)
    missing = wanted - set(regions)
    if missing:
        raise SystemExit('atlas is missing regions the skins reference: %s' % sorted(missing))

    # Un-rotate while cutting so every repacked region is rotate:false.
    cuts = []
    for name in sorted(wanted):
        p = regions[name]
        x, y = [int(v) for v in p['xy'].split(',')]
        w, h = [int(v) for v in p['size'].split(',')]
        rot = p.get('rotate', 'false') == 'true'
        im = src.crop((x, y, x + h, y + w)).rotate(-90, expand=True) if rot else src.crop((x, y, x + w, y + h))
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        cuts.append((name, im.resize((sw, sh), Image.LANCZOS), p))

    # Shelf pack, tallest first, into the narrowest power-of-two page that holds them.
    cuts.sort(key=lambda c: -c[1].height)
    area = sum((c[1].width + PAD) * (c[1].height + PAD) for c in cuts)
    for pw in (256, 512, 1024, 2048, 4096):
        if pw < max(c[1].width for c in cuts) + PAD:
            continue
        placed, x, y, shelf = [], PAD, PAD, 0
        for name, im, p in cuts:
            if x + im.width + PAD > pw:
                x, y, shelf = PAD, y + shelf + PAD, 0
            placed.append((name, im, p, x, y))
            x += im.width + PAD
            shelf = max(shelf, im.height)
        ph = y + shelf + PAD
        if pw * ph >= area and ph <= pw * 2:
            break

    sheet = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    for _, im, _, x, y in placed:
        sheet.paste(im, (x, y))

    out_png = t['name'] + '.png'
    lines = ['', out_png, 'size: %d,%d' % (pw, ph), 'format: RGBA8888',
             'filter: Linear,Linear', 'repeat: none']
    for name, im, p, x, y in placed:
        ow, oh = [int(v) for v in p['orig'].split(',')]
        ox, oy = [int(v) for v in p['offset'].split(',')]
        lines += [
            name,
            '  rotate: false',
            '  xy: %d, %d' % (x, y),
            '  size: %d, %d' % (im.width, im.height),
            '  orig: %d, %d' % (round(ow * scale), round(oh * scale)),
            '  offset: %d, %d' % (round(ox * scale), round(oy * scale)),
            '  index: %s' % p.get('index', '-1')
        ]

    sheet.quantize(colors=COLORS, method=Image.FASTOCTREE, dither=Image.NONE) \
        .convert('RGBA').save(os.path.join(OUT, out_png), optimize=True)
    open(os.path.join(OUT, t['name'] + '.atlas'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    # ASCII only: GameScene hands this to btoa, which cannot encode code points > 255.
    skeleton = json.dumps(skel, separators=(',', ':'))
    assert skeleton.isascii(), 'skeleton JSON must stay ASCII for btoa'
    open(os.path.join(OUT, t['name'] + '.json'), 'w', encoding='utf-8').write(skeleton)

    for f in (out_png, t['name'] + '.atlas', t['name'] + '.json'):
        print('%-22s %6.1f KB' % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))
    print('page %dx%d, %d regions, %d animations' % (pw, ph, len(placed), len(skel['animations'])))
    if t['centre']:
        print('%s spans %.1f skeleton units -> SPINE.scale %.4f draws it %dpx wide'
              % (t['centre'], width, t['on_screen_w'] / width, t['on_screen_w']))
    return skel37


def main():
    for t in TARGETS:
        skel37 = build(t)
        if t['name'] == 'spine_player' and '--preview' in sys.argv:
            preview(skel37, os.path.join(os.path.dirname(OUT), 'spine_preview.png'))


if __name__ == '__main__':
    main()
