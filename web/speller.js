/* Experimental 6×6 row/column speller. Target cues never enter spelling predictions. */
async function startSpeller(){
 if(personalBusy)return;
 let session,ended=false,index=0,group=0,output='',busy=false;
 const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789 ';
 const dialog=document.createElement('dialog');dialog.className='speller-dialog';
 dialog.innerHTML='<header><strong>P300 speller</strong><span class="speller-source"></span><button class="speller-end">End & save</button></header><div class="speller-layout"><section><h2 class="speller-cue">Preparing EEG…</h2><progress max="8" value="0"></progress><output class="speller-output" aria-label="Spelled text"></output><div class="speller-grid"></div><p class="speller-status" role="status"></p><div class="speller-actions"></div></section><div class="speller-analysis"><p class="speller-validation"></p><details open><summary>Calibration responses <span title="Other flashes: teal. Attended flashes: gold. Mean ± approximate pointwise 95% interval. Each electrode is screened independently. These are calibration responses, not proof of spelling accuracy.">?</span></summary><div class="speller-erps"></div></details><details><summary>How this works</summary><p>Attend to one letter and silently count its flashes. Eight calibration letters train a local classifier using 100–700 ms EEG features. Testing holds out whole calibration letters. Muse spelling accuracy is unvalidated. Flash timing uses software timestamps; physical screen and Bluetooth latency are uncalibrated. Output and EEG stay local. Stop if flashing is uncomfortable.</p><a href="https://pubmed.ncbi.nlm.nih.gov/16792299/" target="_blank" rel="noopener">P300 spelling method</a></details></div></div>';
 const q=s=>dialog.querySelector(s),cells=[];
 for(const letter of alphabet){const cell=document.createElement('span');cell.textContent=letter===' '?'␣':letter;q('.speller-grid').append(cell);cells.push(cell)}
 const setStatus=text=>q('.speller-status').textContent=text;
 const check=()=>{if(ended)throw Error('cancelled');if(state?.stale)throw Error('EEG signal lost. Session saved; reconnect before recalibrating.');if(document.hidden)throw Error('Task paused: display hidden. Restart calibration.');};
 const pause=async ms=>{const t=performance.now();await new Promise(r=>setTimeout(r,ms));check();if(performance.now()-t-ms>100)throw Error('Display timing interrupted. Session saved; restart calibration.');};
 const paint=async()=>{await frame();check();};
 const clear=()=>cells.forEach(c=>c.classList.remove('flash'));
 const stop=async(reason='stopped')=>{
  if(ended)return;ended=true;clear();document.removeEventListener('visibilitychange',hidden);personalBusy=false;journeyRun=false;
  if(session)try{await api('stop',{reason});state=await api('state');await refreshResultSessions()}catch(e){toast(e.message)}
  dialog.close();dialog.remove();$('headsetSetup').open=false;journeySetStep('setup');toast(session?'Spelling session saved locally. Calibration responses are available in Results.':'Connect the headset, then try again.');
 };
 const hidden=()=>{if(document.hidden)void stop('presentation hidden')};
 dialog.addEventListener('cancel',e=>{e.preventDefault();void stop()});q('.speller-end').onclick=()=>stop();
 document.body.append(dialog);dialog.showModal();personalBusy=true;
 try{
  await syncClock();session=await api('start',{protocol:'speller',trials:960,minimum:10,channels:['TP9','AF7','AF8','TP10'],allow_noisy_start:true,calibration:{matrix:'6x6',flash_ms:120,onset_interval_ms:300,repetitions:5,feature_window_ms:[100,700],feature_bin_ms:50,covariance_shrinkage:.3}});
  if(ended){await api('stop',{reason:'cancelled during startup'});return}
  personalBusy=true;journeyRun=true;journeySetStep('run');q('.speller-source').textContent=session.source==='simulation'?'SIMULATION — not real EEG':'Live EEG · local recording';document.addEventListener('visibilitychange',hidden);
  const chart=data=>{
   q('.speller-erps').replaceChildren();
   for(const [ch,conditions]of Object.entries(data.channels)){
    const box=document.createElement('div');const title=document.createElement('strong');title.textContent=ch+' · ';for(const [k,c]of conditions.entries()){const label=document.createElement('span');label.style.color=k?'#b27b20':'#268f86';label.textContent=`${c.n} ${k?'attended':'other / '}`;title.append(label)}box.append(title);
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 300 115');svg.setAttribute('aria-label',`${ch} calibration ERP, −200 to 800 milliseconds, ±15 microvolts`);
    const xy=(v,i,n)=>`${20+270*i/(n-1)},${Math.max(8,Math.min(98,53-v*3))}`;
    for(const [k,c]of conditions.entries())if(c.mean.length){
     const color=k?'#cd922f':'#268f86';
     if(c.ci.length){const band=document.createElementNS(ns,'polygon');band.setAttribute('points',c.mean.map((v,i)=>xy(v+c.ci[i],i,c.mean.length)).concat(c.mean.map((v,i)=>xy(v-c.ci[i],i,c.mean.length)).reverse()).join(' '));band.setAttribute('fill',color);band.setAttribute('opacity','.14');svg.append(band)}
     const line=document.createElementNS(ns,'polyline');line.setAttribute('points',c.mean.map((v,i)=>xy(v,i,c.mean.length)).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',color);line.setAttribute('stroke-width','2');svg.append(line)
    }
    for(const [x,y,text]of [[20,112,'−200'],[74,112,'0'],[236,112,'600 ms'],[0,15,'15'],[0,56,'0'],[0,97,'−15 µV']]){const t=document.createElementNS(ns,'text');t.setAttribute('x',x);t.setAttribute('y',y);t.setAttribute('font-size','8');t.textContent=text;svg.append(t)}box.append(svg);q('.speller-erps').append(box)
   }
  };
  const sequence=async(target,phase)=>{
   if(index+60>960)throw Error('Session limit reached. Begin a new calibration to continue.');
   const thisGroup=group++;
   for(let rep=0;rep<5;rep++){
    const lines=Array.from({length:12},(_,i)=>i);for(let i=11;i>0;i--){const j=Math.floor(Math.random()*(i+1));[lines[i],lines[j]]=[lines[j],lines[i]]}
    for(const line of lines){
     await paint();cells.forEach((c,i)=>c.classList.toggle('flash',line<6?Math.floor(i/6)===line:i%6===line-6));
     const onset=now(),start=performance.now();
     // Send without waiting for IPC; flash length is independent of service round-trip.
     const pending=marker({kind:'stimulus',index:index++,condition_index:target===null?0:Number(line===Math.floor(target/6)||line===6+target%6),onset,speller:{group:thisGroup,line,phase,target}}).then(()=>null,e=>e);
     await pause(120);await paint();clear();await pause(Math.max(0,300-(performance.now()-start)));
     const error=await pending;if(error)throw error;
    }
    setStatus(`${phase==='calibration'?'Calibration':'Spelling'} · repetition ${rep+1} / 5`);
    if(phase==='calibration')chart(await api('speller',{action:'status'}));
   }
   await pause(1100);check();return thisGroup;
  };
  const targets=[0,7,14,21,28,35,4,31];
  for(let i=0;i<targets.length;i++){
   q('.speller-cue').textContent=`Count flashes of ${alphabet[targets[i]]===' '?'SPACE':alphabet[targets[i]]}`;q('progress').value=i;
   setStatus(`${i+1} / 8 · Blink now; flashes begin in three seconds.`);await pause(3000);
   await sequence(targets[i],'calibration');chart(await api('speller',{action:'status'}));
  }
  const trained=await api('speller',{action:'fit'});chart(trained);q('progress').value=8;
  const correct=trained.validation.filter(v=>v.predicted===v.expected).length,valid=trained.validation.filter(v=>v.predicted!==undefined&&v.predicted!==null).length;
  q('.speller-cue').textContent='Choose a letter with your eyes';q('.speller-validation').textContent=`Held-out calibration: ${correct} / 8 correct (${8-valid} unavailable). Random guessing: 1 / 36. Exploratory; not a confidence score.`;setStatus('Attend to a letter, then press Select a letter.');
  const action=(text,fn)=>{const b=personalButton(text,fn);q('.speller-actions').append(b);return b};
  action('Select a letter',async()=>{
   if(busy||ended)return;busy=true;q('.speller-actions').querySelectorAll('button').forEach(b=>b.disabled=true);
   try{setStatus('Look at your chosen letter. Starting in three seconds.');await pause(3000);const g=await sequence(null,'spelling');const r=await api('speller',{action:'predict',group:g});check();const p=r.prediction;if(p.symbol===null)setStatus(p.reason);else{output+=p.symbol;q('.speller-output').textContent=output;setStatus(`Selected ${p.symbol===' '?'SPACE':p.symbol} · experimental EEG prediction`)}}
   catch(e){if(!ended){await stop(e.message);toast(e.message)}}finally{busy=false;q('.speller-actions').querySelectorAll('button').forEach(b=>b.disabled=false)}
  });
  action('Delete last letter',()=>{output=output.slice(0,-1);q('.speller-output').textContent=output;void api('speller',{action:'delete'}).catch(e=>toast(e.message))});
 }catch(e){if(!ended){await stop(e.message);toast(e.message)}}
}

function renderSpellerSummary(){
 let panel=$('spellerSummary');if(!panel){panel=personalElement('section',undefined,'panel');panel.id='spellerSummary';$('recordSection').prepend(panel)}
 const s=state?.session;panel.hidden=s?.protocol!=='speller';if(panel.hidden)return;
 const v=s.speller_validation||[],correct=v.filter(x=>x.expected===x.predicted).length;
 panel.replaceChildren(personalElement('h2','P300 spelling'),personalElement('p',s.speller_text||'No letters selected.'),personalElement('p',v.length?`Held-out calibration: ${correct} / ${v.length} letters correct · random guessing: 1 / 36.`:'Calibration was not completed.'),personalElement('p','Experimental Muse adaptation. Plots below show calibration flashes only; spelling flashes have no known target label.'));
}
