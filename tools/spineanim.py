"""Sample a Spine 3.x animation at time t and bake the pose into the skeleton dict.

Supports what these skeletons actually use: bone rotate/translate/scale, slot
attachment swaps, and mesh deform. Curves are linear, stepped, or cubic bezier.
"""
import math


def _bezier(curve, p):
    """Spine stores a cubic bezier as [cx1, cy1, cx2, cy2] over the unit square."""
    cx1, cy1, cx2, cy2 = curve
    # solve x(s) == p for s, then return y(s)
    lo, hi = 0.0, 1.0
    for _ in range(18):
        s = (lo + hi) / 2
        x = 3 * cx1 * s * (1 - s) ** 2 + 3 * cx2 * s * s * (1 - s) + s ** 3
        if x < p:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2
    return 3 * cy1 * s * (1 - s) ** 2 + 3 * cy2 * s * s * (1 - s) + s ** 3


def _alpha(key, t, t0, t1):
    """Blend factor between two keys, honouring the first key's curve."""
    if t1 <= t0:
        return 0.0
    p = (t - t0) / (t1 - t0)
    curve = key.get('curve')
    if curve is None:
        return p
    if curve == 'stepped':
        return 0.0
    if isinstance(curve, list) and len(curve) == 4:
        return _bezier(curve, p)
    if isinstance(curve, (int, float)):  # "curve": c1 with c2/c3/c4 siblings
        return _bezier([curve, key.get('c2', 0), key.get('c3', 1), key.get('c4', 1)], p)
    return p


def _sample(keys, t, fields, defaults):
    """Interpolate a keyframe list at time t. fields/defaults are parallel tuples."""
    if not keys:
        return defaults
    if t <= keys[0].get('time', 0):
        k = keys[0]
        return tuple(k.get(f, d) for f, d in zip(fields, defaults))
    if t >= keys[-1].get('time', 0):
        k = keys[-1]
        return tuple(k.get(f, d) for f, d in zip(fields, defaults))
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        ta, tb = a.get('time', 0), b.get('time', 0)
        if ta <= t <= tb:
            u = _alpha(a, t, ta, tb)
            out = []
            for f, d in zip(fields, defaults):
                va, vb = a.get(f, d), b.get(f, d)
                out.append(va + (vb - va) * u)
            return tuple(out)
    return defaults


def _sample_attachment(keys, t):
    name = None
    for k in keys:
        if k.get('time', 0) <= t:
            name = k.get('name')
        else:
            break
    return name


def _sample_deform(keys, t):
    """Returns (offset, vertices) of interpolated deform offsets, or None."""
    if not keys:
        return None

    def pair(k):
        return k.get('offset', 0), k.get('vertices', [])

    if t <= keys[0].get('time', 0):
        return pair(keys[0])
    if t >= keys[-1].get('time', 0):
        return pair(keys[-1])
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        ta, tb = a.get('time', 0), b.get('time', 0)
        if ta <= t <= tb:
            u = _alpha(a, t, ta, tb)
            oa, va = pair(a)
            ob, vb = pair(b)
            lo = min(oa, ob)
            hi = max(oa + len(va), ob + len(vb))
            out = []
            for idx in range(lo, hi):
                x = va[idx - oa] if oa <= idx < oa + len(va) else 0.0
                y = vb[idx - ob] if ob <= idx < ob + len(vb) else 0.0
                out.append(x + (y - x) * u)
            return lo, out
    return pair(keys[-1])


def pose(sk, anim, t):
    """Mutate `sk` (a parsed skeleton dict) into the pose of `anim` at time `t`.

    Returns (attachment_overrides, deform_overrides) for the caller to apply.
    """
    a = sk.get('animations', {}).get(anim)
    if not a:
        return {}, {}

    by = {b['name']: b for b in sk['bones']}
    for bname, tl in a.get('bones', {}).items():
        b = by.get(bname)
        if b is None:
            continue
        if 'rotate' in tl:
            keys = tl['rotate']
            field = 'angle' if 'angle' in keys[0] else 'value'
            (ang,) = _sample(keys, t, (field,), (0.0,))
            b['rotation'] = b.get('rotation', 0.0) + ang
        if 'translate' in tl:
            dx, dy = _sample(tl['translate'], t, ('x', 'y'), (0.0, 0.0))
            b['x'] = b.get('x', 0.0) + dx
            b['y'] = b.get('y', 0.0) + dy
        if 'scale' in tl:
            sx, sy = _sample(tl['scale'], t, ('x', 'y'), (1.0, 1.0))
            b['scaleX'] = b.get('scaleX', 1.0) * sx
            b['scaleY'] = b.get('scaleY', 1.0) * sy

    attachments = {}
    for sname, tl in a.get('slots', {}).items():
        if 'attachment' in tl:
            attachments[sname] = _sample_attachment(tl['attachment'], t)

    deforms = {}
    for skin, slots in a.get('deform', {}).items():
        for slot, atts in slots.items():
            for att, keys in atts.items():
                d = _sample_deform(keys, t)
                if d:
                    deforms[(slot, att)] = d
    return attachments, deforms


def duration(sk, anim):
    a = sk.get('animations', {}).get(anim)
    if not a:
        return 0.0
    end = 0.0
    for grp in ('bones', 'slots'):
        for _, tls in a.get(grp, {}).items():
            for _, keys in tls.items():
                if isinstance(keys, list) and keys:
                    end = max(end, keys[-1].get('time', 0))
    for _, slots in a.get('deform', {}).items():
        for _, atts in slots.items():
            for _, keys in atts.items():
                if keys:
                    end = max(end, keys[-1].get('time', 0))
    return end
