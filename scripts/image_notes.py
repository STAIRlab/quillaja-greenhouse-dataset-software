"""Validate optional per-frame masking and exposure notes."""
import json

FIELDS=['release_id','note_type','box_or_description']

def mask_rectangles(value):
    rectangles=json.loads(value)
    if not isinstance(rectangles,list) or not rectangles:
        raise ValueError('A masked-frame note requires nonempty xyxy rectangles')
    seen=set()
    for box in rectangles:
        if not isinstance(box,list) or len(box)!=4 or not all(isinstance(v,int) and not isinstance(v,bool) for v in box):
            raise ValueError('Mask coordinates must be integer xyxy values')
        x0,y0,x1,y1=box
        if any(v%16 for v in box) or not(0<=x0<x1<=2560 and 0<=y0<y1<=1440):
            raise ValueError('Mask bounds or16x16 MCU alignment invalid')
        if x1>1600 and y1>1344:
            raise ValueError('Mask overlaps the protected timestamp band')
        if tuple(box) in seen:raise ValueError('Duplicate mask rectangle')
        seen.add(tuple(box))
    return rectangles

def validate_notes_rows(notes, public, images=None, plan=None):
    known={r['release_id'] for r in public};keys=set();masked={};exposure=[]
    for row in notes:
        if set(row)!=set(FIELDS):raise ValueError('Image-notes fields disagree with schema')
        rid=row['release_id'];kind=row['note_type'];key=(rid,kind)
        if rid not in known:raise ValueError('Unknown image-notes release ID')
        if key in keys:raise ValueError('Duplicate image-notes key')
        keys.add(key)
        if kind=='person_masked':masked[rid]=mask_rectangles(row['box_or_description'])
        elif kind=='exposure_anomaly':
            if not row['box_or_description'].strip():raise ValueError('Empty exposure-anomaly description')
            exposure.append(rid)
        else:raise ValueError('Unknown image-notes note type')
    if images is not None:
        for row in images:
            if 'original_file_size_bytes' in row:
                original=int(row['original_file_size_bytes']);released=int(row['file_size_bytes'])
                if original<=0:raise ValueError('Invalid original image byte size')
                if original!=released and row['release_id'] not in masked:
                    raise ValueError('Changed image size without a masking note')
    if plan and 'image_masking' in plan:
        from collections import Counter
        policy=plan['image_masking'];by_id={r['release_id']:r for r in public}
        if policy['masked_frames']!=len(masked):raise ValueError('Masking note count disagrees with package plan')
        counts=Counter(by_id[rid]['camera_id'] for rid in masked)
        if any(counts.get(camera,0)!=count for camera,count in policy['camera_counts'].items()):
            raise ValueError('Masked camera counts disagree with package plan')
    return {'masked_frames':len(masked),'mask_rectangles':sum(map(len,masked.values())),'exposure_notes':len(exposure)},masked
