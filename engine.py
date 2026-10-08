from private_storage import DATA_ROOT
import csv, io, json, math, os, random, subprocess, threading, time, uuid, zipfile
from pathlib import Path
from collections import deque, Counter
import numpy as np
from analysis import FS, CHANNELS, DEFAULT_THRESHOLDS, ERP_THRESHOLDS, Filters, artifacts, compare, summarize, bandpower, time_frequency
from protocols import PROTOCOLS, SOURCES

ROOT=Path(__file__).resolve().parent

def clean(v):
    if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)): return [clean(x) for x in v]
    if isinstance(v,(float,np.floating)): return float(v) if math.isfinite(v) else None
    if isinstance(v,np.integer): return int(v)
    return v

def dumps(v): return json.dumps(clean(v),allow_nan=False)

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
        self.lock=threading.RLock(); self.raw=deque(maxlen=FS*90); self.filtered=deque(maxlen=FS*90); self.times=deque(maxlen=FS*90)
        self.filters=Filters(); self.notch=Filters(notch_only=True); self.spectral=deque(maxlen=FS*90); self.source='live'; self.status={'state':'starting','message':'Checking existing Bluetooth authorization'}
        self.session=None; self.events=[]; self.trials=[]; self.pending=[]; self.notifications=deque(maxlen=20)
        self.motion_samples={k:deque(maxlen=104) for k in ('acc','gyro')}; self.last_quality=0; self.quality=[]; self.band=None; self.signal_count=0; self.bridge=None; self.bridge_enabled=threading.Event(); self.bridge_enabled.set()
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
            if not connected and ((self.session and self.session.get('running')) or self.typing.running or self.developer.status().get('recording')):
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
                x=self.rng.normal(0,4,(n,4))+8*np.sin(2*np.pi*10*ts[:,None]+np.arange(4))
                # Synthetic effects are deliberately present only in labeled simulation.
                for event in self.events[-8:]:
                    if event.get('kind')!='stimulus': continue
                    d=ts-event['onset']; c=event['condition_index']
                    if self.session and self.session['mode']=='erp':
                        x+=(3+5*c)*np.exp(-((d[:,None]-.38)/.075)**2)
                    elif np.any((d>=0)&(d<8)):
                        x+=c*8*np.sin(2*np.pi*10*ts[:,None])
                self.ingest(ts,x)
    def switch_source(self,source):
        if source not in ['live','simulation']: raise ValueError('Unknown data source')
        with self.lock:
            if self.typing.running: raise ValueError('Stop typing recording before changing source.')
            if self.developer.current: raise ValueError('Finish developer calibration before changing source.')
            if self.session and self.session['running']: raise ValueError('End the current session before changing source')
            self.source=source; self.artifact_regions.clear(); self.open_artifact_regions.clear(); self.artifact_region_time=None; [v.clear() for v in self.motion_samples.values()]; self.times.clear(); self.raw.clear(); self.filtered.clear(); self.filters=Filters(); self.notch=Filters(notch_only=True); self.spectral.clear(); self.quality=[]; self.band=None
            self.assembler=PacketAssembler(self.ingest)
            self.status={'state':'simulation','message':'SIMULATED EEG • No headset data'} if source=='simulation' else getattr(self,'live_status',{'state':'waiting','message':'Waiting for Muse'})
    def ingest(self,ts,values):
        with self.lock:
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
            self.process_pending()
            if self.typing.running and self.typing.pending:self.typing.process(list(self.times),list(self.raw),list(self.filtered))
            if self.typing.running and time.time()-self.typing.last_live_prediction>=1:self.typing.live_predict(list(self.times),list(self.raw),list(self.filtered))
    def typing_request(self,path,body):
        with self.lock:
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
        return {'protocols':result,'sources':SOURCES,'thresholds':DEFAULT_THRESHOLDS,'erp_thresholds':ERP_THRESHOLDS,'channels':CHANNELS,'assets':assets}
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
            selected=cfg.get('channels',p['channels'])
            if not selected or not set(selected)<=set(CHANNELS): raise ValueError('Select at least one valid electrode')
            thresholds={**(ERP_THRESHOLDS if p['mode']=='erp' else DEFAULT_THRESHOLDS),**cfg.get('thresholds',{})}
            if set(thresholds)!=set(DEFAULT_THRESHOLDS) or any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0 for v in thresholds.values()): raise ValueError('Artifact thresholds must be finite positive numbers')
            count=int(cfg.get('trials',p['trials'])); minimum=int(cfg.get('minimum',10))
            if not 20<=count<=1000 or not 10<=minimum<=500: raise ValueError('Trial count must be 20–1000; minimum usable trials 10–500')
            window=list(map(float,cfg.get('window',p['window'])))
            if len(window)!=2 or not 0<=window[0]<window[1]<= (8 if p['mode']!='erp' else .8): raise ValueError('Invalid analysis window')
            band=list(map(float,cfg.get('band',p.get('band',[8,13]))))
            if len(band)!=2 or not 2<=band[0]<band[1]<=40: raise ValueError('Band must be within 2–40 Hz')
            conditions=p['conditions']; assets=self.manifest(); pools=None
            if p['id']=='custom':
                conditions=[str(s).strip()[:80] for s in cfg.get('conditions',conditions)]
                if len(conditions)!=2 or not all(conditions) or conditions[0]==conditions[1]: raise ValueError('Provide two different condition labels')
            if p['id'] in ['faces','expertise']:
                categories=['faces','cars'] if p['id']=='faces' else cfg.get('expertise',[])
                if len(categories)!=2 or categories[0]==categories[1]: raise ValueError('Choose two different expertise categories')
                pools=[[a for a in assets if a['category']==cat] for cat in categories]
                if any(len(pool)<20 for pool in pools): raise ValueError('Import at least 20 distinct documented images per category first')
                conditions=categories
            a=np.array(list(self.raw)[-FS*2:]); times=np.array(list(self.times)[-FS*2:])
            reasons=artifacts(a,times,thresholds,[CHANNELS.index(c) for c in selected])
            if reasons and cfg.get('allow_noisy_start') is not True: raise ValueError('Improve contact before recording: '+', '.join(reasons))
            if len(self.times)<FS*3: raise ValueError('Wait for three seconds of stable EEG')
            seed=random.SystemRandom().randint(1,2**31-1); rng=random.Random(seed)
            labels=[1]*round(count*p['probability'])+[0]*(count-round(count*p['probability'])); rng.shuffle(labels)
            plan=[]
            for i,c in enumerate(labels):
                item=dict(index=i,condition_index=c,condition=conditions[c],duration=rng.randint(*p['stim_ms']),isi=rng.randint(*p['isi_ms']),direction=rng.choice(['left','right']),number=rng.randint(600,999))
                if pools: item['asset']=pools[c][(i//2)%len(pools[c])]['file']
                plan.append(item)
            session_id=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
            directory=DATA_ROOT/session_id; directory.mkdir()
            calibration=cfg.get('calibration',{})
            self.session={**p,'id':session_id,'protocol':p['id'],'source':self.source,'channels':selected,'conditions':conditions,'trials_planned':count,'minimum':minimum,'window':window,'band':band,'thresholds':thresholds,'seed':seed,'plan':plan,'running':True,'started':time.time(),'phase':'recording','calibration':calibration,'metric':cfg.get('metric','amplitude'),'training_seconds':max(30,min(1800,int(cfg.get('training_seconds',120)))),'timing':'Browser frame / Web Audio software timestamps aligned by clock ping; BLE receive-anchored sample clock. Physical display/audio/BLE latencies uncalibrated.','analysis':'Causal .1Hz HP, 30Hz LP, 60Hz notch Q30. ERP pre-stimulus baseline -200..0ms. TF uses 60 Hz notched EEG with DC removal and 1s Hann windows. Trial-level statistics, repeated looks; no population inference.'}
            if self.session['metric'] not in ['amplitude','latency']: raise ValueError('Unknown measurement')
            self.session['preflight_quality']={'warnings':reasons,'continued_anyway':cfg.get('allow_noisy_start') is True}
            self.session['electrode_warning']=selected!=p['channels']
            self.events=[]; self.trials=[]; self.pending=[]; self.revision+=1
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
                if i<0 or i>=self.session['trials_planned'] or c not in [0,1]: raise ValueError('Invalid trial index/condition')
                if any(p.get('kind')=='stimulus' and p.get('index')==i for p in self.events): raise ValueError('Duplicate trial marker')
                event['condition']=self.session['conditions'][c]; self.pending.append(event)
            if kind=='phase': self.session['phase']=str(e.get('phase',''))[:100]
            self.events.append(event)
            with open(DATA_ROOT/self.session['id']/'events.jsonl','a') as f: f.write(dumps(event)+'\n')
            self.save_metadata(); return event
    def process_pending(self,force=False):
        if not self.session or not self.pending or not self.times: return
        s=self.session; tt=np.asarray(self.times); raw=np.asarray(self.raw); filt=np.asarray(self.filtered); spectral=np.asarray(self.spectral)
        for event in self.pending[:]:
            pre=.2 if s['mode']=='erp' else 2.; end=.8 if s['mode']=='erp' else 8.
            if not force and tt[-1]<event['onset']+end+.03: continue
            t=tt-event['onset']; use=(t>=-pre)&(t<=end); rt=t[use]; x=raw[use]; y=filt[use]; sx=spectral[use]
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
            self.trials.append(trial); self.pending.remove(event); self.revision+=1
            d=DATA_ROOT/s['id']; np.savez_compressed(d/f"trial-{event['index']:04d}.npz",times=rt,raw=x,filtered=y,notched=sx,grid=grid,processed=epoch if epoch is not None else np.empty((0,4)))
            (d/'trials.json').write_text(dumps(self.trials))
    def analysis(self):
        if not self.session: return {}
        if self.cache_revision==self.revision: return self.cache_analysis
        s=self.session; groups=[]
        for c,label in enumerate(s['conditions']):
            all_trials=[t for t in self.trials if t['condition_index']==c]; good=[t for t in all_trials if t['accepted']]
            waves=[t['wave'] for t in good]; features=[t['feature'] for t in good]
            group=dict(label=label,accepted=len(good),rejected=len(all_trials)-len(good),features=features,mean=float(np.mean(features)) if features else None,se=float(np.std(features,ddof=1)/np.sqrt(len(features))) if len(features)>1 else None,erp=summarize(waves) if waves else None,recent=[{'wave':t['wave'],'index':t['index']} for t in good[-20:]])
            tfs=[t['tf'] for t in good if t['tf']]
            if tfs:
                n=min(len(v['times']) for v in tfs); group['tf']={**tfs[0],'times':tfs[0]['times'][:n],'power_db':np.mean([np.array(v['power_db'])[:,:n] for v in tfs],axis=0).tolist()}
            groups.append(group)
        result=dict(groups=groups,stats=compare(groups[0]['features'],groups[1]['features'],s['minimum']),times=self.trials[0]['times'] if self.trials else [],trial_count=len(self.trials),rejections=[{k:t[k] for k in ['index','condition','reasons']} for t in self.trials if not t['accepted']],pending=len(self.pending),unit='ms' if s['mode']=='erp' and s['metric']=='latency' else 'µV' if s['mode']=='erp' else 'µV²')
        if s['mode']=='erp':
            result['channels']={}
            for channel in s['channels']:
                cg=[]; rejected=[]
                for c,label in enumerate(s['conditions']):
                    trials=[{**t.get('channel_trials',{}).get(channel,{}),'index':t['index']} for t in self.trials if t['condition_index']==c and channel in t.get('channel_trials',{})]
                    good=[t for t in trials if t['accepted']];features=[t['feature'] for t in good]
                    cg.append(dict(label=label,accepted=len(good),rejected=len(trials)-len(good),features=features,mean=float(np.mean(features)) if features else None,se=float(np.std(features,ddof=1)/np.sqrt(len(features))) if len(features)>1 else None,erp=summarize([t['wave'] for t in good]) if good else None,recent=[{'wave':t['wave'],'index':t['index']} for t in good[-20:]]))
                    rejected.extend(dict(index=t['index'],condition=label,reasons=t['reasons']) for t in trials if not t['accepted'])
                result['channels'][channel]=dict(groups=cg,times=result['times'],unit=result['unit'],stats=compare(cg[0]['features'],cg[1]['features'],s['minimum']),rejections=rejected)
        if all(g.get('tf') for g in groups):
            n=min(len(g['tf']['times']) for g in groups); result['tf_difference']={**groups[0]['tf'],'times':groups[0]['tf']['times'][:n],'power_db':(np.array(groups[1]['tf']['power_db'])[:,:n]-np.array(groups[0]['tf']['power_db'])[:,:n]).tolist()}
        self.cache_revision=self.revision; self.cache_analysis=result; return result
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
    def snapshot(self):
        with self.lock:
            stale=not self.times or time.time()-self.times[-1]>2
            current_events=self.live_artifact_events()
            current_artifacts=list(dict.fromkeys(e['label']+('*' if e.get('uncertain',True) else '') for e in current_events))
            self.update_artifact_regions(current_events)
            return clean(dict(typing=self.typing.status(),developer=self.developer.status(),source=self.source,status=self.status,stale=stale,live_artifacts=current_artifacts,artifact_regions=list(self.artifact_regions),motion=self.motion_state(),contact=self.contact_state(),quality=[] if stale else self.quality,band=None if stale else self.band,trace=dict(times=list(self.times)[-FS*8::2],values=list(self.filtered)[-FS*8::2]),session=self.session,analysis=self.analysis(),notifications=list(self.notifications),packet_loss=self.assembler.missing))
    def result_window(self,ident,start,end):
        import copy
        start,end=float(start),float(end)
        if not (math.isfinite(start) and math.isfinite(end) and 0<=start<end<=.8): raise ValueError('Choose 0 ≤ start < end ≤ 800 ms')
        source=self.saved_view(ident)
        with source.lock:
            view=object.__new__(Engine);view.lock=threading.RLock();view.session=copy.deepcopy(source.session);view.trials=copy.deepcopy(source.trials)
        if view.session['mode']!='erp': raise ValueError('Window review is available for ERP recordings')
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
            view=object.__new__(Engine); view.lock=threading.RLock()
            view.session=json.loads((d/'session.json').read_text()); view.session={**view.session,'running':False}
            view.trials=json.loads((d/'trials.json').read_text()) if (d/'trials.json').exists() else []
            view.events=json.loads((d/'events.json').read_text()) if (d/'events.json').exists() else []
            view.pending=[]; view.revision=0; view.cache_revision=None; view.cache_analysis={}; view.readonly_saved=True
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
                    out=io.StringIO(); writer=csv.writer(out); writer.writerow(['trial','condition','accepted','feature','unit','reasons'])
                    for t in self.trials: writer.writerow([t['index'],t['condition'],t['accepted'],t['feature'],self.analysis()['unit'],'; '.join(t['reasons'])])
                    z.writestr('trial-summary.csv',out.getvalue())
                    for g in self.analysis()['groups']:
                        if g['erp']:
                            out=io.StringIO(); writer=csv.writer(out); writer.writerow(['time_s','mean_uV','se_uV','pointwise_ci95_halfwidth_uV'])
                            for i,t in enumerate(self.analysis()['times']): writer.writerow([t,g['erp']['mean'][i],g['erp']['se'][i],g['erp']['ci95'][i] if g['erp']['ci95'] else ''])
                            z.writestr('erp-'+str(self.analysis()['groups'].index(g))+'.csv',out.getvalue())
            return dest.getvalue(),'application/zip',self.session['id']+'-'+kind+'.zip'
