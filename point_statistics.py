"""Exploratory pointwise comparisons, one family across tested coordinates and channels."""
import numpy as np
from analysis import compare, CHANNELS
from spectral_inference import compare_periods


def adjust_pvalues(values, method='holm'):
    p=np.asarray(values,dtype=float)
    if not np.isfinite(p).all() or np.any((p<0)|(p>1)):raise ValueError('Invalid p-values')
    if method not in ('holm','bh','by','none'):raise ValueError('Unknown correction')
    n=len(p)
    if not n:return []
    order=np.argsort(p);rank=np.arange(1,n+1);sorted_p=p[order]
    if method=='holm':q=np.maximum.accumulate(sorted_p*(n-rank+1))
    elif method in ('bh','by'):
        factor=np.sum(1/rank) if method=='by' else 1
        q=np.minimum.accumulate((sorted_p*n*factor/rank)[::-1])[::-1]
    else:q=sorted_p
    result=np.empty(n);result[order]=np.minimum(1,q)
    return result.tolist()


def point_statistics(trials, session, low, high, first=0, second=1, correction='holm', single=False, full_family=False):
    mode=session.get('mode');low=float(low);high=float(high);first=int(first);second=int(second)
    conditions=session['conditions']
    if mode not in ('erp','tf'):raise ValueError('Pointwise statistics require ERP or spectral data')
    if not (0<=first<len(conditions) and 0<=second<len(conditions)) or first==second:raise ValueError('Choose two different conditions')
    if not np.isfinite([low,high]).all() or low>high:raise ValueError('Choose a valid interval')
    if correction not in ('holm','bh','by','none'):raise ValueError('Unknown correction')
    spectral=mode=='tf'
    grid=np.arange(2,40.01,.5) if spectral else np.asarray(trials[0]['times'] if trials else [],dtype=float)*1000
    limits=(2,40) if spectral else (-200,800)
    if low<limits[0] or high>limits[1]:raise ValueError('Range outside available coordinates')
    indices=[int(np.argmin(abs(grid-low)))] if single and len(grid) else np.flatnonzero((grid>=low-1e-7)&(grid<=high+1e-7)).tolist()
    if len(grid) and not indices:raise ValueError('Range contains no sampled coordinates')
    selected_indices=set(indices)
    if full_family:indices=list(range(len(grid)))
    channels={};family=[];tested=[]
    # Speller calibration alone is eligible, never mix online predictions into training labels.
    trials=[t for t in trials if session.get('protocol')!='speller' or t.get('speller',{}).get('phase')=='calibration']
    for ch in (CHANNELS if spectral else session.get('channels',CHANNELS)):
        groups=[]
        for ci in (first,second):
            if spectral:
                runs=[]
                for t in trials:
                    if t['condition_index']!=ci:continue
                    end=-float('inf');run=[]
                    for w in t.get('spectral_channels',{}).get(ch,{}).get('windows',[]):
                        if w['power'] is None or w['start']<end-1e-6:continue
                        power=np.asarray(w['power'],dtype=float)
                        if len(power)!=len(grid) or not np.isfinite(power).all() or np.any(power<0):continue
                        if run and w['start']>end+1e-6:runs.append(np.asarray(run));run=[]
                        run.append(10*np.log10(np.maximum(power,1e-12)));end=w['end']
                    if run:runs.append(np.asarray(run))
                groups.append(runs)
            else:
                waves=[]
                for t in trials:
                    r=t.get('channel_trials',{}).get(ch,{})
                    if t['condition_index']==ci and r.get('accepted'):
                        wave=np.asarray(r.get('wave',[]),dtype=float)
                        if len(wave)==len(grid) and np.isfinite(wave).all() and np.allclose(np.asarray(t['times'])*1000,grid):waves.append(wave)
                groups.append(waves)
        points=[]
        for k in indices:
            if spectral:
                a,b=([[float(row[k]) for row in run] for run in group] for group in groups)
                stat=compare_periods(a,b);values=[np.concatenate(g) if g else np.array([]) for g in (a,b)]
            else:
                values=[np.asarray([w[k] for w in group]) for group in groups]
                stat=compare(*values,minimum=3)
            means=[float(v.mean()) if len(v) else None for v in values]
            point=dict(x=float(grid[k]),n=[len(v) for v in values],means=means,difference=means[0]-means[1] if None not in means else None,ready=stat['ready'],reason=stat.get('reason'),p=stat.get('p'),adjusted_p=None,significant=False)
            points.append(point)
            # Include unavailable tests as p=1 to keep the requested family size fixed.
            family.append(stat['p'] if stat['ready'] else 1.);tested.append(point)
        channels[ch]=dict(points=points)
    for point,q in zip(tested,adjust_pvalues(family,correction)):
        if point['ready']:point.update(adjusted_p=q,significant=q<.05)
    if full_family:
        for channel in channels.values():channel['points']=[p for k,p in enumerate(channel['points']) if k in selected_indices]
    return dict(full_family=full_family,trial_count=len(trials),mode=mode,correction=correction,alpha=.05,conditions=[conditions[first],conditions[second]],channels=channels,family_size=len(family),ready_count=sum(p['ready'] for p in tested),range=[low,high],single=single,unit='Hz' if spectral else 'ms',method='Moving-block bootstrap of non-overlapping 2 s log PSD' if spectral else 'Two-sided Welch test across accepted trials',calibration=session.get('protocol')=='speller',scope=('Full recorded domain' if full_family else 'Selected points')+' × all recorded electrodes, for this condition pair. Unavailable tests count as p=1. Exploratory within-session inference; not corrected for repeated looks or other condition pairs.')


def time_frequency_statistics(trials, session, first=0, second=1, correction='holm'):
    """Separate block observations at each time-frequency cell; never window-count n."""
    first,second=int(first),int(second);conditions=session['conditions']
    if session.get('mode')!='tf':raise ValueError('Time-frequency maps require a spectral recording')
    if first==second or not all(0<=c<len(conditions) for c in (first,second)):raise ValueError('Choose two different conditions')
    frequencies=np.arange(2,40.01,.5)
    times=sorted({round((w['start']+w['end'])/2,4) for t in trials for r in t.get('spectral_channels',{}).values() for w in r.get('windows',[])})
    channels={};family=[];tested=[]
    for ch in CHANNELS:
        groups=[]
        for condition in (first,second):
            by_time={time:[] for time in times}
            for trial in trials:
                if trial['condition_index']!=condition:continue
                seen=set()
                for w in trial.get('spectral_channels',{}).get(ch,{}).get('windows',[]):
                    time=round((w['start']+w['end'])/2,4)
                    if w['power'] is None or time in seen:continue
                    power=np.asarray(w['power'],dtype=float)
                    if len(power)!=len(frequencies) or not np.isfinite(power).all() or np.any(power<0):continue
                    by_time[time].append(10*np.log10(np.maximum(power,1e-12)));seen.add(time)
            groups.append(by_time)
        points=[]
        for time in times:
            for k,freq in enumerate(frequencies):
                a,b=[np.asarray([p[k] for p in group[time]]) for group in groups]
                stat=compare(a,b,minimum=3);means=[float(v.mean()) if len(v) else None for v in (a,b)]
                point=dict(x=float(freq),time=time,n=[len(a),len(b)],means=means,difference=means[0]-means[1] if None not in means else None,ready=stat['ready'],reason=stat.get('reason'),p=stat.get('p'),adjusted_p=None,significant=False)
                points.append(point);tested.append(point);family.append(stat.get('p',1.))
        channels[ch]={'points':points}
    for p,q in zip(tested,adjust_pvalues(family,correction)):
        if p['ready']:p.update(adjusted_p=q,significant=q<.05)
    return dict(mode='tf-map',full_family=True,trial_count=len(trials),conditions=[conditions[first],conditions[second]],channels=channels,frequencies=frequencies.tolist(),times=times,correction=correction,alpha=.05,family_size=len(family),ready_count=sum(p['ready'] for p in tested),unit='Hz',method='Welch tests across separate blocks at each time–frequency cell; provisional',scope='All recorded time–frequency cells × four electrodes, for this pair. Minimum 3 blocks per condition at each cell. Repeated exploration and dependence between blocks are not corrected.')


def request_point_statistics(engine, path):
    """Shared native/HTTP route; only local saved trial arrays are read."""
    import copy
    from urllib.parse import urlsplit, parse_qs
    url=urlsplit(path);args=parse_qs(url.query)
    get=lambda key,default:args.get(key,[default])[0]
    view=engine.saved_view(url.path.rsplit('/',1)[1])
    with view.lock:
        view.analysis()
        trials=copy.deepcopy(view.trials);session=copy.deepcopy(view.session)
    if get('domain','points')=='map':
        return time_frequency_statistics(trials,session,get('first',0),get('second',1),get('correction','holm'))
    return point_statistics(trials,session,get('low',0),get('high',800),get('first',0),get('second',1),get('correction','holm'),get('single','false')=='true',get('full','true')=='true')
