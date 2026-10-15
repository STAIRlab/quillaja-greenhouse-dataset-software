"""Portable, read-only helpers for the Quillaja public resource."""
import csv
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
IMAGE_FIELDS = "release_id public_filename public_archive camera_id view date camera_timestamp_recorded original_filename original_relative_path file_size_bytes width height sequence_index".split()


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError(f"Malformed CSV: {path}")
        return rows

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def inside(base, relative):
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise ValueError(f"Unsafe relative path: {relative!r}")
    path = (Path(base) / relative).resolve()
    if not path.is_relative_to(Path(base).resolve()):
        raise ValueError(f"Path escapes its source root: {relative!r}")
    return path

def derive(images):
    result = []
    for source in sorted(images, key=lambda r: (r["camera_id"], r["date"], int(r["sequence_index"]))):
        camera = source["camera_id"]
        stamp = date.fromisoformat(source["date"])
        expected_id = f"QUI_{camera.replace('-', '')}_{stamp:%Y%m%d}_{int(source['sequence_index']):04d}"
        if camera not in {"GH-1", "GH-2"} or source["release_id"] != expected_id or source["file_extension"] != ".jpg" or int(source["sequence_index"]) < 1:
            raise ValueError(f"Research ID/camera/extension conflict: {source['release_id']}")
        r = {k: source[k] for k in IMAGE_FIELDS if k in source}
        r.update(public_filename=source["release_id"]+".jpg", public_archive=f"QUI_{camera.replace('-', '')}_{stamp:%Y-%m}.tar.gz")
        result.append(r)
    return result

def write_csv_new(path, fields, rows):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def verify_plan_scope(rows, plan):
    """Verify released sizes against the supplied plan, retaining scope checks."""
    from collections import Counter
    scope=plan['image_scope']
    if scope['total_images']!=len(rows) or scope['camera_counts']!=dict(Counter(r['camera_id'] for r in rows)):
        raise ValueError('Package plan image scope disagreement')
    total=sum(int(r['file_size_bytes']) for r in rows)
    if any(int(r['file_size_bytes'])<=0 for r in rows) or not isinstance(scope['logical_jpeg_bytes'],int) or scope['logical_jpeg_bytes']!=total:
        raise ValueError('Package plan logical payload mismatch')
    return total

def checked_public(path, plan=None):
    rows=read_csv(path)
    from collections import Counter
    if len(rows)!=38177 or Counter(r['camera_id'] for r in rows)!={'GH-1':19084,'GH-2':19093}:
        raise ValueError('Manifest scope differs from the published image collection')
    for key in ['release_id','public_filename','original_relative_path']:
        if len({r[key] for r in rows})!=len(rows): raise ValueError('Duplicate '+key)
    for r in rows:
        stamp=date.fromisoformat(r['date']); seq=int(r['sequence_index'])
        rid=f"QUI_{r['camera_id'].replace('-','')}_{stamp:%Y%m%d}_{seq:04d}"
        if r['release_id']!=rid or r['public_filename']!=rid+'.jpg' or seq<1:
            raise ValueError('Noncanonical public ID/name')
        if r['public_archive']!=f"QUI_{r['camera_id'].replace('-','')}_{stamp:%Y-%m}.tar.gz":
            raise ValueError('Archive camera/month mismatch')
        if not '2023-05-30'<=r['date']<='2023-10-10' or r['view']!={'GH-1':'top','GH-2':'side'}[r['camera_id']] or (r['width'],r['height'])!=('2560','1440'):
            raise ValueError('Date/view/dimensions mismatch')
    if len({r['public_archive'] for r in rows})!=12:
        raise ValueError('Archive count mismatch')
    if plan is None:
        plan=json.loads((Path(path).parent/'package_plan.json').read_text())
    verify_plan_scope(rows,plan)
    return rows
