"""Local descriptive inventory for original matrix items; no upload or auto-training.

Usage: python scripts/report_matrix_pilots.py /explicit/personal/session/directory
Only aggregate item statistics are printed, never names, record IDs, EEG or text.
Session counts are NOT independent participant counts. Calibration requires the
separate review described in docs/matrix-original-bank.md.
"""
import argparse,json,statistics
from pathlib import Path

def report(paths):
    seen=set();groups={};excluded=0
    for path in paths:
        r=json.loads(path.read_text())
        if r.get('kind')!='matrix':continue
        if r.get('source') not in ('live','muse','ble','bluetooth') or r.get('matrix_result',{}).get('answered')!=12:
            excluded+=1;continue
        if not r.get('id') or r['id'] in seen:continue
        seen.add(r['id'])
        for v in r.get('matrix_pilot_responses',[]):
            if v.get('version')!='bandstand-matrix-pilot-v1':continue
            groups.setdefault(v['item_id'],[]).append(v)
    return dict(stage='descriptive collection only — not calibrated',sessions=len(seen),excluded_sessions=excluded,
                caveat='Repeated people may contribute multiple sessions. These are not independent participant counts; no scoring parameters are fitted or activated.',
                items=[dict(item_id=k,responses=len(v),correct=sum(x['correct'] for x in v),timeouts=sum(x['timeout'] for x in v),median_seconds=round(statistics.median(x['seconds'] for x in v),2)) for k,v in sorted(groups.items())])
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args()
    if not a.directory.is_dir():p.error('Choose an existing local personal-session directory')
    print(json.dumps(report(sorted(a.directory.glob('record-*.json'))),indent=2))
