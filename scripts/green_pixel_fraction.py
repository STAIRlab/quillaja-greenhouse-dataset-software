#!/usr/bin/env python3
"""Reproduce the fixed-region GH-1 daily 15:00–18:00 green-pixel fraction."""
import argparse
from collections import defaultdict
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import tarfile
import numpy as np
from PIL import Image,ImageDraw
from common import checked_public,inside,write_csv_new,sha

def vegetation_mask(rgb):
    rgb=np.asarray(rgb,dtype=np.float32)
    red,green,blue=rgb[...,0],rgb[...,1],rgb[...,2]
    return (green>0)&(red<.95*green)&(blue<.95*green)&((2*green-red-blue)>20)

def region_mask(region):
    if region.get('analysis_scale')!=.5 or region.get('image_size_at_analysis')!=[1280,720]:
        raise ValueError('Expected the documented half-scale region')
    if region.get('colour_rule')!={'R_over_G_max_exclusive':.95,'B_over_G_max_exclusive':.95,'excess_green_min_exclusive':20}:
        raise ValueError('Region colour rule differs from the documented rule')
    points=region['polygon_xy']
    if len(points)<3 or any(len(p)!=2 or not(0<=p[0]<=2560 and 0<=p[1]<=1440) for p in points):
        raise ValueError('Invalid original-frame polygon')
    im=Image.new('L',(1280,720));ImageDraw.Draw(im).polygon([(x/2,y/2) for x,y in region['polygon_xy']],fill=255)
    mask=np.asarray(im)>0
    if not mask.any():raise ValueError('Empty bench region')
    return mask

def frame_fraction(data,roi):
    with Image.open(io.BytesIO(data)) as im:
        if im.size!=(2560,1440):raise ValueError('Expected original 2560x1440 geometry')
        im.draft('RGB',(1280,720));im.load()
        if im.size!=(1280,720):raise ValueError('Half-scale JPEG decoding unavailable')
        green=vegetation_mask(im.convert('RGB'))
    count=int(np.count_nonzero(green&roi));area=int(np.count_nonzero(roi))
    return count,area,count/area

def in_window(timestamp):
    minute=int(timestamp[11:13])*60+int(timestamp[14:16]);return 900<=minute<=1080

def selected_rows(public):
    gh=[r for r in public if r['camera_id']=='GH-1'];first=min(r['date'] for r in gh);last=max(r['date'] for r in gh)
    return [r for r in gh if first<r['date']<last and in_window(r['camera_timestamp_recorded'])]

def daily_rows(per_frame):
    groups=defaultdict(list)
    for r in per_frame:groups[r['timestamp'][:10]].append(float(r['green_fraction']))
    return [{'date':day,'green_fraction':float(np.median(values)),'frames':len(values)} for day,values in sorted(groups.items())]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--images-dir',type=Path);g.add_argument('--archives-dir',type=Path)
    p.add_argument('--region',type=Path,default=Path(__file__).resolve().parents[1]/'resources/green_fraction_region.json');p.add_argument('--out-dir',type=Path,required=True)
    a=p.parse_args();public=checked_public(a.dataset/'manifest__public_images.csv');selected=selected_rows(public);by_name={r['public_filename']:r for r in selected};region=json.loads(a.region.read_text());roi=region_mask(region)
    outputs=[a.out_dir/name for name in ['per_frame.csv','daily_series.csv','summary.json']]
    if any(p.exists() for p in outputs):raise FileExistsError('Use a new output directory; existing results are preserved')
    a.out_dir.mkdir(parents=True,exist_ok=True);features=[]
    def consume(row,data):
        count,area,value=frame_fraction(data,roi);features.append({'release_id':row['release_id'],'timestamp':row['camera_timestamp_recorded'],'green_pixels':count,'region_pixels':area,'green_fraction':value,'released_jpeg_sha256':hashlib.sha256(data).hexdigest()})
    if a.images_dir:
        for row in selected:consume(row,inside(a.images_dir,row['public_filename']).read_bytes())
    else:
        for name in sorted({r['public_archive'] for r in selected}):
            with tarfile.open(inside(a.archives_dir,name),'r|gz') as archive:
                for member in archive:
                    if member.name in by_name:
                        if not member.isfile():raise ValueError('Expected regular JPEG member')
                        with archive.extractfile(member) as f:consume(by_name[member.name],f.read())
            print(f'Computed {name}: {len(features)} selected frames so far',flush=True)
    if len(features)!=len(selected) or len({r['release_id'] for r in features})!=len(selected):raise ValueError('Missing or duplicate selected frames')
    features.sort(key=lambda r:r['release_id']);daily=daily_rows(features);values=np.array([r['green_fraction'] for r in daily])
    trend=np.array([np.median(values[i-3:i+4]) if 3<=i<len(values)-3 else np.nan for i in range(len(values))]);changes=np.diff(values-trend);valid=changes[np.isfinite(changes)]
    write_csv_new(outputs[0],list(features[0]),features);write_csv_new(outputs[1],list(daily[0]),daily)
    reaching=[r for r in daily if r['green_fraction']>=.9]
    summary={'rule':{'R_over_G_less_than':.95,'B_over_G_less_than':.95,'twoG_minus_R_minus_B_greater_than':20,'RGB_depth':8},'index':'green-pixel fraction; not calibrated ground cover','window':'15:00 to 18:00, recorded hour/minute inclusive','scale':.5,'region_file_sha256':sha(a.region),'region_pixels':int(roi.sum()),'region_share_of_frame':float(roi.mean()),'frames':len(features),'dates':len(daily),'first_date':daily[0]['date'],'first_value':daily[0]['green_fraction'],'last_date':daily[-1]['date'],'last_value':daily[-1]['green_fraction'],'first_date_at_least_90_percent':reaching[0]['date'] if reaching else None,'detrended_median_absolute_day_change':float(np.median(np.abs(valid))),'noise_pairs':len(valid),'source_manifest_sha256':sha(a.dataset/'manifest__public_images.csv'),'source_modified':False}
    with outputs[2].open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
