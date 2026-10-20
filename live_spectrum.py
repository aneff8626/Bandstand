"""Rolling, per-electrode Welch spectra for display only."""
import numpy as np

WINDOWS = (2, 4, 8, 16, 30)
BANDS = [('Delta', 1, 4), ('Theta', 4, 8), ('Alpha', 8, 13), ('Low beta', 13, 20), ('High beta', 20, 30), ('Gamma', 30, 40)]

def rolling_spectra(times, values, fs=256):
    t, x = np.asarray(times), np.asarray(values, dtype=float)
    if len(t) < 2*fs or x.ndim != 2:
        return {}
    result = {}
    for seconds in WINDOWS:
        take = t >= t[-1] - seconds + .5/fs
        tt, xx = t[take], x[take]
        channels = []
        for ch in range(x.shape[1]):
            segments = []
            for start in range(0, len(xx)-2*fs+1, fs):
                segment = xx[start:start+2*fs, ch]
                ts = tt[start:start+2*fs]
                if not np.isfinite(segment).all() or np.any(np.diff(ts) > 1.5/fs):
                    continue
                window = np.hanning(2*fs+1)[:-1]
                f = np.fft.rfftfreq(2*fs, 1/fs)
                power = np.abs(np.fft.rfft((segment-segment.mean())*window))**2 / (fs*np.sum(window**2))
                power[1:-1] *= 2
                segments.append(power)
            if not segments:
                channels.append(None)
                continue
            power = np.mean(segments, axis=0)
            keep = (f >= 1) & (f <= 40)
            channels.append(dict(psd=power[keep].tolist(), bands=[float(np.sum(power[(f>=lo)&(f<hi)])*(f[1]-f[0])) for _,lo,hi in BANDS], segments=len(segments)))
        result[str(seconds)] = dict(frequencies=np.arange(1,40.5,.5).tolist(), channels=channels, duration=min(seconds,float(t[-1]-tt[0]+1/fs)))
    return result
