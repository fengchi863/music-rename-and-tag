from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from opencc import OpenCC


@dataclass(frozen=True)
class RenameOp:
    src: Path
    dst: Path


def _convert_name(cc: OpenCC, name: str) -> str:
    return cc.convert(name)

_AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"}


_WIN_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def _sanitize_windows_name(name: str) -> str:
    # Windows forbids trailing dots/spaces and these characters: \ / : * ? " < > |
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.rstrip(" .")
    if not name:
        name = "_"

    base, dot, ext = name.partition(".")
    if base.upper() in _WIN_RESERVED_BASENAMES:
        base = f"_{base}_"
    return base + (dot + ext if dot else "")


def _unique_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _build_plan(root: Path, cc: OpenCC, sanitize_windows: bool) -> list[RenameOp]:
    ops: list[RenameOp] = []

    # Bottom-up so children are handled before their parents (important for directories).
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        cur = Path(dirpath)

        for fname in filenames:
            src = cur / fname
            new = _convert_name(cc, fname)
            if sanitize_windows:
                new = _sanitize_windows_name(new)
            if new != fname:
                dst = cur / new
                ops.append(RenameOp(src=src, dst=dst))

        for dname in dirnames:
            src = cur / dname
            new = _convert_name(cc, dname)
            if sanitize_windows:
                new = _sanitize_windows_name(new)
            if new != dname:
                dst = cur / new
                ops.append(RenameOp(src=src, dst=dst))

    return ops


def _apply_plan(ops: list[RenameOp], *, dry_run: bool) -> tuple[int, int]:
    changed = 0
    skipped = 0

    for op in ops:
        if not op.src.exists():
            skipped += 1
            continue

        dst = op.dst
        # If it already has the target name (e.g., due to earlier rename), skip.
        if op.src.resolve() == dst.resolve():
            skipped += 1
            continue

        # Avoid renaming across parents; this tool only changes basename.
        if op.src.parent != dst.parent:
            skipped += 1
            continue

        if dst.exists():
            dst = _unique_path(dst)

        if dry_run:
            print(f"[DRY] {op.src} -> {dst}")
            changed += 1
            continue

        try:
            op.src.rename(dst)
            print(f"[OK ] {op.src} -> {dst}")
            changed += 1
        except PermissionError as e:
            print(f"[SKIP] PermissionError: {op.src} ({e})", file=sys.stderr)
            skipped += 1
        except OSError as e:
            print(f"[SKIP] OSError: {op.src} ({e})", file=sys.stderr)
            skipped += 1

    return changed, skipped


def _iter_audio_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        cur = Path(dirpath)
        for fname in filenames:
            p = cur / fname
            if p.suffix.lower() in _AUDIO_EXTS:
                files.append(p)
    return files


def _to_str_list(value: object) -> list[str] | None:
    # Mutagen may return: str, list[str], tuple[str], MP4FreeForm bytes, etc.
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)) and all(isinstance(x, str) for x in value):
        return list(value)
    return None


def _update_audio_tags_one(path: Path, cc: OpenCC, *, dry_run: bool) -> tuple[bool, int]:
    """
    Returns (changed, fields_changed_count)
    """
    try:
        from mutagen import File as MutagenFile
    except Exception as e:  # pragma: no cover
        print(f"[SKIP] mutagen import failed: {e}", file=sys.stderr)
        return False, 0

    try:
        audio = MutagenFile(path)
    except Exception as e:
        print(f"[SKIP] Cannot read tags: {path} ({e})", file=sys.stderr)
        return False, 0

    if audio is None or audio.tags is None:
        return False, 0

    tags = audio.tags
    fields_changed = 0
    any_changed = False

    # Convert all string-ish tag values we can safely rewrite.
    # This covers common fields like Title/Artist/Album as well as custom text fields.
    for key in list(tags.keys()):
        try:
            old_val = tags.get(key)
            str_list = _to_str_list(old_val)
            if str_list is None:
                continue

            new_list = [cc.convert(v) for v in str_list]
            if new_list != str_list:
                fields_changed += 1
                any_changed = True
                if dry_run:
                    print(f"[DRY-TAG] {path}  {key}: {str_list} -> {new_list}")
                else:
                    # Preserve the original container type where possible.
                    tags[key] = new_list
        except Exception as e:
            print(f"[SKIP] Tag update failed: {path} key={key} ({e})", file=sys.stderr)
            continue

    if not any_changed:
        return False, 0

    if dry_run:
        return True, fields_changed

    try:
        audio.save()
        print(f"[OK-TAG] {path} fields_changed={fields_changed}")
        return True, fields_changed
    except Exception as e:
        print(f"[SKIP] Cannot save tags: {path} ({e})", file=sys.stderr)
        return False, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recursively rename files/folders from Traditional Chinese to Simplified Chinese.",
    )
    parser.add_argument("root", type=Path, help="Root directory to process")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without renaming",
    )
    parser.add_argument(
        "--no-sanitize-windows",
        action="store_true",
        help="Do not sanitize Windows-invalid filename characters (not recommended on Windows)",
    )
    parser.add_argument(
        "--update-tags",
        action="store_true",
        help="Also convert audio file metadata tags (Title/Artist/Album etc.) from Traditional to Simplified",
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    cc = OpenCC("t2s")
    ops = _build_plan(root, cc, sanitize_windows=not args.no_sanitize_windows)

    planned = 0
    changed_total = 0
    skipped_total = 0
    if ops:
        # Make destination names unique within same directory in a deterministic way.
        # Sorting ensures we handle siblings predictably.
        ops_sorted = sorted(ops, key=lambda x: (str(x.src.parent), str(x.src)))
        planned += len(ops_sorted)
        changed, skipped = _apply_plan(ops_sorted, dry_run=args.dry_run)
        changed_total += changed
        skipped_total += skipped

    tag_files = 0
    tag_fields_changed = 0
    if args.update_tags:
        # Re-scan after rename, so we always update tags on the final paths.
        for f in _iter_audio_files(root):
            ch, fields = _update_audio_tags_one(f, cc, dry_run=args.dry_run)
            if ch:
                tag_files += 1
                tag_fields_changed += fields

    if planned == 0 and not args.update_tags:
        print("No changes needed.")
        return 0

    print(
        "Done."
        f" planned={planned} changed={changed_total} skipped={skipped_total}"
        + (f" tag_files_changed={tag_files} tag_fields_changed={tag_fields_changed}" if args.update_tags else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

