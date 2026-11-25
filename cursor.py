"""Local, session-calibrated four-arrow P300 cursor. Moves are decided from EEG alone; targets never enter decoding."""
import numpy as np
from pathlib import Path
from analysis import CHANNELS
from speller import trial_features,calibration_responses,channel_model,window_choice,model_windows

ARROWS=('up','right','down','left')
STEP=((0,-1),(1,0),(0,1),(-1,0))
REPETITIONS=10                 # each arrow flashes this many times per move
FLASHES=4*REPETITIONS
GRID=7                         # 7 × 7 cells; the cursor starts in the centre
# Pacing used by cursor.js for every move: 2 s get-ready, 40 flashes 300 ms apart, 1.1 s settle.
SECONDS_PER_MOVE=2+FLASHES*.3+1.1

def examples(engine):
    events={e['index']:e for e in engine.events if e.get('kind')=='stimulus' and 'cursor' in e}
    rows=[]
    for trial in engine.trials:
        event=events.get(trial['index'])
        if not event:continue
        meta=event['cursor']
        rows.append(dict(features=trial_features(trial),group=meta['group'],arrow=meta['arrow'],target=meta.get('target'),phase=meta['phase']))
    return rows

def fit(rows):
    models={}
    for ch in CHANNELS:
        usable=[r for r in rows if ch in r['features']]
        y=np.array([r['arrow']==r['target'] for r in usable],dtype=bool)
        if y.sum()<8 or (~y).sum()<24:continue
        x=np.array([r['features'][ch] for r in usable]);groups=np.array([r['group'] for r in usable])
        window=window_choice(x,y,groups)
        if window is not None:models[ch]=channel_model(x,y,*window)
    return models

def decode(rows,models):
    # Require repeated clean observations of every arrow; never guess from a missing one.
    values=[[] for _ in ARROWS]
    for r in rows:
        scores=[float(((r['features'][ch]-m)/s)@w-b) for ch,(m,s,w,b) in models.items() if ch in r['features']]
        if scores:values[r['arrow']].append(float(np.mean(scores)))
    counts=list(map(len,values))
    if min(counts,default=0)<3:return dict(direction=None,counts=counts,scores=[],reason='Need at least three clean flashes of every arrow.')
    scores=[float(np.mean(v)) for v in values];order=np.argsort(scores)
    # The gap to the runner-up is classifier evidence, not a probability that the move is correct.
    return dict(direction=int(order[-1]),arrow=ARROWS[int(order[-1])],counts=counts,scores=scores,margin=float(scores[order[-1]]-scores[order[-2]]))

def calibrate(cal):
    groups=sorted({r['group'] for r in cal});models=fit(cal)
    predictions=[];by_channel={ch:[] for ch in models}
    for group in groups:
        train=[r for r in cal if r['group']!=group];test=[r for r in cal if r['group']==group]
        fold=fit(train);prediction=decode(test,fold)
        record=dict(group=group,expected=test[0]['target'],predicted=prediction.get('direction'))
        attended=[];unattended=[]
        for r in test:
            scores=[float(((r['features'][ch]-m)/scale)@w-b) for ch,(m,scale,w,b) in fold.items() if ch in r['features']]
            if scores:(attended if r['arrow']==r['target'] else unattended).append(float(np.mean(scores)))
        if attended and unattended:
            diff=np.asarray(attended)[:,None]-np.asarray(unattended)[None,:]
            record['auc']=float(np.mean((diff>0)+.5*(diff==0)))
        predictions.append(record)
        for ch in by_channel:
            single=decode(test,{ch:fold[ch]} if ch in fold else {})
            by_channel[ch].append({**record,'predicted':single.get('direction')})
    return models,predictions,by_channel

def bits_per_move(p,n=4):
    """Wolpaw information transfer for an n-choice selection made correctly with probability p."""
    if p<=1/n:return 0.0
    if p>=1:return float(np.log2(n))
    return float(np.log2(n)+p*np.log2(p)+(1-p)*np.log2((1-p)/(n-1)))

def calibration_quality(predictions):
    """Experimental readiness rule using outer held-out moves, never training fit. Chance is 1 in 4."""
    aucs=[p['auc'] for p in predictions if p.get('auc') is not None]
    n=len(predictions);correct=sum(p.get('predicted') is not None and p['predicted']==p['expected'] for p in predictions)
    auc=float(np.mean(aucs)) if aucs else None
    ready=n>=8 and len(aucs)==n and auc>=.65 and sum(a>.5 for a in aucs)/n>=.75 and correct/n>=.5
    bits=bits_per_move(correct/n) if n else 0.0
    return dict(ready=bool(ready),auc=auc,correct=correct,total=n,bits_per_move=bits,bits_per_minute=bits*60/SECONDS_PER_MOVE,seconds_per_move=SECONDS_PER_MOVE,
                message='Ready to steer the cursor.' if ready else 'Separation is weak or inconsistent. Check contact and attention, then add calibration moves.',
                rule='Experimental threshold: held-out AUC ≥ 0.65, above chance in ≥ 75% of moves, and ≥ 50% of moves correct (chance 25%). Bits per minute use the Wolpaw formula with held-out calibration accuracy at the app’s fixed pacing; not a validated prediction of future performance.')

def step(position,direction,size=GRID):
    x,y=position;dx,dy=STEP[direction]
    return [x+dx,y+dy] if 0<=x+dx<size and 0<=y+dy<size else [x,y]

def distance(a,b):return abs(a[0]-b[0])+abs(a[1]-b[1])

def helpful(position,target):
    """How many of the four arrows would bring the cursor closer: chance of a random move being helpful is this / 4."""
    return sum(distance(step(position,d),target)<distance(position,target) for d in range(4))

def cell(value):
    if not (isinstance(value,(list,tuple)) and len(value)==2 and all(type(v) is int and 0<=v<GRID for v in value)):raise ValueError('Invalid cursor cell')
    return [value[0],value[1]]

def task_summary(moves):
    targets={}
    for m in moves:targets.setdefault(m['target_number'],[]).append(m)
    rows=[dict(number=k,fewest=distance(v[0]['start'],v[0]['target']),moves=len(v),reached=any(m['reached'] for m in v)) for k,v in sorted(targets.items())]
    decided=[m for m in moves if m.get('direction') is not None]
    return dict(targets=rows,reached=sum(t['reached'] for t in rows),moves=len(moves),decided=len(decided),
                toward=sum(m['toward'] for m in decided),chance_toward=float(sum(m['helpful']/4 for m in decided)))

def saved_output(engine):
    s=engine.session;moves=s.get('cursor_moves',[])
    return dict(moves=moves,summary=task_summary(moves),windows=s.get('cursor_windows_ms',{}),quality=s.get('cursor_quality'))

def request(engine,body):
    with engine.lock:
        if not engine.session or engine.session.get('protocol')!='cursor':raise ValueError('Start a P300 cursor session first.')
        engine.process_pending()
        action=body.get('action')
        rows=examples(engine) if action in ('fit','move') else [];cal=[r for r in rows if r['phase']=='calibration'];groups=sorted({r['group'] for r in cal})
        result={'channels':calibration_responses(engine,'cursor'),'flashes':len(engine.trials),'source':engine.source}
        if action=='fit':
            if not 8<=len(groups)<=24 or any(sum(r['group']==g for r in cal)!=FLASHES for g in groups):raise ValueError('Complete at least eight calibration moves first.')
            models,predictions,by_channel=calibrate(cal)
            if not models:raise ValueError('Not enough clean calibration EEG across moves. Adjust contact and recalibrate.')
            engine.cursor_model=models;result['validation']=predictions
            s=engine.session
            s['cursor_validation']=predictions;s['cursor_quality']=calibration_quality(predictions)
            s['cursor_model_channels']=list(models);s['cursor_windows_ms']=model_windows(models)
            s['cursor_model_version']=1;s['cursor_channel_validation']=by_channel
            engine.cache_revision=None
            # Store the model alongside its calibration, only on this machine.
            from private_storage import DATA_ROOT
            np.savez_compressed(Path(DATA_ROOT)/s['id']/'cursor-model.npz',**{ch:np.concatenate([v[0],v[1],v[2],[v[3]]]) for ch,v in models.items()})
            engine.save_metadata()
        elif action=='move':
            models=getattr(engine,'cursor_model',None)
            if not models:raise ValueError('Calibrate before moving the cursor.')
            group=int(body['group'])
            prior=next((m for m in engine.session.get('cursor_moves',[]) if m['group']==group),None)
            if prior:return {**result,'move':prior,**saved_output(engine)}
            start=cell(body.get('position'));target=cell(body.get('target'));number=int(body.get('target_number',0))
            prediction=decode([r for r in rows if r['phase']=='moving' and r['group']==group],models)
            end=step(start,prediction['direction']) if prediction.get('direction') is not None else start
            move=dict(group=group,target_number=number,start=start,target=target,end=end,blocked=prediction.get('direction') is not None and end==start,
                      toward=distance(end,target)<distance(start,target),helpful=helpful(start,target),reached=end==target,**prediction)
            engine.session.setdefault('cursor_moves',[]).append(move)
            engine.event(dict(kind='note',cursor_move=move,group=group))
            engine.save_metadata();result['move']=move
        return {**result,**saved_output(engine)}

def retrospective_calibration(view):
    """Derived results only: never replace the model used in an older recording."""
    s=view.session
    if s.get('cursor_quality') or s.get('running'):return
    cal=[r for r in examples(view) if r['phase']=='calibration']
    groups={r['group'] for r in cal}
    if not 8<=len(groups)<=24 or any(sum(r['group']==g for r in cal)!=FLASHES for g in groups):return
    models,validation,channels=calibrate(cal)
    s['cursor_windows_ms']=model_windows(models)
    s['cursor_validation']=validation;s['cursor_channel_validation']=channels
    s['cursor_quality']=calibration_quality(validation)
    s['cursor_retrospective']=True;s['cursor_model_version']=1
