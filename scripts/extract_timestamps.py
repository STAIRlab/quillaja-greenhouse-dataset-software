#!/usr/bin/env python3
"""Run preserved fixed-font inference on explicitly selected public JPEGs."""
import argparse
from pathlib import Path
from PIL import Image
from common import checked_public, inside, read_csv, write_csv_new
from timestamp_core import Recognizer, parse_text

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--images-dir',type=Path,required=True)
    p.add_argument('--model',type=Path,default=Path(__file__).resolve().parents[1]/'resources/timestamp_ocr_model.json')
    p.add_argument('--out',type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--release-id',action='append');group.add_argument('--all',action='store_true')
    a=p.parse_args();rows=checked_public(a.manifest)
    selected=rows if a.all else [r for r in rows if r['release_id'] in set(a.release_id)]
    if not a.all and {r['release_id'] for r in selected}!=set(a.release_id): raise ValueError('Unknown requested ID')
    model=Recognizer(a.model);results=[]
    for r in selected:
        result={'release_id':r['release_id'],'public_filename':r['public_filename'],'camera_timestamp_recorded':r['camera_timestamp_recorded']}
        try:
            path=inside(a.images_dir,r['public_filename']);before=path.stat()
            if before.st_size!=int(r['file_size_bytes']): raise ValueError('Unexpected JPEG size')
            with Image.open(path) as im: raw,details=model.recognize(im)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise ValueError('Source changed')
            parsed=parse_text(raw,r['date']);score=min(c['score'] for c in details);margin=min(c['margin'] for c in details)
            issues=list(parsed['issues'])
            if score<model.model['min_character_score'] or margin<model.model['min_character_margin']: issues.append('low_glyph_score_or_margin')
            result.update(extracted_text=raw,candidate_timestamp=parsed['candidate'],min_character_score=score,min_character_margin=margin,
                          automatic_checks_passed=not issues,exact_recorded_timestamp_match=parsed['candidate']==r['camera_timestamp_recorded'],issues=';'.join(issues))
        except (OSError,ValueError) as exc:
            result.update(extracted_text='',candidate_timestamp='',min_character_score='',min_character_margin='',automatic_checks_passed=False,exact_recorded_timestamp_match=False,issues=type(exc).__name__+': '+str(exc))
        results.append(result)
    write_csv_new(a.out,list(results[0]),results)
    print(f"Inferred {len(results)} selected timestamps; accepted metadata unchanged.")
if __name__=='__main__': main()
