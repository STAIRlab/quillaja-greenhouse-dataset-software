#!/usr/bin/env python3
"""Apply exact documented head rectangles to new copies; never infer or repad."""
import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image
from common import checked_public,inside,read_csv,sha
from image_notes import validate_notes_rows

def wipe_jpeg(data,rectangles,jpegtran='jpegtran'):
    for x0,y0,x1,y1 in rectangles:
        geometry=f'{x1-x0}x{y1-y0}+{x0}+{y0}'
        data=subprocess.run([jpegtran,'-copy','none','-optimize','-wipe',geometry],input=data,capture_output=True,check=True).stdout
    return data

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--images-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--jpegtran',default='jpegtran')
    a=p.parse_args();binary=shutil.which(a.jpegtran)
    if not binary:raise FileNotFoundError('jpegtran is required; this script does not install tools')
    public=checked_public(a.dataset/'manifest__public_images.csv');images=read_csv(a.dataset/'metadata__images.csv')
    plan=json.loads((a.dataset/'package_plan.json').read_text())
    _,masks=validate_notes_rows(read_csv(a.dataset/'metadata__image_notes.csv'),public,images,plan)
    by_id={r['release_id']:r for r in images};out=a.output_dir.resolve();source=a.images_dir.resolve()
    if out==source or out.is_relative_to(source):raise ValueError('Output must be outside the source image tree')
    targets=[out/(rid+'.jpg') for rid in masks]
    if any(t.exists() for t in targets) or (out/'masking_report.json').exists():raise FileExistsError('Preserving existing masking outputs')
    out.mkdir(parents=True,exist_ok=True);records=[]
    version=subprocess.run([binary,'-version'],capture_output=True,text=True,check=True)
    for rid,rectangles in sorted(masks.items()):
        path=inside(source,rid+'.jpg');before=sha(path);data=path.read_bytes();row=by_id[rid]
        if 'original_file_size_bytes' in row and len(data)!=int(row['original_file_size_bytes']):raise ValueError('Expected unmasked source size: '+rid)
        with Image.open(io.BytesIO(data)) as im:
            im.load();size=im.size;quant=im.quantization
        masked=wipe_jpeg(data,rectangles,binary)
        with Image.open(io.BytesIO(masked)) as im:
            im.load()
            if im.size!=size or im.quantization!=quant:raise ValueError('JPEG geometry/quantization changed')
        if sha(path)!=before:raise ValueError('Source changed during masking')
        target=out/(rid+'.jpg')
        with target.open('xb') as f:f.write(masked)
        records.append({'release_id':rid,'rectangles_xyxy':rectangles,'source_sha256':before,'masked_sha256':sha(target),'masked_bytes':len(masked)})
    report={'masked_frames':len(records),'jpegtran_version':(version.stdout+version.stderr).strip(),'options':['-copy','none','-optimize','-wipe'],'records':records,'source_files_modified':0}
    with (out/'masking_report.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({'masked_frames':len(records),'report':str(out/'masking_report.json')}))
if __name__=='__main__':main()
