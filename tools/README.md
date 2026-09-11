# Asset pipeline

Regenerates everything in `../assets/` straight out of the Unity project. Run it
whenever the source art changes:

```bash
cd /path/to/Explottens-FtP/ExplottensUnityProject/Assets
python3 /path/to/playable-explottens-survivor/tools/build_assets.py
```

Needs Python 3 + Pillow. Paths to the Unity project and to `assets/` are constants
at the top of `build_assets.py`.

- `atlas.py` — parses libgdx/Spine `.atlas.txt` sheets (v3 and v4 layouts).
- `spineanim.py` — samples a Spine animation at time `t`: bone rotate/translate/scale
  with linear, stepped and cubic-bezier curves, slot attachment swaps, mesh deform.
- `spinestrip.py` — renders a posed skeleton (region quads + mesh triangles, weighted
  meshes included) and bakes N frames into one horizontal strip on a shared bounding box.
- `build_assets.py` — the manifest: which skeleton, which animation, how many frames,
  what cell width, plus the flat sprites (gems, projectiles, icons, HUD, background).

Frame counts and cell sizes live in the `CHARS` table. If you change a cell size,
update the matching entry in `src/data.ts` → `SHEETS`.
