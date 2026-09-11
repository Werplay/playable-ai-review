import re, os, sys
from PIL import Image

def parse(path):
    """Parse libgdx/spine atlas (v3 or v4 format). Returns {page_png: {name: region}}"""
    lines = open(path, encoding='utf-8').read().splitlines()
    pages, i = {}, 0
    cur = None
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        if not ln.startswith((' ', '\t')) and (ln.strip().endswith('.png') or ln.strip().endswith('.jpg')):
            cur = ln.strip(); pages[cur] = {}
            i += 1
            while i < len(lines) and ':' in lines[i] and not lines[i].startswith((' ','\t')):
                i += 1
            continue
        # region name
        name = ln.strip()
        i += 1
        props = {}
        while i < len(lines) and lines[i].startswith((' ', '\t')) and ':' in lines[i]:
            k, v = lines[i].split(':', 1)
            props[k.strip()] = v.strip()
            i += 1
        if 'xy' in props:  # v3
            x, y = [int(t) for t in props['xy'].split(',')]
            w, h = [int(t) for t in props['size'].split(',')]
        elif 'bounds' in props:  # v4
            x, y, w, h = [int(t) for t in props['bounds'].split(',')]
        else:
            continue
        rot = props.get('rotate', 'false')
        pages[cur][name] = (x, y, w, h, rot)
    return pages

def extract(atlas_path, names, outdir, prefix=''):
    base = os.path.dirname(atlas_path)
    os.makedirs(outdir, exist_ok=True)
    out = []
    for page, regions in parse(atlas_path).items():
        im = Image.open(os.path.join(base, page)).convert('RGBA')
        for n in (names or regions.keys()):
            if n not in regions: continue
            x, y, w, h, rot = regions[n]
            if rot == 'true':   # spine v4 rotates 90 CW packing
                crop = im.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
            elif rot not in ('false',):
                crop = im.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
            else:
                crop = im.crop((x, y, x + w, y + h))
            safe = prefix + re.sub(r'[^A-Za-z0-9_-]', '_', n)
            p = os.path.join(outdir, safe + '.png')
            crop.save(p)
            out.append((n, crop.size, p))
    return out

if __name__ == '__main__':
    for n, s, p in extract(sys.argv[1], sys.argv[3:] or None, sys.argv[2]):
        print(n, s, p)
