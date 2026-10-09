#!/usr/bin/env python3
"""Rebuild one deterministic monthly archive, preserving every source JPEG byte."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import tarfile
import zlib
from common import checked_public, inside, sha

class HashingReader:
    def __init__(self,stream): self.stream=stream;self.digest=hashlib.sha256();self.count=0
    def read(self,size=-1):
        b=self.stream.read(size);self.digest.update(b);self.count+=len(b);return b

def signature(path):
    s=path.stat();return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    sources=p.add_mutually_exclusive_group(required=True)
    sources.add_argument('--images-dir',type=Path);sources.add_argument('--raw-source-root',type=Path)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--camera',choices=['GH-1','GH-2'],required=True);p.add_argument('--month',required=True)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--dry-run',action='store_true');mode.add_argument('--build',action='store_true')
    a=p.parse_args();rows=checked_public(a.manifest)
    selected=sorted((r for r in rows if r['camera_id']==a.camera and r['date'][:7]==a.month),key=lambda r:r['release_id'])
    if not selected: raise ValueError('No images selected')
    names={r['public_archive'] for r in selected}
    if len(names)!=1: raise ValueError('Mixed archive selection')
    source_root=(a.images_dir or a.raw_source_root).resolve();dest=a.output_dir.resolve()
    if dest.is_relative_to(source_root): raise ValueError('Output must be outside the image source directory')
    seen=set();items=[]
    for r in selected:
        path=inside(source_root,r['public_filename'] if a.images_dir else r['original_relative_path'])
        if not path.is_file(): raise FileNotFoundError(path)
        sig=signature(path)
        if sig[:2] in seen or sig[2]!=int(r['file_size_bytes']): raise ValueError('Duplicate source or unexpected byte size')
        seen.add(sig[:2]);items.append((r,path,sig))
    summary={'archive':next(iter(names)),'images':len(items),'logical_jpeg_bytes':sum(int(r['file_size_bytes']) for r,_,_ in items)}
    if a.dry_run: print(json.dumps({'dry_run':True,**summary},sort_keys=True));return
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/summary['archive'];partial=target.with_name(target.name+'.incomplete')
    ledger=target.with_name(target.name+'.members.csv');report=target.with_name(target.name+'.build.json')
    if any(x.exists() for x in [target,partial,ledger,report]): raise FileExistsError('Preserving existing archive/sidecars')
    with partial.open('xb') as out,ledger.open('x',newline='') as lf:
        writer=csv.DictWriter(lf,fieldnames=['release_id','public_filename','file_size_bytes','source_sha256']);writer.writeheader()
        with gzip.GzipFile(filename='',mode='wb',fileobj=out,compresslevel=6,mtime=0) as gz:
            with tarfile.open(fileobj=gz,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
                for r,path,sig in items:
                    if signature(path)!=sig: raise ValueError('Source changed before reading')
                    info=tarfile.TarInfo(r['public_filename']);info.size=int(r['file_size_bytes']);info.mtime=0;info.mode=0o644
                    info.uid=info.gid=0;info.uname=info.gname=''
                    with path.open('rb') as src:
                        reader=HashingReader(src);tar.addfile(info,reader)
                    if signature(path)!=sig or reader.count!=info.size: raise ValueError('Source changed while reading')
                    writer.writerow({'release_id':r['release_id'],'public_filename':r['public_filename'],'file_size_bytes':info.size,'source_sha256':reader.digest.hexdigest()})
        out.flush();os.fsync(out.fileno())
    partial.rename(target)
    summary.update(archive_sha256=sha(target),compressed_bytes=target.stat().st_size,manifest_sha256=sha(a.manifest),members_sha256=sha(ledger),python=platform.python_version(),zlib=zlib.ZLIB_VERSION,jpeg_reencoded=False)
    with report.open('x') as f: json.dump(summary,f,indent=2);f.write('\n')
    print(json.dumps(summary,sort_keys=True))
if __name__=='__main__': main()
