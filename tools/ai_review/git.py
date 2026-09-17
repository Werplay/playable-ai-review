from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .core import ChangedFile


def run_git(root: Path, *args: str, binary: bool = False, check: bool = True):
    result = subprocess.run(["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout if binary else result.stdout.decode("utf-8", "replace")


def merge_base(root: Path, ref: str) -> str:
    return run_git(root, "merge-base", ref, "HEAD").strip()


def _blob(root: Path, revision: str | None, path: str) -> str:
    if revision is None:
        target = root / path
        try: return target.read_text("utf-8")
        except (OSError, UnicodeDecodeError): return ""
    spec = f":{path}" if revision == ":" else f"{revision}:{path}"
    result = subprocess.run(["git", "show", spec], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode or b"\0" in result.stdout: return ""
    return result.stdout.decode("utf-8", "replace")


def _name_status(root: Path, args: list[str]) -> list[tuple[str, str, str | None]]:
    raw = run_git(root, *args, "--name-status", "-z", binary=True)
    fields = raw.split(b"\0"); result = []; i = 0
    while i < len(fields) and fields[i]:
        status = fields[i].decode(); i += 1
        if status.startswith(("R", "C")):
            old, new = fields[i].decode("utf-8", "surrogateescape"), fields[i+1].decode("utf-8", "surrogateescape"); i += 2
            result.append((status[0], new, old))
        else:
            path = fields[i].decode("utf-8", "surrogateescape"); i += 1
            result.append((status[0], path, None))
    return result


def collect(root: Path, base: str | None, staged: bool, range_spec: str | None) -> list[ChangedFile]:
    if staged:
        diff_args, before, after = ["diff", "--cached", "--find-renames"], "HEAD", ":"
    elif range_spec:
        if ".." not in range_spec: raise ValueError("--range must be A..B")
        before, after = range_spec.split("..", 1)
        diff_args = ["diff", "--find-renames", before, after]
    else:
        before = merge_base(root, base or "HEAD")
        after = None
        diff_args = ["diff", "--find-renames", before]
    statuses = _name_status(root, diff_args)
    patch_all = run_git(root, *diff_args, "--no-ext-diff", "--binary")
    patches: dict[str,str] = {}
    matches = list(re.finditer(r"(?m)^diff --git a/(.*?) b/(.*?)$", patch_all))
    for idx, match in enumerate(matches):
        path = match.group(2); patches[path] = patch_all[match.start():matches[idx+1].start() if idx+1 < len(matches) else len(patch_all)]
    files = []
    for status, path, old in statuses:
        patch = patches.get(path, "")
        # Only Git's patch control lines indicate binary content. The same words
        # may legitimately occur inside source code (including this collector).
        binary = bool(re.search(r"(?m)^(?:GIT binary patch|Binary files .+ differ)$", patch))
        generated = bool(re.search(r"(?i)(^|/)(dist|build|generated|vendor)/|\.min\.(js|css)$", path))
        base_path = old or path
        proposed_rev = after if (range_spec or staged) else None
        proposed = "" if status == "D" else _blob(root, proposed_rev, path)
        base_text = "" if status == "A" else _blob(root, before, base_path)
        files.append(ChangedFile(path,status,old,patch,base_text,proposed,binary,generated))
    return files


def file_map(root: Path) -> list[str]:
    raw = run_git(root, "ls-files", "-z", binary=True)
    return [x.decode("utf-8", "surrogateescape") for x in raw.split(b"\0") if x]
