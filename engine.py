from private_storage import DATA_ROOT
import csv, io, json, math, os, random, subprocess, threading, time, uuid, zipfile
from pathlib import Path
from collections import deque, Counter
import numpy as np
from tf_analysis import channel_windows,summarize_tf
from analysis import FS, CHANNELS, DEFAULT_THRESHOLDS, ERP_THRESHOLDS, Filters, artifacts, compare, summarize, bandpower, time_frequency, behavior_summary
from protocols import PROTOCOLS, SOURCES

ROOT=Path(__file__).resolve().parent

def clean(v):
    if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)): return [clean(x) for x in v]
    if isinstance(v,(float,np.floating)): return float(v) if math.isfinite(v) else None
    if isinstance(v,np.integer): return int(v)
    return v

def dumps(v): return json.dumps(clean(v),allow_nan=False)


# Labelled simulation only. Each protocol gets its textbook direction at plausible Muse sites (TP9, AF7, AF8,
# TP10), so demos teach the expected pattern. Nothing is injected for biofeedback or self-disclosure, so the
# simulator never manufactures a training or disclosure effect.
SIM_ERP={  # protocol: (latency s, width s, {condition index: µV per channel})
 'oddball':(.38,.075,{0:(1,.5,.5,1),1:(6,3,3,6)}),
 'auditory':(.33,.08,{0:(1,1.5,1.5,1),1:(4,5,5,4)}),
 'faces':(.17,.03,{0:(-6,-1,-1,-6),1:(-2,-.5,-.5,-2)}),
 'expertise':(.17,.03,{0:(-5,-1,-1,-5),1:(-3,-.5,-.5,-3)}),
 'flanker':(.28,.05,{0:(-.5,-2,-2,-.5),1:(-1,-5,-5,-1)}),
 'reward':(.3,.05,{0:(0,0,0,0),1:(0,5,5,0)}),
}
SIM_TF={'alpha':(10,(8,4,4,8)),'theta':(6,(1,4,4,1)),'custom':(10,(4,4,4,4))}  # added only in the second condition
SIM_NOTES={
 'oddball':'a positive peak near 380 ms, larger for targets and largest at TP9/TP10.',
 'auditory':'a frontal negative peak near 100 ms for every tone and a positive peak near 330 ms that is larger for targets.',
 'faces':'a negative peak near 170 ms at TP9/TP10 that is larger for faces than cars.',
 'expertise':'a negative peak near 170 ms at TP9/TP10 that is larger for the more familiar category.',
 'flanker':'a frontal negative peak near 280 ms that is larger for incongruent arrows.',
 'reward':'a frontal positive peak near 300 ms after wins only (AF7/AF8, so it survives the TP9/TP10 re-reference).',
 'alpha':'extra 10 Hz alpha during eyes-closed blocks on every electrode, strongest at TP9/TP10.',
 'theta':'extra 6 Hz theta at AF7/AF8 during arithmetic blocks.',
 'custom':'extra 10 Hz alpha during the second condition.',
 'disclosure':'no effect; any difference is noise.',
 'biofeedback':'no effect; any pre/post difference is noise, not training.',
}

def image_sequence(pool,n,rng):
    """n images for one condition: every image once per shuffled pass, never the same image twice in a row
    (also across pass boundaries), so repetition does not differ between images or conditions."""
    out=[]
    while len(out)<n:
        deck=list(pool);rng.shuffle(deck)
        if out and len(deck)>1 and deck[0] is out[-1]:deck[0],deck[1]=deck[1],deck[0]
        out.extend(deck)
    return out[:n]

class PacketAssembler:
    def __init__(self,callback):
        self.callback=callback; self.pending={}; self.last=None; self.last_t=None; self.missing=0
    def add(self,p):
        counter=p['counter']; arrival=p['received']
        if self.last is not None and ((counter-self.last)&65535)>32768: return
        row=self.pending.setdefault(counter,{'arrival':arrival,'channels':{}})
        row['arrival']=min(row['arrival'],arrival); row['channels'][p['channel']]=p['values']
        # Order by arrival/counter; incomplete bundles become explicit NaNs after 200ms.
        for c,r in list(self.pending.items()):
            if len(r['channels'])==4 or arrival-r['arrival']>.20:
                if self.last is not None:
                    delta=(c-self.last)&65535
                    if delta==0 or delta>32768:
                        del self.pending[c]; continue
                    self.missing+=max(0,delta-1)*12
                else: delta=1
                target=r['arrival']-11/FS
                if self.last_t is None: start=target
                else:
                    predicted=self.last_t+(delta*12-11)/FS
                    # Slowly track oscillator drift; retain gaps. Unknown BLE delay remains uncalibrated.
                    start=predicted+float(np.clip((target-predicted)*.002,-.0001,.0001))
                values=np.asarray([r['channels'].get(ch,[np.nan]*12) for ch in CHANNELS]).T
                ts=start+np.arange(12)/FS
                self.callback(ts,values); self.last=c; self.last_t=ts[-1]; del self.pending[c]

class Engine:
    def __init__(self):
        from personal import PersonalActivities
        self.personal=PersonalActivities(DATA_ROOT)
        self.lock=threading.RLock(); self.raw=deque(maxlen=FS*90); self.filtered=deque(maxlen=FS*90); self.times=deque(maxlen=FS*90)
        self.filters=Filters(); self.notch=Filters(notch_only=True); self.spectral=deque(maxlen=FS*90); self.source='live'; self.status={'state':'starting','message':'Checking existing Bluetooth authorization'}
        self.session=None; self.events=[]; self.trials=[]; self.pending=[]; self.notifications=deque(maxlen=20)
        self.motion_samples={k:deque(maxlen=52*8) for k in ('acc','gyro')}; self.last_quality=0; self.quality=[]; self.band=None; self.signal_count=0; self.bridge=None; self.bridge_enabled=threading.Event(); self.bridge_enabled.set()
        self.assembler=PacketAssembler(self.ingest); self.last_notify=0; self.demo_time=None; self.rng=np.random.default_rng(472)
        self.cache_revision=None; self.cache_analysis={}; self.revision=0
        self.artifact_regions=deque(maxlen=200); self.open_artifact_regions={}; self.artifact_region_time=None
        self.annotation_log_state={}; self.annotation_next_id=1
        (DATA_ROOT).mkdir(exist_ok=True)
        from developer_capture import DeveloperCapture
        self.developer=DeveloperCapture(ROOT, data_dir=DATA_ROOT)
        from typing_lab import TypingLab
        self.typing=TypingLab(ROOT, data_dir=DATA_ROOT)
        profile_path=DATA_ROOT/'artifact_profile.json'
        self.artifact_profile=json.loads(profile_path.read_text()) if profile_path.exists() else None
    def start(self):
        if os.environ.get("MUSE_NATIVE_BLUETOOTH") != "1":
            threading.Thread(target=self.bridge_loop,daemon=True).start()
        threading.Thread(target=self.simulation_loop,daemon=True).start()
    def bluetooth_connection(self,connected):
        with self.lock:
            if not connected and ((self.session and self.session.get('running')) or self.typing.running or self.developer.status().get('recording') or getattr(getattr(self,'personal',None),'current',None)):
                raise ValueError('Stop and save the recording before disconnecting.')
            if connected:
                self.bridge_enabled.set()
                self.status={'state':'scanning','message':'Searching for your headset.'}
            else:
                self.bridge_enabled.clear()
                if self.bridge and self.bridge.poll() is None:self.bridge.terminate()
                self.status={'state':'disconnected','message':'Disconnected. Click Connect Bluetooth to reconnect.'}
                self.live_status=self.status.copy()
            return {'connected':connected}
    def bridge_loop(self):
        while True:
            self.bridge_enabled.wait()
            try:
                path=ROOT/'build/muse-bridge'
                if not path.exists():
                    self.status={'state':'bridge_missing','message':'Native bridge has not been built. Run Launch Muse Lab.command.'}; time.sleep(15); continue
                with self.lock:
                    if not self.bridge_enabled.is_set():continue
                    self.bridge=subprocess.Popen([str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                for line in self.bridge.stdout:
                    try:
                        p=json.loads(line)
                        with self.lock:
                            if not self.bridge_enabled.is_set():continue
                            if p.get('type')=='status':
                                if p.get('state')=='connecting' and self.source=='live':
                                    self.typing.stop('Headset reconnected')
                                    if self.session and self.session['running']: self.stop('headset reconnected; start a new session')
                                    self.assembler=PacketAssembler(self.ingest); self.filters=Filters(); self.notch=Filters(notch_only=True)
                                    self.times.clear(); self.raw.clear(); self.filtered.clear(); self.spectral.clear()
                                self.live_status=p
                                if self.source=='live': self.status=p
                            elif p.get('type')=='packet' and self.source=='live': self.assembler.add(p)
                    except (ValueError,KeyError) as e: self.status={'state':'decode_error','message':str(e)}
                self.bridge.wait()
            except OSError as e: self.status={'state':'bridge_error','message':str(e)}
            time.sleep(15)
    def simulation_loop(self):
        while True:
            time.sleep(.046875)
            with self.lock:
                if self.source!='simulation': self.demo_time=None; continue
                now=time.time()
                if self.demo_time is None or now-self.demo_time>2: self.demo_time=now-12/FS
                n=max(1,int((now-self.demo_time)*FS))
                ts=self.demo_time+np.arange(1,n+1)/FS; self.demo_time=ts[-1]
                # Background alpha drifts slowly in strength, so block-to-block variance resembles real recordings.
                x=self.rng.normal(0,4,(n,4))+8*(1+.35*np.sin(2*np.pi*ts[:,None]/37+np.arange(4)))*np.sin(2*np.pi*10*ts[:,None]+np.arange(4))
                # Synthetic effects are deliberately present only in labeled simulation.
                protocol=self.session['protocol'] if self.session else None
                for event in self.events[-8:]:
                    if event.get('kind')!='stimulus': continue
                    d=ts-event['onset']; c=event['condition_index']
                    if protocol in SIM_ERP:
                        latency,width,amplitude=SIM_ERP[protocol]
                        x+=np.exp(-((d[:,None]-latency)/width)**2)*np.asarray(amplitude[c])
                        if protocol=='auditory': x+=np.exp(-((d[:,None]-.1)/.025)**2)*np.asarray((-1,-3,-3,-1))
                    elif protocol in SIM_TF and c==1:
                        # In phase with the background rhythm, for the whole block, on every channel.
                        frequency,amplitude=SIM_TF[protocol]; inside=(d>=0)&(d<self.session['stim_ms'][1]/1000)
                        gain=.6+.8*((event["index"]*.618034)%1)  # each block its own effect size
                        if np.any(inside): x[inside]+=gain*np.sin(2*np.pi*frequency*ts[inside,None]+np.arange(4))*np.asarray(amplitude)
                self.ingest(ts,x)
    def switch_source(self,source):
        if source not in ['live','simulation']: raise ValueError('Unknown data source')
        with self.lock:
            if self.personal.current:raise ValueError('Stop the personal activity before changing source.')
            if self.typing.running: raise ValueError('Stop typing recording before changing source.')
            if self.developer.current: raise ValueError('Finish developer calibration before changing source.')
            if self.session and self.session['running']: raise ValueError('End the current session before changing source')
            self.source=source; self.artifact_regions.clear(); self.open_artifact_regions.clear(); self.artifact_region_time=None; [v.clear() for v in self.motion_samples.values()]; self.times.clear(); self.raw.clear(); self.filtered.clear(); self.filters=Filters(); self.notch=Filters(notch_only=True); self.spectral.clear(); self.quality=[]; self.band=None
            self.assembler=PacketAssembler(self.ingest)
            self.status={'state':'simulation','message':'SIMULATED EEG • No headset data'} if source=='simulation' else getattr(self,'live_status',{'state':'waiting','message':'Waiting for Muse'})
    def ingest(self,ts,values):
        with self.lock:
            self.personal.record_raw(ts,values)
            filtered=self.filters.process(values); self.developer.add(ts,values,filtered); notched=self.notch.process(values); self.spectral.extend(notched.tolist())
            self.typing.ingest(ts,values,filtered)
            self.times.extend(ts.tolist()); self.raw.extend(values.tolist()); self.filtered.extend(filtered.tolist()); self.signal_count+=len(ts)
            if self.session and self.session['running']:
                for t,r,f in zip(ts,values,filtered): self.writer.writerow([t,*r,*f,self.source])
                self.raw_file.flush()
            if time.time()-self.last_quality>1 and len(self.raw)>=FS*2:
                a=np.array(list(self.raw)[-FS*2:]); t=np.array(list(self.times)[-FS*2:]); self.quality=[]
                th=self.session['thresholds'] if self.session else DEFAULT_THRESHOLDS
                for i,ch in enumerate(CHANNELS):
                    reasons=artifacts(a,t,th,[i]); self.quality.append({'channel':ch,'state':'review' if reasons else 'good','reasons':reasons,'rms':float(np.nanstd(a[:,i]))})
                selected=self.session['channels'] if self.session else ['TP9','TP10']; idx=[CHANNELS.index(c) for c in selected]
                reasons=artifacts(a,t,th,idx)
                if reasons and time.time()-self.last_notify>3:
                    self.notifications.append({'id':time.time(),'text':'; '.join(reasons)}); self.last_notify=time.time()
                chosen=self.session.get('band',[8,13]) if self.session else [8,13]
                bp=bandpower(np.asarray(list(self.spectral)[-FS*2:])[:,idx],chosen) if not reasons else None
                self.band={'value':float(np.mean(bp)) if bp is not None else None,'band':chosen,'valid':not reasons,'reasons':reasons}
                if self.session and self.session['running']:
                    self.bio_writer.writerow([time.time(),self.session.get('phase','recording'),self.band['value'],self.band['valid'],'; '.join(reasons)])
                    self.bio_file.flush()
                self.last_quality=time.time()
            if self.personal.current and self.times[-1]-self.personal.last_sample>=2:self.personal.ingest(list(self.times),list(self.raw),list(self.spectral))
            self.process_pending()
            if self.typing.running and self.typing.pending and self.times[-1]>=self.typing.next_due():self.typing.process(list(self.times),list(self.raw),list(self.filtered))
            if self.typing.running and time.time()-self.typing.last_live_prediction>=1:self.typing.live_predict(list(self.times),list(self.raw),list(self.filtered))
    def typing_request(self,path,body):
        with self.lock:
            if path=='typing/start' and self.personal.current:raise ValueError('Finish the personal activity first')
            if path=='typing/update_test':
                self.typing.maybe_fit(force=True)
                return self.typing.status()
            if path=='typing/document':
                files=sorted(self.typing.root.glob('*/document.txt'))
                return {'text':files[-1].read_text() if files else ''}
            if path=='typing/start':
                if self.source!='live' or not self.times or time.time()-self.times[-1]>1:raise ValueError('Connect the live headset first.')
                if self.developer.current or (self.session and self.session['running']):raise ValueError('Finish the current recording first.')
                result=self.typing.start(body.get('window','context'),int(body.get('history',30)),int(body.get('delay',0)),body.get('capture','editor'))
                self.typing.ingest(list(self.times)[-FS*60:],list(self.raw)[-FS*60:],list(self.filtered)[-FS*60:])
                return result
            if path=='typing/export':
                if not self.typing.session:raise ValueError('Record a typing session first.')
                if self.typing.running:raise ValueError('Stop typing before exporting.')
                directory=self.typing.directory;dest=DATA_ROOT/'exports'/('typing-'+self.typing.session['id']+'.zip');dest.parent.mkdir(exist_ok=True)
                with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
                    for p in directory.iterdir():
                        if p.is_file():z.write(p,p.name)
                return {'file':str(dest),'message':'Saved to '+str(dest)}
            if path=='typing/native_event':return self.typing.native_event(body,list(self.times),list(self.raw),list(self.filtered))
            if path=='typing/event':return self.typing.event(body,list(self.times),list(self.raw),list(self.filtered))
            if path=='typing/stop':return self.typing.stop(body.get('reason','Stopped by writer'))
            raise ValueError('Unknown typing request')
    def manifest(self):
        path=DATA_ROOT/'stimuli/manifest.json'
        if not path.exists():path=ROOT/'stimuli/manifest.json'
        return json.loads(path.read_text()) if path.exists() else []
    def catalog(self):
        assets=self.manifest(); result=[]
        for p in PROTOCOLS:
            p=dict(p); p['assets']=Counter(a['category'] for a in assets)
            result.append(p)
        return {'protocols':result,'sources':SOURCES,'thresholds':DEFAULT_THRESHOLDS,'erp_thresholds':ERP_THRESHOLDS,'channels':CHANNELS,'assets':assets,'simulation_effects':SIM_NOTES}
    def begin(self,cfg):
        with self.lock:
            if self.typing.running: raise ValueError('Stop typing recording first.')
            if self.developer.current: raise ValueError('Finish developer calibration first.')
            if self.session and self.session['running']: raise ValueError('A session is already running')
            protocol=next((p for p in PROTOCOLS if p['id']==cfg.get('protocol')),None)
            if not protocol: raise ValueError('Choose a known protocol')
            if not self.times or time.time()-self.times[-1]>2: raise ValueError('No recent EEG. Connect Muse or explicitly select simulation.')
            p=dict(protocol)
            if cfg.get('custom_title'):
                p['title']=str(cfg['custom_title']).strip()[:100] or p['title']
            custom=None
            if p['id'] in ('custom','custom_erp'):
                from custom_experiments import validate_design
                custom=validate_design(cfg,p['mode'])
                p.update(conditions=custom['conditions'],stim_ms=[custom['duration_ms']]*2,isi_ms=[custom['interval_ms']]*2)
                cfg={**cfg,'trials':len(custom['conditions'])*custom['repetitions']}
                if p['mode']=='tf':cfg.setdefault('window',[2.,custom['duration_ms']/1000])
            selected=cfg.get('channels',p['channels'])
            if not selected or not set(selected)<=set(CHANNELS): raise ValueError('Select at least one valid electrode')
            thresholds={**(ERP_THRESHOLDS if p['mode']=='erp' else DEFAULT_THRESHOLDS),**cfg.get('thresholds',{})}
            if set(thresholds)!=set(DEFAULT_THRESHOLDS) or any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0 for v in thresholds.values()): raise ValueError('Artifact thresholds must be finite positive numbers')
            if self.personal.current:raise ValueError('Finish the personal activity first')
            count=int(cfg.get('trials',p['trials'])); minimum=int(cfg.get('minimum',10))
            if p['id']=='disclosure':count=4
            # Biofeedback measures six 8 s rest blocks before and six after training; its comparison needs 5 per phase.
            if p['id']=='biofeedback':count=12;minimum=min(minimum,5)
            if custom:valid=2<=count<=1000 and 10<=minimum<=500
            elif p['id']=='biofeedback':valid=5<=minimum<=6
            else:valid=(count==4 if p['id']=='disclosure' else 20<=count<=(2400 if p['id']=='speller' else 1000)) and 10<=minimum<=500
            if not valid: raise ValueError('Trial count must be 20–1000; minimum usable trials 10–500')
            window=list(map(float,cfg.get('window',p['window'])))
            if len(window)!=2 or not 0<=window[0]<window[1]<= (p['stim_ms'][1]/1000 if p['mode']!='erp' else .8): raise ValueError('Invalid analysis window')
            band=list(map(float,cfg.get('band',p.get('band',[8,13]))))
            if len(band)!=2 or not 2<=band[0]<band[1]<=40: raise ValueError('Band must be within 2–40 Hz')
            gain=(cfg.get('calibration') or {}).get('audio_gain') if isinstance(cfg.get('calibration') or {},dict) else None
            # The page always sends the gain it will play; refuse any unsafe value (absent: no audio settings recorded).
            if p['id'] in ('auditory','alpha','custom_erp') and gain is not None and not (type(gain) in (int,float) and 0<gain<=.2): raise ValueError('Audio gain must be above 0 and at most 0.2.')
            conditions=p['conditions']; assets=self.manifest(); pools=None
            if p['id'] in ['faces','expertise']:
                categories=['faces','cars'] if p['id']=='faces' else cfg.get('expertise',[])
                if len(categories)!=2 or categories[0]==categories[1]: raise ValueError('Choose two different expertise categories')
                pools=[[a for a in assets if a['category']==cat] for cat in categories]
                if any(len(pool)<20 for pool in pools): raise ValueError('Import at least 20 distinct documented images per category first')
                # Keep the protocol's roles in every label, export and report.
                conditions=['Faces','Cars'] if p['id']=='faces' else [f'{p["conditions"][0]}: {categories[0]}',f'{p["conditions"][1]}: {categories[1]}']
            a=np.array(list(self.raw)[-FS*2:]); times=np.array(list(self.times)[-FS*2:])
            reasons=artifacts(a,times,thresholds,[CHANNELS.index(c) for c in selected])
            if reasons and cfg.get('allow_noisy_start') is not True: raise ValueError('Improve contact before recording: '+', '.join(reasons))
            if len(self.times)<FS*3: raise ValueError('Wait for three seconds of stable EEG')
            seed=random.SystemRandom().randint(1,2**31-1); rng=random.Random(seed)
            labels=[1]*round(count*p['probability'])+[0]*(count-round(count*p['probability'])); rng.shuffle(labels)
            if p['id']=='disclosure':labels=[seed%2,1-seed%2,1-seed%2,seed%2]
            if p['id']=='alpha':labels= [(i+seed%2)%2 for i in range(count)]
            if p['id']=='biofeedback':labels=[0]*6+[1]*6
            if custom:
                from custom_experiments import condition_order
                labels=condition_order(custom,rng)
            plan=[];decks=[image_sequence(pool,labels.count(c),rng) for c,pool in enumerate(pools)] if pools else None
            for i,c in enumerate(labels):
                item=dict(index=i,condition_index=c,condition=conditions[c],duration=rng.randint(*p['stim_ms']),isi=rng.randint(*p['isi_ms']),direction=rng.choice(['left','right']),number=rng.randint(600,999))
                if custom:
                    item['instruction']=custom['instructions'][c]
                    if p['mode']=='erp' and custom['media'][c]:item['asset']=custom['media'][c][sum(x['condition_index']==c for x in plan)%len(custom['media'][c])]
                if pools: item['asset']=decks[c].pop(0)['file']
                # Reward outcomes follow the participant's choice; a pre-drawn label would contradict them.
                if p['id']=='reward': item.update(condition_index=None,condition='set by choice outcome')
                plan.append(item)
            session_id=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
            directory=DATA_ROOT/session_id; directory.mkdir()
            calibration=cfg.get('calibration',{})
            if hasattr(self,'review_band'):del self.review_band
            self.session={**p,'id':session_id,'protocol':p['id'],'source':self.source,'channels':selected,'conditions':conditions,'trials_planned':count,'minimum':minimum,'window':window,'band':band,'thresholds':thresholds,'seed':seed,'plan':plan,'running':True,'started':time.time(),'phase':'recording','calibration':calibration,'metric':cfg.get('metric','amplitude'),'training_seconds':max(30,min(1800,int(cfg.get('training_seconds',120)))),'timing':'Browser frame / Web Audio software timestamps aligned by clock ping; BLE receive-anchored sample clock. Physical display/audio/BLE latencies uncalibrated.','analysis':{'erp':'Causal .1 Hz high-pass, 30 Hz low-pass, 60 Hz notch Q30. ERP pre-stimulus baseline -200..0 ms. Trial-level statistics, repeated looks; no population inference.','tf':'60 Hz notch; channel-local 2 s Hann windows every 0.5 s with DC removal. At least 4 clean seconds per block/channel; comparisons use block log band power. Exploratory statistics within one participant; no population inference.','bio':'Rest blocks: whole-block band power after artifact screening (linear µV²). Feedback: overlapping 2 s windows, descriptive only. Pre/post changes are observational.'}[p['mode']]}
            if custom:self.session['custom_design']=custom
            if self.session['metric'] not in ['amplitude','latency']: raise ValueError('Unknown measurement')
            if p['id']=='disclosure':self.session['analysis']+=' Public self-disclosure exception: condition comparisons use non-overlapping 2-second clips as observations. Clips within blocks are correlated; p-values may overstate evidence. Answer text is not saved by this task.'
            self.session['preflight_quality']={'warnings':reasons,'continued_anyway':cfg.get('allow_noisy_start') is True}
            self.session['electrode_warning']=selected!=p['channels']
            self.events=[]; self.trials=[]; self.pending=[]; self.revision+=1
            self.speller_model=None
            self.raw_file=open(directory/'continuous.csv','w',newline=''); self.writer=csv.writer(self.raw_file)
            self.writer.writerow(['timestamp_unix_s',*['raw_'+c+'_uV' for c in CHANNELS],*['filtered_'+c+'_uV' for c in CHANNELS],'source'])
            self.bio_file=open(directory/'bandpower.csv','w',newline=''); self.bio_writer=csv.writer(self.bio_file); self.bio_writer.writerow(['timestamp','phase','power_uV2','valid','reasons'])
            # Preserve pre-roll so the first baseline is exportable.
            for t,r,f in zip(list(self.times)[-FS*3:],list(self.raw)[-FS*3:],list(self.filtered)[-FS*3:]): self.writer.writerow([t,*r,*f,self.source])
            self.save_metadata(); return self.session
    def save_metadata(self):
        if self.session:
            d=DATA_ROOT/self.session['id']; (d/'session.json').write_text(dumps(self.session)); (d/'events.json').write_text(dumps(self.events))
    def event(self,e):
        with self.lock:
            if not self.session or not self.session['running']: raise ValueError('No active session')
            kind=e.get('kind'); allowed=['stimulus','offset','response','phase','behavior','timing_issue','note']
            if kind not in allowed: raise ValueError('Unknown event kind')
            onset=float(e.get('onset',time.time()))
            if not math.isfinite(onset) or abs(onset-time.time())>10: raise ValueError('Clock mismatch; synchronize browser clock')
            event={**e,'onset':onset,'received':time.time(),'source':self.source}
            if kind=='stimulus':
                i=int(e['index']); c=int(e['condition_index'])
                if i<0 or i>=self.session['trials_planned'] or c not in range(len(self.session.get('conditions',[0,1]))): raise ValueError('Invalid trial index/condition')
                if any(p.get('kind')=='stimulus' and p.get('index')==i for p in self.events): raise ValueError('Duplicate trial marker')
                if self.session['protocol']=='speller':
                    meta=e.get('speller',{})
                    if type(meta.get('group')) is not int or not 0<=meta['group']<16 or type(meta.get('line')) is not int or not 0<=meta['line']<12:raise ValueError('Invalid speller flash')
                    if meta.get('phase')=='calibration':
                        target=meta.get('target')
                        if type(target) is not int or not 0<=target<36 or c!=int(meta['line'] in (target//6,6+target%6)):raise ValueError('Invalid calibration target')
                    elif meta.get('phase')!='spelling' or meta.get('target') is not None or c!=0:raise ValueError('Spelling must not provide a target label')
                event['condition']=self.session['conditions'][c]; self.pending.append(event)
            if kind=='phase': self.session['phase']=str(e.get('phase',''))[:100]
            self.events.append(event)
            with open(DATA_ROOT/self.session['id']/'events.jsonl','a') as f: f.write(dumps(event)+'\n')
            self.save_metadata(); return event
    def process_pending(self,force=False):
        if not self.session or not self.pending or not self.times: return
        s=self.session
        # Blocks report their planned length as planned_duration_ms; the protocol default is only a fallback.
        def epoch_end(event):return .8 if s['mode']=='erp' else (event.get('duration') or event.get('planned_duration_ms') or s.get('stim_ms',[8000,8000])[1])/1000
        # Converting the whole 90 s buffer is costly; skip it on packets where no epoch is complete yet.
        if not force and self.times[-1]<min(e['onset']+epoch_end(e)+.03 for e in self.pending): return
        tt=np.asarray(self.times); raw=np.asarray(self.raw); filt=np.asarray(self.filtered); spectral=np.asarray(self.spectral)
        for event in self.pending[:]:
            pre=.2 if s['mode']=='erp' else 2.; end=epoch_end(event)
            if not force and tt[-1]<event['onset']+end+.03: continue
            t=tt-event['onset']; use=(t>=-pre)&(t<=end); rt=t[use]; x=raw[use]; y=filt[use]; sx=spectral[use]
            if s['mode']=='tf':
                spectral_channels=channel_windows(x,sx,rt,s['window'],s['thresholds'])
                trial=dict(index=event['index'],condition=event['condition'],condition_index=event['condition_index'],onset=event['onset'],accepted=any(v['accepted'] for v in spectral_channels.values()),reasons=[],feature=None,wave=None,times=[],tf=None,spectral_channels=spectral_channels)
                self.trials.append(trial);self.pending.remove(event);self.revision+=1
                d=DATA_ROOT/s['id'];np.savez_compressed(d/f"trial-{event['index']:04d}.npz",times=rt,raw=x,filtered=y,notched=sx)
                (d/'trials.json').write_text(dumps(self.trials));continue
            idx=[CHANNELS.index(c) for c in s['channels']]
            reasons=[]
            expected=int((pre+end)*FS)
            if len(rt)<expected-3 or not len(rt) or rt[0]>-pre+2/FS or rt[-1]<end-2/FS: reasons.append('incomplete epoch / data loss')
            # Conservatively reject artifacts anywhere in the exported epoch, including baseline.
            global_reasons=list(reasons)
            reasons+=artifacts(x,rt,s['thresholds'],idx)
            if s['protocol']=='reward': reasons+=artifacts(x,rt,s['thresholds'],[0,3])
            if event.get('clock_rtt_ms',0)>30: reasons.append('uncertain event timing')
            if any(e.get('kind')=='timing_issue' and -pre<=e['onset']-event['onset']<=end for e in self.events): reasons.append('presentation timing interrupted')
            grid=np.arange(-round(pre*FS),round(end*FS)+1)/FS
            channel_trials={}
            if s['mode']=='erp':
                timing=[r for r in reasons if r in ['uncertain event timing','presentation timing interrupted']]
                reference_reasons=artifacts(x,rt,s['thresholds'],[0,3]) if s['protocol']=='reward' else []
                channel_y=y-y[:,[0,3]].mean(1)[:,None] if s['protocol']=='reward' else y
                for i in idx:
                    cr=list(dict.fromkeys(global_reasons+timing+reference_reasons+artifacts(x,rt,s['thresholds'],[i])))
                    wave=None; value=None
                    if not cr:
                        wave=np.interp(grid,rt,channel_y[:,i]-channel_y[rt<0,i].mean())
                        mask=(grid>=s['window'][0])&(grid<=s['window'][1])
                        value=float(grid[mask][np.argmin(wave[mask]) if s['polarity']=='negative' else np.argmax(wave[mask])]*1000) if s['metric']=='latency' else float(wave[mask].mean())
                    channel_trials[CHANNELS[i]]=dict(accepted=not cr,reasons=cr,wave=wave.tolist() if wave is not None else None,feature=value)
            epoch=None; feature=None; tf=None
            if not reasons:
                if s['protocol']=='reward': y=y-y[:,[0,3]].mean(1)[:,None]
                baseline=y[rt<0].mean(0); y=y-baseline
                epoch=np.stack([np.interp(grid,rt,y[:,i]) for i in range(4)],axis=1)
                combined=epoch[:,idx].mean(1); mask=(grid>=s['window'][0])&(grid<=s['window'][1])
                if s['mode']=='erp':
                    feature=float(grid[mask][np.argmin(combined[mask]) if s['polarity']=='negative' else np.argmax(combined[mask])]*1000) if s['metric']=='latency' else float(combined[mask].mean())
                else:
                    mask_raw=(rt>=s['window'][0])&(rt<=s['window'][1]); feature=float(bandpower(sx[mask_raw][:,idx],s['band']).mean())
                    tf=time_frequency(sx[:,idx].mean(1),rt)
            trial=dict(index=event['index'],condition=event['condition'],condition_index=event['condition_index'],onset=event['onset'],accepted=not reasons,reasons=list(dict.fromkeys(reasons)),feature=feature,wave=epoch[:,idx].mean(1).tolist() if epoch is not None else None,times=grid.tolist(),tf=tf)
            trial['channel_trials']=channel_trials
            if s['protocol']=='speller':trial['speller']=event.get('speller',{})
            self.trials.append(trial); self.pending.remove(event); self.revision+=1
            d=DATA_ROOT/s['id']; np.savez_compressed(d/f"trial-{event['index']:04d}.npz",times=rt,raw=x,filtered=y,notched=sx,grid=grid,processed=epoch if epoch is not None else np.empty((0,4)))
            (d/'trials.json').write_text(dumps(self.trials))
    def analysis(self):
        if not self.session: return {}
        if self.session['mode']=='tf' and self.pending and hasattr(self,'times') and self.times:
            tick=int(self.times[-1]*2)
            if getattr(self,'tf_tick',None)!=tick:self.tf_tick=tick;self.cache_revision=None
        if self.cache_revision==(self.revision,len(getattr(self,"events",[]))): return self.cache_analysis
        s=self.session
        if s.get('protocol')=='speller':s['conditions']=['Unattended','Attended']
        if s['mode']=='tf':
            for trial in self.trials:
                if 'spectral_channels' not in trial:
                    path=DATA_ROOT/s['id']/f"trial-{trial['index']:04d}.npz"
                    if path.exists():
                        with np.load(path,allow_pickle=False) as z:trial['spectral_channels']=channel_windows(z['raw'],z['notched'],z['times'],s['window'],s['thresholds'])
            result=summarize_tf(self.trials,s,getattr(self,'review_band',s['band']));result['pending']=len(self.pending)
            if self.pending and hasattr(self,'times') and self.times:
                event=self.pending[-1];relative=np.asarray(self.times)-event['onset'];end=min(float(relative[-1]),s['window'][1])
                if end>=s['window'][0]+2:
                    latest=channel_windows(np.asarray(self.raw),np.asarray(self.spectral),relative,[end-2,end],s['thresholds'])
                    result['live_preview']={ch:r['preview_psd'] for ch,r in latest.items()};result['live_condition']=event['condition_index'];result['live_second']=end
            self.cache_revision=(self.revision,len(getattr(self,"events",[])));self.cache_analysis=result;return result
        analysis_trials=[t for t in self.trials if s.get('protocol')!='speller' or t.get('speller',{}).get('phase')=='calibration']
        groups=[]
        for c,label in enumerate(s['conditions']):
            all_trials=[t for t in analysis_trials if t['condition_index']==c]; good=[t for t in all_trials if t['accepted']]
            waves=[t['wave'] for t in good]; features=[t['feature'] for t in good]
            group=dict(label=label,accepted=len(good),rejected=len(all_trials)-len(good),features=features,mean=float(np.mean(features)) if features else None,se=float(np.std(features,ddof=1)/np.sqrt(len(features))) if len(features)>1 else None,erp=summarize(waves) if waves else None,recent=[{'wave':t['wave'],'index':t['index']} for t in good[-20:]])
            tfs=[t['tf'] for t in good if t['tf']]
            if tfs:
                n=min(len(v['times']) for v in tfs); group['tf']={**tfs[0],'times':tfs[0]['times'][:n],'power_db':np.mean([np.array(v['power_db'])[:,:n] for v in tfs],axis=0).tolist()}
            groups.append(group)
        result=dict(groups=groups,stats=compare(groups[0]['features'],groups[1]['features'],s['minimum']) if len(groups)==2 else dict(ready=False,reason='Multiple conditions: descriptive estimates; no omnibus test'),times=self.trials[0]['times'] if self.trials else [],trial_count=len(self.trials),rejections=[{k:t[k] for k in ['index','condition','reasons']} for t in self.trials if not t['accepted']],pending=len(self.pending),unit='ms' if s['mode']=='erp' and s['metric']=='latency' else 'µV' if s['mode']=='erp' else 'µV²')
        if s['mode']=='erp':
            result['channels']={}
            for channel in s['channels']:
                cg=[]; rejected=[]
                for c,label in enumerate(s['conditions']):
                    trials=[{**t.get('channel_trials',{}).get(channel,{}),'index':t['index']} for t in analysis_trials if t['condition_index']==c and channel in t.get('channel_trials',{})]
                    good=[t for t in trials if t['accepted']];features=[t['feature'] for t in good]
                    window=s.get('speller_review_windows_ms',{}).get(channel,s.get('speller_windows_ms',{}).get(channel)) if s.get('protocol')=='speller' else None
                    if window and good:
                        mask=(np.asarray(result['times'])>=window[0]/1000)&(np.asarray(result['times'])<window[1]/1000)
                        features=[float(np.asarray(t['wave'])[mask].mean()) for t in good]
                    cg.append(dict(label=label,accepted=len(good),rejected=len(trials)-len(good),features=features,mean=float(np.mean(features)) if features else None,se=float(np.std(features,ddof=1)/np.sqrt(len(features))) if len(features)>1 else None,erp=summarize([t['wave'] for t in good]) if good else None,recent=[{'wave':t['wave'],'index':t['index']} for t in good[-20:]]))
                    rejected.extend(dict(index=t['index'],condition=label,reasons=t['reasons']) for t in trials if not t['accepted'])
                result['channels'][channel]=dict(groups=cg,times=result['times'],unit=result['unit'],stats=compare(cg[0]['features'],cg[1]['features'],s['minimum']) if len(cg)==2 else dict(ready=False,reason='Multiple conditions: descriptive estimates; no omnibus test'),rejections=rejected)
                if s.get('protocol')=='speller':
                    result['channels'][channel]['window']=[v/1000 for v in window] if window else None
                    result['channels'][channel]['stats']={'ready':False,'reason':'Means ± SE · descriptive calibration data'}
        if all(g.get('tf') for g in groups):
            n=min(len(g['tf']['times']) for g in groups); result['tf_difference']={**groups[0]['tf'],'times':groups[0]['tf']['times'][:n],'power_db':(np.array(groups[1]['tf']['power_db'])[:,:n]-np.array(groups[0]['tf']['power_db'])[:,:n]).tolist()}
        result['behavior']=behavior_summary(s.get('protocol'),getattr(self,'events',[]))
        self.cache_revision=(self.revision,len(getattr(self,"events",[]))); self.cache_analysis=result; return result
    def stop(self,reason='completed'):
        with self.lock:
            if not self.session or not self.session['running']: return self.session
            self.process_pending(force=True); self.session.update(running=False,ended=time.time(),end_reason=reason)
            self.raw_file.close(); self.bio_file.close(); self.save_metadata()
            (DATA_ROOT/self.session['id']/'analysis.json').write_text(dumps(self.analysis()))
            return self.session
    def ingest_motion(self, body):
        self.developer.add_motion(body)
        sensor=body.get('sensor')
        if sensor not in self.motion_samples or self.source!='live': return
        values=np.asarray(body.get('values'),float)
        if values.shape!=(3,3) or not np.isfinite(values).all(): return
        received=float(body['received'])
        for i,row in enumerate(values): self.motion_samples[sensor].append((received-(2-i)/52,row.tolist()))
    def motion_state(self):
        now=time.time(); result={}
        for sensor,rows in self.motion_samples.items():
            recent=[v for t,v in rows if now-t<.5] if self.source=='live' else []
            if len(recent)<6: result[sensor]=None; continue
            x=np.asarray(recent)
            result[sensor]=float(np.sqrt(np.mean(np.sum((x-x.mean(0) if sensor=='acc' else x)**2,axis=1))))
        result['available']=any(result[k] is not None for k in ('acc','gyro'))
        result['moving']=(result['acc'] is not None and result['acc']>.035) or (result['gyro'] is not None and result['gyro']>8)
        return result
    def live_artifact_events(self):
        from live_artifacts import detect_events
        if not self.times or time.time()-self.times[-1]>.75 or len(self.raw)<FS//2: return []
        th=self.session['thresholds'] if self.session else DEFAULT_THRESHOLDS
        return detect_events(np.asarray(list(self.raw)[-FS//2:]),np.asarray(list(self.times)[-FS//2:]),th,profile=self.artifact_profile if self.source=='live' else None,motion=self.motion_state())
    def live_artifacts(self):
        return list(dict.fromkeys(e['label'] for e in self.live_artifact_events()))
    def contact_state(self):
        if not self.times or time.time()-self.times[-1]>2 or len(self.raw)<FS:
            return [{'channel':c,'state':'No signal','p2p':None,'level':'red'} for c in CHANNELS]
        x=np.asarray(list(self.raw)[-FS:]); result=[]
        for i,c in enumerate(CHANNELS):
            v=x[:,i]; p2p=float(np.ptp(v)) if np.isfinite(v).all() else None
            status='Signal available'
            if p2p is None: status='Data missing'
            elif np.max(np.abs(v))>=995: status='Clipping · check fit'
            elif np.std(v)<.5: status='Flat · check contact'
            elif p2p>150: status='Noisy · check fit'
            level='red' if status.startswith(('Data missing','Clipping','Flat')) else 'yellow' if status.startswith('Noisy') else 'green'
            result.append({'channel':c,'state':status,'p2p':p2p,'level':level})
        return result
    def update_artifact_regions(self, events):
        if not self.times:return
        end=float(self.times[-1])
        if self.artifact_region_time is not None and end<self.artifact_region_time:
            self.artifact_regions.clear(); self.open_artifact_regions.clear()
        for r in self.artifact_regions:r['active']=False
        for event in events:
            if isinstance(event,str): event=dict(label=event,channels=CHANNELS[:],kind='ocular',onset=max(float(self.times[0]),end-.5),offset=end)
            key=(event['label'],tuple(event['channels']))
            region=self.open_artifact_regions.get(key)
            if region is not None and event['onset']<=region['offset']+.08:
                region['offset']=max(region['offset'],event['offset']); region['active']=True
            else:
                region={**event,'active':True,'id':self.annotation_next_id}; self.annotation_next_id+=1; self.artifact_regions.append(region); self.open_artifact_regions[key]=region
        if self.session and self.session.get('running'):
            updates=[]
            for r in self.artifact_regions:
                key=(r['onset'],r['label'],tuple(r['channels']))
                signature=(r['offset'],r['active'])
                if self.annotation_log_state.get(key)!=signature:
                    updates.append(r.copy());self.annotation_log_state[key]=signature
            if updates:
                with open(DATA_ROOT/self.session['id']/'artifact_annotations.jsonl','a') as f:
                    for r in updates:f.write(dumps(r)+'\n')
        self.artifact_region_time=end
        while self.artifact_regions and self.artifact_regions[0]['offset']<end-10:self.artifact_regions.popleft()
        self.open_artifact_regions={k:v for k,v in self.open_artifact_regions.items() if v['offset']>=end-1}
    def live_spectra(self, stale):
        if stale: return {}
        stamp=self.times[-1]
        cached=getattr(self,'_spectrum_cache',None)
        if cached and 0<=stamp-cached[0]<.25: return cached[1]
        from live_spectrum import rolling_spectra
        result=rolling_spectra(list(self.times)[-FS*30:],list(self.spectral)[-FS*30:])
        self._spectrum_cache=(stamp,result)
        return result
    def snapshot(self):
        with self.lock:
            stale=not self.times or time.time()-self.times[-1]>2
            current_events=self.live_artifact_events()
            current_artifacts=list(dict.fromkeys(e['label']+('*' if e.get('uncertain',True) else '') for e in current_events))
            self.update_artifact_regions(current_events)
            return clean(dict(typing=self.typing.status(),developer=self.developer.status(),source=self.source,status=self.status,stale=stale,live_artifacts=current_artifacts,artifact_regions=list(self.artifact_regions),motion=self.motion_state(),motion_trace={k:list(v) for k,v in self.motion_samples.items()},live_spectra=self.live_spectra(stale),contact=self.contact_state(),quality=[] if stale else self.quality,band=None if stale else self.band,trace=dict(times=list(self.times)[-FS*8::2],values=list(self.filtered)[-FS*8::2]),session=self.session,analysis=self.analysis(),notifications=list(self.notifications),packet_loss=self.assembler.missing))
    def result_band(self,ident,low,high):
        band=[float(low),float(high)]
        if not all(math.isfinite(v) for v in band) or not 2<=band[0]<band[1]<=40:raise ValueError('Choose 2 ≤ low < high ≤ 40 Hz')
        view=self.saved_view(ident)
        if view.session['mode']!='tf':raise ValueError('Frequency review requires a time-frequency session')
        with view.lock:
            view.review_band=band;view.cache_revision=None
            return dict(session=view.session,analysis=view.analysis())

    def result_window(self,ident,start,end,channel=None):
        import copy
        start,end=float(start),float(end)
        if not (math.isfinite(start) and math.isfinite(end) and 0<=start<end<=.8): raise ValueError('Choose 0 ≤ start < end ≤ 800 ms')
        source=self.saved_view(ident)
        with source.lock:
            view=object.__new__(Engine);view.lock=threading.RLock();view.session=copy.deepcopy(source.session);view.trials=copy.deepcopy(source.trials)
        if view.session['mode']!='erp': raise ValueError('Window review is available for ERP recordings')
        if channel is not None:
            if view.session.get('protocol')!='speller' or channel not in view.session['channels']:raise ValueError('Choose a speller electrode')
            view.session.setdefault('speller_review_windows_ms',{})[channel]=[start*1000,end*1000]
            view.pending=[];view.revision=0;view.cache_revision=None;view.cache_analysis={}
            return dict(session=view.session,analysis=view.analysis())
        original=view.session['window'];view.session.update(window=[start,end],review_window=True,original_window=original,running=False)
        grid=np.asarray(view.trials[0]['times']) if view.trials else np.array([]);mask=(grid>=start)&(grid<=end)
        if len(grid) and mask.sum()<2: raise ValueError('Select a window containing at least two samples')
        def feature(wave):
            values=np.asarray(wave)[mask]
            return float(grid[mask][np.argmin(values) if view.session['polarity']=='negative' else np.argmax(values)]*1000) if view.session['metric']=='latency' else float(values.mean())
        for t in view.trials:
            if t['accepted']:t['feature']=feature(t['wave'])
            for c in t.get('channel_trials',{}).values():
                if c['accepted']:c['feature']=feature(c['wave'])
        view.pending=[];view.revision=0;view.cache_revision=None;view.cache_analysis={}
        return dict(session=view.session,analysis=view.analysis())

    def saved_view(self,ident):
        if not ident or any(c not in '0123456789-abcdef' for c in ident): raise ValueError('Invalid session identifier')
        with self.lock:
            if self.session and ident==self.session['id']: return self
            d=DATA_ROOT/ident
            if not (d/'session.json').is_file(): raise ValueError('Session not found')
            stamp=(ident,(d/'session.json').stat().st_mtime_ns,(d/'trials.json').stat().st_mtime_ns if (d/'trials.json').exists() else 0)
            cached=getattr(self,'_speller_saved_cache',None)
            if cached and cached[0]==stamp:return cached[1]
            view=object.__new__(Engine); view.lock=threading.RLock()
            view.session=json.loads((d/'session.json').read_text()); view.session={**view.session,'running':False}
            view.trials=json.loads((d/'trials.json').read_text()) if (d/'trials.json').exists() else []
            view.events=json.loads((d/'events.json').read_text()) if (d/'events.json').exists() else []
            view.pending=[]; view.revision=0; view.cache_revision=None; view.cache_analysis={}; view.readonly_saved=True
            if view.session.get('protocol')=='speller':
                from speller import retrospective_calibration
                retrospective_calibration(view)
                self._speller_saved_cache=(stamp,view)
            return view

    def export(self,kind):
        with self.lock:
            if not self.session: raise ValueError('Record a session first')
            if self.session['running']: self.raw_file.flush(); self.bio_file.flush()
            d=DATA_ROOT/self.session['id']
            if not getattr(self,'readonly_saved',False):
                self.save_metadata()
                (d/'analysis.json').write_text(dumps(self.analysis()))
                (d/'trials.json').write_text(dumps(self.trials))
            if kind=='pdf':
                from report import make_report
                return make_report(self.session,self.analysis(),self.events,d), 'application/pdf', self.session['id']+'.pdf'
            dest=io.BytesIO()
            with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
                names=['session.json','events.json','events.jsonl','continuous.csv','bandpower.csv','artifact_annotations.jsonl'] if kind=='raw' else ['session.json','trials.json','analysis.json','artifact_annotations.jsonl']
                for name in names:
                    if (d/name).exists(): z.write(d/name,name)
                if kind!='raw':
                    for file in d.glob('trial-*.npz'): z.write(file,file.name)
                    out=io.StringIO(); writer=csv.writer(out); writer.writerow(['trial','condition','accepted','feature','unit','reasons','response','correct','rt_ms','choice'])
                    responses={e['index']:e for e in self.events if e.get('kind')=='response' and 'index' in e}
                    for t in self.trials:
                        r=responses.get(t['index'],{});writer.writerow([t['index'],t['condition'],t['accepted'],t['feature'],self.analysis()['unit'],'; '.join(t['reasons']),r.get('key',''),r.get('correct',''),r.get('rt_ms',''),r.get('choice','')])
                    z.writestr('trial-summary.csv',out.getvalue())
                    if self.session['mode']=='tf':
                        out=io.StringIO();writer=csv.writer(out);writer.writerow(['trial','condition','channel','accepted','clean_seconds','power_dB','band_low_Hz','band_high_Hz'])
                        band=self.analysis()['band'];f=np.arange(2,40.01,.5);mask=(f>=band[0])&(f<=band[1])
                        for t in self.trials:
                            for ch,r in t.get('spectral_channels',{}).items():
                                value=float(10*np.log10(max(np.sum(np.asarray(r['psd'])[mask])*.5,1e-12))) if r['accepted'] else ''
                                writer.writerow([t['index'],t['condition'],ch,r['accepted'],r['clean_seconds'],value,*band])
                        z.writestr('channel-bandpower.csv',out.getvalue())
                    for g in self.analysis()['groups']:
                        if g['erp']:
                            out=io.StringIO(); writer=csv.writer(out); writer.writerow(['time_s','mean_uV','se_uV','pointwise_ci95_halfwidth_uV'])
                            for i,t in enumerate(self.analysis()['times']): writer.writerow([t,g['erp']['mean'][i],g['erp']['se'][i],g['erp']['ci95'][i] if g['erp']['ci95'] else ''])
                            z.writestr('erp-'+str(self.analysis()['groups'].index(g))+'.csv',out.getvalue())
            return dest.getvalue(),'application/zip',self.session['id']+'-'+kind+'.zip'
