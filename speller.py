"""Local, session-calibrated row/column P300 decoder. No text uploads."""
import numpy as np
from pathlib import Path
from analysis import CHANNELS

SYMBOLS='ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789 '

def examples(engine):
    events={e['index']:e for e in engine.events if e.get('kind')=='stimulus' and 'speller' in e}
    rows=[]
    for trial in engine.trials:
        event=events.get(trial['index'])
        if not event:continue
        meta=event['speller']; features={}
        times=np.asarray(trial['times'])
        for ch,result in trial.get('channel_trials',{}).items():
            if not result['accepted'] or result['wave'] is None:continue
            wave=np.asarray(result['wave'])
            features[ch]=np.array([wave[(times>=lo)&(times<lo+.05)].mean() for lo in (.1+np.arange(14)*.05)])
        rows.append(dict(features=features,group=meta['group'],line=meta['line'],target=meta.get('target'),phase=meta['phase']))
    return rows

def channel_model(x,y,start,end):
    mean=x.mean(0);scale=np.maximum(x.std(0),.1);z=((x-mean)/scale)[:,start:end]
    a=z[y].mean(0);b=z[~y].mean(0);res=z-np.where(y[:,None],a,b)
    cov=res.T@res/max(1,len(res)-2);cov=.7*cov+.3*np.eye(len(a))*max(np.trace(cov)/len(a),.01)
    w=np.linalg.solve(cov,a-b);norm=max(float(np.sqrt(w@cov@w)),.1)
    weights=np.zeros(x.shape[1]);weights[start:end]=w/norm
    return mean,scale,weights,float((a+b)@w/(2*norm))

def window_choice(x,y,groups):
    # Inner whole-letter validation chooses both position and duration. The outer
    # held-out letter never enters this function during performance evaluation.
    folds=[]
    for group in np.unique(groups):
        train=groups!=group;test=~train
        if y[train].sum()>=8 and (~y[train]).sum()>=24 and y[test].any() and (~y[test]).any():folds.append((train,test))
    if len(folds)<3:return None
    best=None
    for width in range(2,min(8,x.shape[1])+1):
        for start in range(x.shape[1]-width+1):
            scores=[]
            for train,test in folds:
                m,scale,w,b=channel_model(x[train],y[train],start,start+width)
                values=((x[test]-m)/scale)@w-b;target=values[y[test]];other=values[~y[test]]
                diff=target[:,None]-other[None,:]
                scores.append(float(np.mean((diff>0)+.5*(diff==0))))
            # In exact ties prefer a wider interval rather than an isolated peak.
            rank=(float(np.mean(scores)),width,-start)
            if best is None or rank>best[0]:best=(rank,start,start+width)
    return best[1:]

def fit(rows):
    models={}
    for ch in CHANNELS:
        usable=[r for r in rows if ch in r['features']]
        y=np.array([r['line'] in (r['target']//6,6+r['target']%6) for r in usable],dtype=bool)
        if y.sum()<8 or (~y).sum()<24:continue
        x=np.array([r['features'][ch] for r in usable]);groups=np.array([r['group'] for r in usable])
        window=window_choice(x,y,groups)
        if window is not None:models[ch]=channel_model(x,y,*window)
    return models

def calibrate(cal):
    groups=sorted({r['group'] for r in cal});models=fit(cal)
    predictions=[];by_channel={ch:[] for ch in models}
    for group in groups:
        train=[r for r in cal if r['group']!=group];test=[r for r in cal if r['group']==group]
        fold=fit(train);prediction=decode(test,fold)
        record=dict(group=group,expected=test[0]['target'],predicted=prediction.get('index'))
        attended=[];unattended=[]
        for r in test:
            scores=[float(((r['features'][ch]-m)/scale)@w-b) for ch,(m,scale,w,b) in fold.items() if ch in r['features']]
            if scores:(attended if r['line'] in (r['target']//6,6+r['target']%6) else unattended).append(float(np.mean(scores)))
        if attended and unattended:
            diff=np.asarray(attended)[:,None]-np.asarray(unattended)[None,:]
            record['auc']=float(np.mean((diff>0)+.5*(diff==0)))
        predictions.append(record)
        for ch in by_channel:
            single=decode(test,{ch:fold[ch]} if ch in fold else {})
            by_channel[ch].append({**record,'predicted':single.get('index')})
    return models,predictions,by_channel


def calibration_quality(predictions):
    """Experimental readiness rule using outer held-out letters, never training fit."""
    aucs=[p['auc'] for p in predictions if p.get('auc') is not None]
    n=len(predictions);correct=sum(p.get('predicted') is not None and p['predicted']==p['expected'] for p in predictions)
    auc=float(np.mean(aucs)) if aucs else None
    ready=n>=8 and len(aucs)==n and auc>=.65 and sum(a>.5 for a in aucs)/n>=.75 and correct/n>=.5
    return dict(ready=bool(ready),auc=auc,correct=correct,total=n,
                message='Ready to try spelling.' if ready else 'Separation is weak or inconsistent. Check contact and attention, then add calibration letters.',
                rule='Experimental threshold: held-out AUC ≥ 0.65, above chance in ≥ 75% of letters, and ≥ 50% letters correct. Not a validated probability of future accuracy.')


def decode(rows,models):
    # Require repeated clean observations for every row and column; never guess from missing lines.
    values=[[] for _ in range(12)]
    for r in rows:
        scores=[float(((r['features'][ch]-m)/s)@w-b) for ch,(m,s,w,b) in models.items() if ch in r['features']]
        if scores:values[r['line']].append(float(np.mean(scores)))
    counts=list(map(len,values))
    if min(counts,default=0)<3:return dict(symbol=None,counts=counts,scores=[],reason='Need at least three clean flashes of every row and column.')
    scores=[float(np.mean(v)) for v in values];index=int(np.argmax(scores[:6]))*6+int(np.argmax(scores[6:]))
    # Evidence gaps are not calibrated probabilities of spelling correctly.
    gaps=[float(np.sort(scores[lo:lo+6])[-1]-np.sort(scores[lo:lo+6])[-2]) for lo in (0,6)]
    return dict(symbol=SYMBOLS[index],index=index,counts=counts,scores=scores,row_margin=gaps[0],column_margin=gaps[1])

def model_windows(models):
    return {ch:[int(100+50*np.flatnonzero(v[2])[0]),int(150+50*np.flatnonzero(v[2])[-1])] for ch,v in models.items() if np.any(v[2])}

def saved_output(engine):
    return dict(text=engine.session.get('speller_text',''),history=engine.session.get('speller_history',[]),windows=engine.session.get('speller_windows_ms',{}),quality=engine.session.get('speller_quality'))

def request(engine,body):
    with engine.lock:
        if not engine.session or engine.session.get('protocol')!='speller':raise ValueError('Start a P300 spelling session first.')
        engine.process_pending()
        rows=examples(engine) if body.get('action') in ('fit','predict') else [];cal=[r for r in rows if r['phase']=='calibration'];groups=sorted({r['group'] for r in cal})
        result={'channels':{},'flashes':len(engine.trials),'source':engine.source}
        event_map={e['index']:e for e in engine.events if e.get('kind')=='stimulus'}
        for ch in CHANNELS:
            waves=[[],[]]
            for t in engine.trials:
                e=event_map.get(t['index'])
                if not e or e.get('speller',{}).get('phase')!='calibration':continue
                v=t.get('channel_trials',{}).get(ch,{})
                if v.get('accepted'):waves[t['condition_index']].append(v['wave'])
            result['channels'][ch]=[{'n':len(w),'mean':np.mean(w,axis=0).tolist() if w else [],'ci':(1.96*np.std(w,axis=0,ddof=1)/np.sqrt(len(w))).tolist() if len(w)>1 else []} for w in waves]
        if body.get('action')=='fit':
            if not 8<=len(groups)<=24 or any(sum(r['group']==g for r in cal)!=60 for g in groups):raise ValueError('Complete at least eight calibration letters first.')
            models,predictions,by_channel=calibrate(cal)
            if not models:raise ValueError('Not enough clean calibration EEG across letters. Adjust contact and recalibrate.')
            engine.speller_model=models;result['validation']=predictions
            engine.session['speller_validation']=predictions
            engine.session['speller_quality']=calibration_quality(predictions)
            engine.session['speller_model_channels']=list(models)
            engine.session['speller_windows_ms']=model_windows(models)
            engine.session['speller_model_version']=3
            engine.session['speller_channel_validation']=by_channel
            engine.cache_revision=None
            # Store model alongside its calibration, only on this machine.
            from private_storage import DATA_ROOT
            np.savez_compressed(Path(DATA_ROOT)/engine.session['id']/'speller-model.npz',**{ch:np.concatenate([v[0],v[1],v[2],[v[3]]]) for ch,v in models.items()})
            engine.save_metadata()
        elif body.get('action')=='delete':
            engine.session['speller_text']=engine.session.get('speller_text','')[:-1]
            engine.session['speller_history']=engine.session.get('speller_history',[])[:-1]
            engine.save_metadata()
        elif body.get('action')=='predict':
            models=getattr(engine,'speller_model',None)
            if not models:raise ValueError('Calibrate before spelling.')
            group=int(body['group']);result['prediction']=decode([r for r in rows if r['phase']=='spelling' and r['group']==group],models)
            prior=next((e for e in engine.events if 'speller_prediction' in e and e.get('group')==group),None)
            if prior:return {**result,'prediction':prior['speller_prediction'],**saved_output(engine)}
            prediction=result['prediction']
            if prediction.get('symbol') is not None:
                engine.session['speller_text']=engine.session.get('speller_text','')+prediction['symbol']
                engine.session.setdefault('speller_history',[]).append(dict(group=group,**prediction))
            engine.event(dict(kind='note',speller_prediction=prediction,group=group))
        return {**result,**saved_output(engine)}


def retrospective_calibration(view):
    """Derived results only: never replace the model used in an older recording."""
    s=view.session
    if s.get('speller_quality') or s.get('running'):return
    cal=[r for r in examples(view) if r['phase']=='calibration']
    groups={r['group'] for r in cal}
    if not 8<=len(groups)<=24 or any(sum(r['group']==g for r in cal)!=60 for g in groups):return
    models,validation,channels=calibrate(cal)
    s['speller_windows_ms']=model_windows(models)
    s['speller_original_validation']=s.get('speller_validation',[])
    s['speller_validation']=validation;s['speller_channel_validation']=channels
    s['speller_quality']=calibration_quality(validation)
    s['speller_retrospective']=True;s['speller_model_version']=3
