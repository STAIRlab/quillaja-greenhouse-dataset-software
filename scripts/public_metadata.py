#!/usr/bin/env python3
"""Derive and validate public tables without changing accepted scientific values."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from common import IMAGE_FIELDS, checked_public, derive, read_csv, write_csv_new
from image_notes import validate_notes_rows


def validate_tables(dataset):
    dataset=Path(dataset)
    public=checked_public(dataset/'manifest__public_images.csv')
    images=read_csv(dataset/'metadata__images.csv')
    if derive(images)!=public: raise ValueError('Public manifest is not an exact one-to-one derivation')
    by_id={r['release_id']:r for r in images}
    for row in images:
        if row['included_in_release']!='True' or row['timestamp_status']!='accepted_automatic_checks':
            raise ValueError('Unexpected inclusion or accepted-timestamp status')
        for key in ['timestamp_review_flags','chronology_flags']:
            if not isinstance(json.loads(row[key]),list): raise ValueError('Malformed flag list')
        if datetime.fromisoformat(row['camera_timestamp_recorded']).date().isoformat()!=row['date']:
            raise ValueError('Camera date disagreement')
    hobo=read_csv(dataset/'environmental__hobo.csv')
    if len(hobo)!=24035 or Counter(r['deployment_number'] for r in hobo)!={'6':4309,'7':3885,'8':15841}:
        raise ValueError('Environmental scope disagreement')
    keys=set()
    for r in hobo:
        key=tuple(r[k] for k in ['source_file','source_sheet','source_row'])
        if key in keys: raise ValueError('Duplicate environmental provenance key')
        keys.add(key)
        datetime.fromisoformat(r['timestamp_recorded'])
        for k in ['temperature_F','relative_humidity_percent','dew_point_F']: float(r[k])
    for number in ['6','7','8']:
        times=[datetime.fromisoformat(r['timestamp_recorded']) for r in hobo if r['deployment_number']==number]
        if any((b-a).total_seconds()!=600 for a,b in zip(times,times[1:])):
            raise ValueError('Environmental interval disagreement')
    anchors=read_csv(dataset/'metadata__reference_spatial_anchors.csv')
    if len(anchors)!=17 or len({r['anchor_id'] for r in anchors})!=17 or Counter(r['camera_id'] for r in anchors)!={'GH-1':12,'GH-2':5}:
        raise ValueError('Anchor scope disagreement')
    anchor_ids={r['anchor_id'] for r in anchors}
    for row in anchors:
        source=by_id[row['reference_image_id']]
        if any(row[k]!=source[k] for k in ['camera_id','view']) or row['reference_timestamp_recorded']!=source['camera_timestamp_recorded']:
            raise ValueError('Anchor reference disagreement')
        if not 0<=int(row['x_px'])<2560 or not 0<=int(row['y_px'])<1440: raise ValueError('Anchor outside image')
    events=read_csv(dataset/'metadata__scene_events.csv')
    if len(events)!=2 or {r['event_id'] for r in events}!={'GH1_E001','GH2_E001'}: raise ValueError('Event scope disagreement')
    for row in events:
        for prefix in ['before','after']:
            source=by_id[row[prefix+'_image_id']]
            if any(row[k]!=source[k] for k in ['camera_id','view']) or row[prefix+'_timestamp_recorded']!=source['camera_timestamp_recorded']:
                raise ValueError('Event reference disagreement')
        if row['time_interval_start']!=row['before_timestamp_recorded'] or row['time_interval_end']!=row['after_timestamp_recorded'] or row['time_interval_start']>=row['time_interval_end']:
            raise ValueError('Event clock bounds disagree')
        if not set(json.loads(row['affected_anchor_ids'] or '[]'))<=anchor_ids: raise ValueError('Unknown event anchor')
    plan=json.loads((dataset/'package_plan.json').read_text())
    notes_path=dataset/'metadata__image_notes.csv'
    if 'image_masking' in plan and not notes_path.is_file():raise ValueError('Missing required image notes')
    notes_summary,_=validate_notes_rows(read_csv(notes_path) if notes_path.is_file() else [],public,images,plan)
    return {'passed':True,'images':len(public),'cameras':dict(Counter(r['camera_id'] for r in public)),
            'hobo_records':len(hobo),'reference_anchors':len(anchors),'scene_events':len(events),
            'image_notes':notes_summary,'logical_jpeg_bytes':sum(int(r['file_size_bytes']) for r in public)}, public


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();summary,rows=validate_tables(a.dataset)
    write_csv_new(a.out,IMAGE_FIELDS,rows)
    print(json.dumps(summary,sort_keys=True))
if __name__=='__main__': main()
