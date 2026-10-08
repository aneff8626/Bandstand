"""Auditable NumPy-only online EEG analysis. Units: seconds and microvolts."""
import math
import numpy as np

FS = 256
CHANNELS = ['TP9', 'AF7', 'AF8', 'TP10']
DEFAULT_THRESHOLDS = dict(peak_to_peak=150., step=39., blink=100., flat_std=.5,
                          clip=995., muscle_rms=12., muscle_ratio=.45)

# Modestly more permissive ERP trial rejection; display and writing thresholds stay separate.
ERP_THRESHOLDS = {**DEFAULT_THRESHOLDS, 'peak_to_peak':180., 'step':47., 'blink':120.}

class Filters:
    """Causal notch Q=30, first-order HP .1Hz, second-order LP 30Hz."""
    def __init__(self, notch_only=False):
        self.z = np.zeros((3, 2, 4))
        self.ready = False
        w=2*np.pi*60/FS; alpha=np.sin(w)/(2*30)
        self.coefs=[(np.array([1,-2*np.cos(w),1])/(1+alpha), np.array([1,-2*np.cos(w)/(1+alpha),(1-alpha)/(1+alpha)]))]
        k=np.tan(np.pi*.1/FS)
        self.coefs.append((np.array([1,-1,0])/(1+k), np.array([1,(k-1)/(k+1),0])))
        k=np.tan(np.pi*30/FS); norm=1/(1+np.sqrt(2)*k+k*k)
        self.coefs.append((np.array([k*k,2*k*k,k*k])*norm,np.array([1,2*(k*k-1)*norm,(1-np.sqrt(2)*k+k*k)*norm])))
        if notch_only: self.coefs=self.coefs[:1]
    def process(self, x):
        x=np.asarray(x,float); output=np.empty_like(x)
        for i,row in enumerate(x):
            if not np.isfinite(row).all():
                output[i]=np.nan; self.z[:]=0; self.ready=False; continue
            if not self.ready:
                # Steady-state states avoid DC startup transients.
                v=row.copy()
                for j,(b,a) in enumerate(self.coefs):
                    gain=sum(b)/sum(a); y=v*gain
                    self.z[j,0]=y-b[0]*v; self.z[j,1]=b[2]*v-a[2]*y; v=y
                self.ready=True
            v=row.copy()
            for j,(b,a) in enumerate(self.coefs):
                y=b[0]*v+self.z[j,0]
                self.z[j,0]=b[1]*v-a[1]*y+self.z[j,1]
                self.z[j,1]=b[2]*v-a[2]*y; v=y
            output[i]=v
        return output

def artifacts(raw, times=None, thresholds=None, channels=None):
    th={**DEFAULT_THRESHOLDS, **(thresholds or {})}; a=np.asarray(raw,float)
    if len(a)<4: return ['data loss']
    selected=list(range(4)) if channels is None else channels
    x=a[:,selected]; reasons=[]
    if not np.isfinite(x).all() or (times is not None and np.any(np.diff(times)>1.75/FS)):
        return ['data loss / electrode stream missing']
    if np.max(np.abs(x))>=th['clip']: reasons.append('signal clipping')
    if np.any(np.std(x,axis=0)<th['flat_std']): reasons.append('flat signal / probable poor contact')
    if np.max(np.ptp(x,axis=0))>th['peak_to_peak'] or np.max(np.abs(np.diff(x,axis=0)))>th['step']:
        reasons.append('large EEG transient / possible contact noise')
    frontal=a[:,[i for i in selected if i in (1,2)]]
    if frontal.size and np.isfinite(frontal).all() and np.max(np.ptp(frontal,axis=0))>th['blink'] and np.max(np.abs(np.diff(frontal,axis=0)))>th['blink']/25:
        reasons.append('probable blink')
    freqs=np.fft.rfftfreq(len(x),1/FS)
    power=np.abs(np.fft.rfft((x-x.mean(0))*np.hanning(len(x))[:,None],axis=0))**2
    total=power[(freqs>=1)&(freqs<=45)].sum(0)
    high=power[(freqs>=25)&(freqs<=45)].sum(0)
    high_rms=np.sqrt(high*2/np.sum(np.hanning(len(x))**2)/len(x))
    if np.any((high/np.maximum(total,1e-12)>th['muscle_ratio']) & (high_rms>th['muscle_rms'])):
        reasons.append('probable muscle artifact')
    return reasons

def _betacf(a,b,x):
    qab=a+b; qap=a+1; qam=a-1; c=1.; d=1-qab*x/qap
    d=1/(d if abs(d)>1e-300 else 1e-300); h=d
    for m in range(1,250):
        aa=m*(b-m)*x/((qam+2*m)*(a+2*m))
        d=1+aa*d; d=d if abs(d)>1e-300 else 1e-300
        c=1+aa/c; c=c if abs(c)>1e-300 else 1e-300
        d=1/d; h*=d*c
        aa=-(a+m)*(qab+m)*x/((a+2*m)*(qap+2*m))
        d=1+aa*d; d=d if abs(d)>1e-300 else 1e-300
        c=1+aa/c; c=c if abs(c)>1e-300 else 1e-300
        d=1/d; delta=d*c; h*=delta
        if abs(delta-1)<3e-14: break
    return h

def ibeta(a,b,x):
    if x<=0: return 0.
    if x>=1: return 1.
    bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    return bt*_betacf(a,b,x)/a if x<(a+1)/(a+b+2) else 1-bt*_betacf(b,a,1-x)/b

def t_p(t,df): return ibeta(df/2,.5,df/(df+t*t))
def t_critical(df):
    lo,hi=0.,100.
    for _ in range(55):
        mid=(lo+hi)/2
        if t_p(mid,df)>.05: lo=mid
        else: hi=mid
    return (lo+hi)/2

def compare(a,b,minimum=10):
    a=np.asarray(a); b=np.asarray(b)
    if min(len(a),len(b))<minimum: return dict(ready=False, reason=f'At least {minimum} usable trials in each condition required')
    va=float(np.var(a,ddof=1)/len(a)); vb=float(np.var(b,ddof=1)/len(b))
    if va+vb<=1e-18: return dict(ready=False,reason='Insufficient variance for a t-test')
    t=float((a.mean()-b.mean())/np.sqrt(va+vb)); df=(va+vb)**2/(va*va/(len(a)-1)+vb*vb/(len(b)-1))
    p=t_p(t,df)
    return dict(ready=True,t=t,df=df,p=p,label='***' if p<.001 else '**' if p<.01 else '*' if p<.05 else 'NS',
                test='Two-sided Welch t-test; trial-level, within one participant; exploratory repeated looks')

def summarize(waves):
    a=np.asarray(waves)
    if not len(a): return None
    mean=a.mean(0); n=len(a)
    se=a.std(0,ddof=1)/np.sqrt(n) if n>1 else np.zeros_like(mean)
    return dict(n=n,mean=mean.tolist(),se=se.tolist(),ci95=(se*t_critical(n-1)).tolist() if n>=10 else None)

def spectrum(x):
    x=np.asarray(x); n=len(x); w=np.hanning(n)
    p=np.abs(np.fft.rfft((x-x.mean(0))*w[:,None],axis=0))**2/(FS*np.sum(w*w))
    p[1:-1]*=2
    return np.fft.rfftfreq(n,1/FS),p

def bandpower(x,band=(8,13)):
    f,p=spectrum(x); sel=(f>=band[0])&(f<=band[1])
    return np.sum(p[sel],axis=0)*(f[1]-f[0])

def time_frequency(x,times):
    # 1 second Hann windows, 125 ms hops. No baseline normalization hidden.
    n=FS; hop=32; rows=[]; centers=[]
    for start in range(0,len(x)-n+1,hop):
        f,p=spectrum(np.asarray(x[start:start+n])[:,None])
        rows.append(10*np.log10(np.maximum(p[(f>=2)&(f<=40),0],1e-12)))
        centers.append(float(times[start+n//2]))
    return dict(frequencies=list(range(2,41)),times=centers,power_db=np.asarray(rows).T.tolist(),units='dB re 1 microvolt squared / Hz')
