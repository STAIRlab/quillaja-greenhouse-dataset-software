#!/usr/bin/env python3
"""Validate downloaded tables, checksums and optionally selected/all payloads."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from common import inside, sha, write_csv_new
from public_metadata import validate_tables


def verify_payload(path, rows, source_root=None, image_hashes=None):
    expected=sorted(rows,key=lambda r:r['release_id']);seen=set();logical=0
    with path.open('rb') as compressed,gzip.GzipFile(fileobj=compressed,mode='rb') as gz:
        with tarfile.open(fileobj=gz,mode='r|') as tar:
            count=0
            for member in tar:
                if count>=len(expected): raise ValueError('Extra archive member')
                row=expected[count]
                if member.name!=row['public_filename'] or member.name in seen or not member.isfile() or member.size!=int(row['file_size_bytes']):
                    raise ValueError('Unexpected member name/type/size/order')
                if (member.uid,member.gid,member.mode,member.mtime,member.uname,member.gname)!=(0,0,0o644,0,'',''):
                    raise ValueError('Unexpected archive header metadata')
                digest=hashlib.sha256();size=0
                with tar.extractfile(member) as stream:
                    while block:=stream.read(1024*1024): digest.update(block);size+=len(block)
                if size!=member.size: raise ValueError('Truncated JPEG payload')
                if source_root is not None and digest.hexdigest()!=sha(inside(source_root,member.name)):
                    raise ValueError('JPEG payload differs from supplied source: '+member.name)
                if image_hashes is not None:
                    image_hashes.append({'release_id':row['release_id'],'public_filename':member.name,
                        'file_size_bytes':size,'sha256':digest.hexdigest()})
                seen.add(member.name);logical+=size;count+=1
        # Read through gzip footer/CRC after the tar end marker.
        while gz.read(1024*1024): pass
    if count!=len(expected): raise ValueError('Missing archive members')
    return {'archive':path.name,'members':count,'logical_jpeg_bytes':logical,'source_content_compared':source_root is not None,'passed':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    g=p.add_mutually_exclusive_group();g.add_argument('--metadata-only',action='store_true');g.add_argument('--archive',action='append');g.add_argument('--payloads',action='store_true')
    p.add_argument('--source-root',type=Path,help='Optional extracted canonical JPEGs for content comparison')
    p.add_argument('--archives-dir',type=Path,help='Complete canonical archives, if stored outside the flat deposit directory')
    p.add_argument('--image-hashes-out',type=Path,help='New CSV of per-JPEG SHA-256 values observed during payload validation')
    a=p.parse_args()
    if a.source_root and not (a.payloads or a.archive): p.error('--source-root requires --payloads or --archive')
    if (a.archives_dir or a.image_hashes_out) and not (a.payloads or a.archive): p.error('Archive directory/image hashes require --payloads or --archive')
    if a.image_hashes_out and a.image_hashes_out.exists():raise FileExistsError(a.image_hashes_out)
    summary,rows=validate_tables(a.dataset);summary.update(hash_checked_files=[],payload_checks=[])
    archive_names=sorted({r['public_archive'] for r in rows})
    if a.archive and (len(set(a.archive))!=len(a.archive) or not set(a.archive)<=set(archive_names)): raise ValueError('Unknown or duplicate selected archive')
    if not a.metadata_only:
        entries={}
        for line in (a.dataset/'checksums__SHA256SUMS.txt').read_text().splitlines():
            digest,name=line.split('  ',1)
            if name in entries or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest): raise ValueError('Malformed checksum ledger')
            inside(a.dataset,name);entries[name]=digest
        names=a.archive or list(entries)
        if not a.archive:
            plan=json.loads((a.dataset/'package_plan.json').read_text())
            expected={r['filename'] for r in plan['files']}-{'checksums__SHA256SUMS.txt'}
            if set(entries)!=expected: raise ValueError('Ledger/plan disagreement')
        for name in names:
            base=a.archives_dir if a.archive and a.archives_dir else a.dataset
            if name not in entries or sha(inside(base,name))!=entries[name]: raise ValueError('File checksum disagreement: '+name)
            summary['hash_checked_files'].append(name)
    if a.payloads or a.archive:
        mapping=json.loads((a.dataset/'archive_parts.json').read_text())
        archives={r['logical_archive']:r for r in mapping['archives']}
        if len(archives)!=len(mapping['archives']) or set(archives)!=set(archive_names):raise ValueError('Archive map membership disagreement')
        image_hashes=[] if a.image_hashes_out else None
        for name in (a.archive or archive_names):
            selected=[r for r in rows if r['public_archive']==name];record=archives[name]
            if record['image_count']!=len(selected) or record['logical_jpeg_bytes']!=sum(int(r['file_size_bytes']) for r in selected):raise ValueError('Archive map payload totals disagree')
            path=inside(a.archives_dir or a.dataset,name)
            if path.stat().st_size!=record['archive_byte_size'] or sha(path)!=record['archive_sha256']:raise ValueError('Complete archive hash/size disagreement: '+name)
            summary['payload_checks'].append(verify_payload(path,selected,a.source_root,image_hashes))
        if a.image_hashes_out:
            write_csv_new(a.image_hashes_out,['release_id','public_filename','file_size_bytes','sha256'],image_hashes)
            summary['image_sha256_ledger']=str(a.image_hashes_out)
    summary['scope']='metadata_only' if a.metadata_only else 'selected_archives' if a.archive else 'all_files_and_payloads' if a.payloads else 'all_file_hashes_and_metadata'
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x') as f: json.dump(summary,f,indent=2);f.write('\n')
    print(json.dumps({k:summary[k] for k in ['passed','scope','images','hobo_records','reference_anchors','scene_events']}))
if __name__=='__main__': main()
