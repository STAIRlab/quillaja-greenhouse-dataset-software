#!/usr/bin/env python3
"""Reproduce observed-window slot coverage from accepted recorded timestamps."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
from common import checked_public
ORIGIN=datetime(2023,1,1)
STEP=600

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();rows=checked_public(a.dataset/'manifest__public_images.csv');results={}
    for camera in ['GH-1','GH-2']:
        selected=sorted((r for r in rows if r['camera_id']==camera),key=lambda r:(r['date'],int(r['sequence_index'])))
        times=[datetime.fromisoformat(r['camera_timestamp_recorded']) for r in selected]
        slots=[(int((t-ORIGIN).total_seconds())+STEP//2)//STEP for t in times]
        if len(set(slots))!=len(slots) or any(b<=a for a,b in zip(times,times[1:])): raise ValueError('Nonunique or nonincreasing clock/slot')
        missing=sorted(set(range(min(slots),max(slots)+1))-set(slots))
        expected=max(slots)-min(slots)+1
        residual=max(abs((t-(ORIGIN+timedelta(seconds=slot*STEP))).total_seconds()) for t,slot in zip(times,slots))
        results[camera]={'observed':len(slots),'expected':expected,'missing':len(missing),'coverage_percent':100*len(slots)/expected,
          'first_slot':(ORIGIN+timedelta(seconds=min(slots)*STEP)).isoformat(),'last_slot':(ORIGIN+timedelta(seconds=max(slots)*STEP)).isoformat(),
          'max_absolute_slot_residual_seconds':residual,'missing_recorded_clock_slots':[(ORIGIN+timedelta(seconds=s*STEP)).isoformat() for s in missing]}
    if (results['GH-1']['expected'],results['GH-2']['expected'],results['GH-1']['missing'],results['GH-2']['missing'])!=(19140,19140,56,47):
        raise ValueError('Coverage differs from frozen published facts')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x') as f: json.dump({'passed':True,'timestamp_values_changed':False,'method':'nearest 600-second slot; half-up; inclusive observed endpoints; streams independent','cameras':results},f,indent=2);f.write('\n')
    print(json.dumps({k:{n:v[n] for n in ['observed','expected','missing']} for k,v in results.items()}))
if __name__=='__main__': main()
