"""Bake a Spine animation into a horizontal sprite strip (one row of equal cells)."""
import copy, json, math, os, sys
from PIL import Image, ImageChops, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas import parse as parse_atlas
import spineanim


def _bone_world(bones):
    by = {b['name']: b for b in bones}
    out = {}
    def solve(b):
        n = b['name']
        if n in out: return out[n]
        x, y = b.get('x', 0.0), b.get('y', 0.0)
        rot = math.radians(b.get('rotation', 0.0))
        sx, sy = b.get('scaleX', 1.0), b.get('scaleY', 1.0)
        shx, shy = math.radians(b.get('shearX', 0.0)), math.radians(b.get('shearY', 0.0))
        la, lb = math.cos(rot + shx) * sx, math.cos(rot + math.pi / 2 + shy) * sy
        lc, ld = math.sin(rot + shx) * sx, math.sin(rot + math.pi / 2 + shy) * sy
        p = b.get('parent')
        if p is None:
            return out.setdefault(n, (la, lb, lc, ld, x, y))
        pa, pb, pc, pd, px, py = solve(by[p])
        return out.setdefault(n, (pa*la + pb*lc, pa*lb + pb*ld, pc*la + pd*lc, pc*lb + pd*ld,
                                  pa*x + pb*y + px, pc*x + pd*y + py))
    for b in bones: solve(b)
    return out


def _mesh_points(entry, bones_order, world, slot_bone, deform):
    verts = list(entry['vertices'])
    n_uv = len(entry['uvs']) // 2
    weighted = len(verts) != n_uv * 2
    if deform:
        offset, delta = deform
        if not weighted:
            for i, d in enumerate(delta):
                j = offset + i
                if j < len(verts): verts[j] += d
    pts = []
    if not weighted:
        a, b, c, d, tx, ty = world[slot_bone]
        for i in range(n_uv):
            x, y = verts[2*i], verts[2*i+1]
            pts.append((a*x + b*y + tx, c*x + d*y + ty))
    else:
        # weighted meshes: deform offsets apply to the per-bone bind positions in order
        di = 0
        delta = deform[1] if deform else None
        doff = deform[0] if deform else 0
        i = 0
        for _ in range(n_uv):
            cnt = int(verts[i]); i += 1
            wx = wy = 0.0
            for _ in range(cnt):
                bi, bx, by, w = int(verts[i]), verts[i+1], verts[i+2], verts[i+3]; i += 4
                if delta is not None:
                    if doff <= di < doff + len(delta): bx += delta[di - doff]
                    if doff <= di + 1 < doff + len(delta): by += delta[di + 1 - doff]
                di += 2
                a, b, c, d, tx, ty = world[bones_order[bi]]
                wx += (a*bx + b*by + tx) * w
                wy += (c*bx + d*by + ty) * w
            pts.append((wx, wy))
    return pts


def _collect(sk, pages, imgs, skin, attachments, deforms):
    world = _bone_world(sk['bones'])
    bones_order = [b['name'] for b in sk['bones']]
    skins = sk['skins']
    skinmap = skins if isinstance(skins, dict) else {s['name']: s.get('attachments', {}) for s in skins}

    def region(name):
        for p, regs in pages.items():
            if name in regs:
                x, y, w, h, rot = regs[name]
                im = imgs[p]
                if rot == 'false':
                    return im.crop((x, y, x + w, y + h))
                return im.crop((x, y, x + h, y + w)).rotate(-90, expand=True)
        return None

    draws = []
    for slot in sk['slots']:
        name = slot['name']
        att_name = attachments[name] if name in attachments else slot.get('attachment')
        if not att_name: continue
        entry = skinmap.get(skin, {}).get(name, {}).get(att_name)
        if entry is None:
            entry = skinmap.get('default', {}).get(name, {}).get(att_name)
        if entry is None: continue
        img = region(entry.get('path') or entry.get('name') or att_name)
        if img is None: continue
        kind = entry.get('type', 'region')
        if kind == 'region':
            w = entry.get('width', img.width); h = entry.get('height', img.height)
            if (int(w), int(h)) != img.size:
                img = img.resize((max(1, int(w)), max(1, int(h))), Image.LANCZOS)
            ax, ay = entry.get('x', 0.0), entry.get('y', 0.0)
            ar = math.radians(entry.get('rotation', 0.0))
            asx, asy = entry.get('scaleX', 1.0), entry.get('scaleY', 1.0)
            ba, bb, bc, bd, bx, by = world[slot['bone']]
            la, lb = math.cos(ar)*asx, -math.sin(ar)*asy
            lc, ld = math.sin(ar)*asx,  math.cos(ar)*asy
            draws.append(('region', img, (ba*la + bb*lc, ba*lb + bb*ld, bc*la + bd*lc, bc*lb + bd*ld,
                                          ba*ax + bb*ay + bx, bc*ax + bd*ay + by)))
        elif kind == 'mesh':
            pts = _mesh_points(entry, bones_order, world, slot['bone'], deforms.get((name, att_name)))
            uvs = entry['uvs']
            uv_px = [(uvs[2*i] * img.width, uvs[2*i+1] * img.height) for i in range(len(pts))]
            draws.append(('mesh', img, (pts, uv_px, entry['triangles'])))
    return draws


def _bounds(draws):
    pts = []
    for kind, img, payload in draws:
        if kind == 'region':
            a, b, c, d, tx, ty = payload
            hw, hh = img.width/2.0, img.height/2.0
            pts += [(a*cx + b*cy + tx, c*cx + d*cy + ty)
                    for cx, cy in ((-hw,-hh),(hw,-hh),(hw,hh),(-hw,hh))]
        else:
            pts += payload[0]
    return pts


def _paint(draws, minx, maxy, W, H, scale):
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    to_px = lambda p: ((p[0]-minx)*scale, (maxy-p[1])*scale)
    for kind, img, payload in draws:
        if kind == 'region':
            a, b, c, d, tx, ty = payload
            hw, hh = img.width/2.0, img.height/2.0
            A, B = scale*a, -scale*b
            C, D = -scale*c, scale*d
            E = scale*(-a*hw + b*hh + tx - minx)
            F = scale*(maxy - (-c*hw + d*hh + ty))
            det = A*D - B*C
            if abs(det) < 1e-9: continue
            ia, ib, ic, id_ = D/det, -B/det, -C/det, A/det
            canvas.alpha_composite(img.transform((W, H), Image.AFFINE,
                (ia, ib, -(ia*E + ib*F), ic, id_, -(ic*E + id_*F)), resample=Image.BICUBIC))
        else:
            wpts, uv_px, tris = payload
            dst = [to_px(p) for p in wpts]
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            for t in range(0, len(tris), 3):
                i0, i1, i2 = tris[t], tris[t+1], tris[t+2]
                (x0,y0),(x1,y1),(x2,y2) = dst[i0], dst[i1], dst[i2]
                (u0,v0),(u1,v1),(u2,v2) = uv_px[i0], uv_px[i1], uv_px[i2]
                det = (x1-x0)*(y2-y0) - (x2-x0)*(y1-y0)
                if abs(det) < 1e-9: continue
                m11 = ((u1-u0)*(y2-y0) - (u2-u0)*(y1-y0)) / det
                m12 = ((x1-x0)*(u2-u0) - (x2-x0)*(u1-u0)) / det
                m21 = ((v1-v0)*(y2-y0) - (v2-v0)*(y1-y0)) / det
                m22 = ((x1-x0)*(v2-v0) - (x2-x0)*(v1-v0)) / det
                m13 = u0 - m11*x0 - m12*y0
                m23 = v0 - m21*x0 - m22*y0
                bx0 = max(0, int(min(x0,x1,x2)) - 1); bx1 = min(W, int(max(x0,x1,x2)) + 2)
                by0 = max(0, int(min(y0,y1,y2)) - 1); by1 = min(H, int(max(y0,y1,y2)) + 2)
                if bx1 <= bx0 or by1 <= by0: continue
                bw, bh = bx1-bx0, by1-by0
                warped = img.transform((bw, bh), Image.AFFINE,
                    (m11, m12, m13 + m11*bx0 + m12*by0, m21, m22, m23 + m21*bx0 + m22*by0),
                    resample=Image.BICUBIC)
                mask = Image.new('L', (bw, bh), 0)
                ImageDraw.Draw(mask).polygon([(x0-bx0,y0-by0),(x1-bx0,y1-by0),(x2-bx0,y2-by0)], fill=255)
                warped.putalpha(ImageChops.multiply(warped.getchannel('A'), mask))
                layer.alpha_composite(warped, (bx0, by0))
            canvas.alpha_composite(layer)
    return canvas


def strip(skel_json, atlas_path, anim, frames, cell_w, skin='default', pad=4, loop=True):
    """Render `frames` evenly-spaced poses of `anim` into one horizontal strip.

    All frames share one bounding box so the sprite never jitters between cells.
    Returns (PIL.Image strip, cell_w, cell_h).
    """
    base_sk = json.load(open(skel_json, encoding='utf-8'))
    base = os.path.dirname(atlas_path)
    pages = parse_atlas(atlas_path)
    imgs = {p: Image.open(os.path.join(base, p)).convert('RGBA') for p in pages}
    dur = spineanim.duration(base_sk, anim) or 1.0
    # a looping cycle ends where it began, so the last sample sits one step short
    times = [dur * i / frames for i in range(frames)] if loop else [dur * i / max(1, frames - 1) for i in range(frames)]

    posed = []
    for t in times:
        sk = copy.deepcopy(base_sk)
        atts, defs = spineanim.pose(sk, anim, t)
        posed.append(_collect(sk, pages, imgs, skin, atts, defs))

    pts = [p for d in posed for p in _bounds(d)]
    minx, maxx = min(x for x, _ in pts) - pad, max(x for x, _ in pts) + pad
    miny, maxy = min(y for _, y in pts) - pad, max(y for _, y in pts) + pad
    scale = cell_w / (maxx - minx)
    W = cell_w
    H = max(1, int(round((maxy - miny) * scale)))

    out = Image.new('RGBA', (W * frames, H), (0, 0, 0, 0))
    for i, draws in enumerate(posed):
        out.alpha_composite(_paint(draws, minx, maxy, W, H, scale), (i * W, 0))
    return out, W, H
