"""Provisional display annotations; no EOG-ground-truth validation.
Ocular features use frontal polarity and pulse/step shape. Vertical eye movements
remain ambiguous. Time bounds describe detected excursions, not physical onset.
"""
import numpy as np
from analysis import FS, CHANNELS, DEFAULT_THRESHOLDS, artifacts

def ocular_event(raw, times, thresholds=None):
    th={**DEFAULT_THRESHOLDS, **(thresholds or {})}
    x=np.asarray(raw,float); t=np.asarray(times)
    f=x[:,1:3]
    if len(f)<32 or not np.isfinite(f).all() or np.any(np.abs(f)>=th['clip']): return None
    # Smooth ~35 ms to avoid interpreting high-frequency noise as eye rotation.
    f=np.stack([np.convolve(f[:,i],np.ones(9)/9,'valid') for i in range(2)],axis=1)
    t=t[4:-4]; f-=np.median(f[:8],axis=0)
    amplitudes=np.max(np.abs(f),axis=0)
    if np.min(amplitudes)<th['blink']*.5 or np.max(amplitudes)<th['blink']: return None
    corr=float(np.corrcoef(f.T)[0,1]) if np.min(np.std(f,axis=0))>1 else 0
    common=np.mean(f,axis=1); differential=(f[:,0]-f[:,1])/2
    peak=int(np.argmax(np.abs(common)))
    recovered=np.max(np.abs(np.median(f[-8:],axis=0)))<np.max(amplitudes)*.3
    if corr>.75 and recovered and 8<peak<len(f)-8:
        label='probable blink'; channels=CHANNELS[:]; measure=np.abs(common)
    elif corr<-.7 and abs(np.median(differential[-8:]))>np.max(amplitudes)*.4:
        label='possible horizontal saccade'; channels=['AF7','AF8']; measure=np.abs(differential)
    else:
        label='possible eye movement (blink / vertical saccade unresolved)'; channels=['AF7','AF8']; measure=np.max(np.abs(f),axis=1)
    idx=np.flatnonzero(measure>max(th['blink']*.3,np.max(measure)*.25))
    if not len(idx): return None
    return dict(label=label,channels=channels,kind='ocular',onset=float(t[idx[0]]),offset=float(t[idx[-1]]))

def detect_events(raw,times,thresholds=None,profile=None,motion=None):
    th={**DEFAULT_THRESHOLDS,**(thresholds or {})}; x=np.asarray(raw,float); t=np.asarray(times)
    if len(x)<32:return []
    channel_reasons=[artifacts(x,t,th,[i]) for i in range(4)]
    frontal_unreliable=any(any(r.startswith(('probable muscle','signal clipping','flat signal','data loss')) for r in channel_reasons[i]) for i in (1,2))
    eye=None if frontal_unreliable else ocular_event(x,t,th)
    events=[eye] if eye else []
    if profile is not None:
        from calibrated_artifacts import classify
        events=classify(x,t,profile,motion); eye=None
    for i,ch in enumerate(CHANNELS):
        reasons=[r for r in channel_reasons[i] if r!='probable blink']
        if eye and ch in eye['channels']: reasons=[r for r in reasons if not r.startswith('large EEG')]
        if profile is not None and any(ch in e['channels'] for e in events):
            reasons=[r for r in reasons if r.startswith(('data loss','signal clipping','flat signal'))]
        if not reasons:continue
        severe=[r for r in reasons if r.startswith(('data loss','signal clipping','flat signal'))]
        label=severe[0] if severe else 'probable muscle artifact' if 'probable muscle artifact' in reasons else 'channel noise'
        v=x[:,i]
        if label=='signal clipping': mask=np.abs(v)>=th['clip']
        elif label=='channel noise':
            baseline=np.nanmedian(v[:8]); mask=(np.abs(v-baseline)>th['peak_to_peak']*.5)
            mask[1:]|=np.abs(np.diff(v))>th['step']
        else:mask=np.ones(len(v),dtype=bool)
        idx=np.flatnonzero(mask)
        if not len(idx):idx=np.arange(len(v))
        events.append(dict(label=('Contact / electrode noise' if label=='channel noise' else 'Muscle tension' if label=='probable muscle artifact' else label),channels=[ch],kind='noise',onset=float(t[idx[0]]),offset=float(t[idx[-1]]),uncertain=not label.startswith(('signal clipping','data loss'))))
    return events
