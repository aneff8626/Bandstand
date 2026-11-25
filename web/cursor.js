/* Experimental four-arrow P300 cursor. Target cues never enter move predictions. */
let cursorRunning=false;
const CURSOR_GLYPHS=['↑','→','↓','←'],CURSOR_NAMES=['up','right','down','left'],CURSOR_GRID=7;
// Each round flashes every arrow once in a new random order; the same arrow never flashes twice in a row.
function cursorFlashOrder(rounds,random=Math.random){
 const order=[];
 for(let r=0;r<rounds;r++){
  let round;
  do{round=[0,1,2,3];for(let i=3;i>0;i--){const j=Math.floor(random()*(i+1));[round[i],round[j]]=[round[j],round[i]]}}while(order.length&&round[0]===order.at(-1));
  order.push(...round);
 }
 return order;
}
// A target three to five moves away, so every target needs several decisions.
function cursorTarget(position,random=Math.random){
 const cells=[];
 for(let x=0;x<CURSOR_GRID;x++)for(let y=0;y<CURSOR_GRID;y++){const d=Math.abs(x-position[0])+Math.abs(y-position[1]);if(d>=3&&d<=5)cells.push([x,y])}
 return cells[Math.floor(random()*cells.length)];
}
function cursorScore(summary){
 if(!summary?.moves)return '';
 return `Targets reached ${summary.reached} / ${summary.targets.length} · moves toward the target ${summary.toward} / ${summary.decided} (random moves would give about ${summary.chance_toward.toFixed(1)})`;
}
function prepareCursor(){
 if(!personalLeave())return;
 personalRoute('bci');
 preparePersonalActivity('P300 direction cursor','Calibrate, then steer a dot with EEG',()=>startCursor());
 journeySetStep('setup');
}
async function startCursor(){
 if(personalBusy)return;
 personalRoute('bci');chosenActivityTitle='P300 direction cursor';selectedResult=null;renderRevision='';
 let session,ended=false,index=0,group=0,busy=false,pauseRequested=false,position=[3,3],target=null,targetNumber=0,trail=[];
 const dialog=document.createElement('section');dialog.className='speller-run cursor-run';dialog.id='cursorRun';
 dialog.innerHTML='<header><strong>P300 direction cursor</strong><span class="speller-source"></span><button class="speller-end">End & save</button></header><div class="speller-layout"><section><h2 class="speller-cue">Preparing EEG…</h2><progress max="8" value="0"></progress><div class="cursor-stage"><div class="cursor-grid" role="img" aria-label="Cursor grid"></div></div><p class="speller-evidence muted"></p><p class="speller-status" role="status"></p><div class="speller-actions"></div></section><div class="speller-analysis"><p class="speller-validation"></p><p class="cursor-score"></p><details open><summary>Calibration responses <span title="Unattended: teal. Attended: gold; these labels indicate the instructed arrow, not measured attention. Mean ± approximate pointwise 95% interval. Each electrode is screened independently. These are calibration responses, not proof of cursor accuracy.">?</span></summary><div class="speller-erps"></div></details><details><summary>How this works</summary><p>Four arrows flash one at a time, ten times each per move. Count the flashes of the arrow you want; the dot moves one cell that way. Eight cued calibration moves train a local classifier using an interval of 100–400 ms selected for each electrode within 100–800 ms, the same method as the speller. Inner held-out moves select the interval; separate outer held-out moves assess accuracy (chance is 25%). Bits per minute use that held-out accuracy at about 15 seconds per move. Muse cursor accuracy is unvalidated. Flash timing uses software timestamps; physical screen and Bluetooth latency are uncalibrated. EEG stays local. Stop if flashing is uncomfortable.</p><a href="https://pubmed.ncbi.nlm.nih.gov/16792299/" target="_blank" rel="noopener">P300 classification method</a></details></div></div>';
 const q=s=>dialog.querySelector(s),arrows=[],cells=[];
 for(const [i,glyph]of CURSOR_GLYPHS.entries()){const arrow=document.createElement('span');arrow.className='cursor-arrow';arrow.dataset.arrow=i;arrow.textContent=glyph;arrow.setAttribute('aria-label',CURSOR_NAMES[i]+' arrow');q('.cursor-stage').append(arrow);arrows.push(arrow)}
 for(let i=0;i<CURSOR_GRID*CURSOR_GRID;i++){const cell=document.createElement('span');q('.cursor-grid').append(cell);cells.push(cell)}
 const draw=()=>cells.forEach((c,i)=>{const x=i%CURSOR_GRID,y=Math.floor(i/CURSOR_GRID);c.className='';if(trail.some(p=>p[0]===x&&p[1]===y))c.classList.add('cursor-trail');if(target&&target[0]===x&&target[1]===y)c.classList.add('cursor-target');if(position[0]===x&&position[1]===y)c.classList.add('cursor-dot')});
 const setStatus=text=>q('.speller-status').textContent=text;
 const check=()=>{if(ended)throw Error('cancelled');if(state?.stale)throw Error('EEG signal lost. Session saved; reconnect before recalibrating.');if(document.hidden)throw Error('Task paused: display hidden. Restart calibration.');};
 const pause=async ms=>{const t=performance.now();await new Promise(r=>setTimeout(r,ms));check();if(performance.now()-t-ms>100)throw Error('Display timing interrupted. Session saved; restart calibration.');};
 const paint=async()=>{await frame();check();};
 const clear=()=>arrows.forEach(a=>a.classList.remove('flash'));
 const stop=async(reason='stopped')=>{
  if(ended)return;ended=true;clear();document.removeEventListener('visibilitychange',hidden);
  if(session)try{await api('stop',{reason});state=await api('state');await refreshResultSessions()}catch(e){toast(e.message)}
  document.removeEventListener('keydown',escape);dialog.remove();document.body.classList.remove('cursor-running');cursorRunning=false;personalBusy=false;journeyRun=false;
  if(session){personalRoute('lab');chosenActivityTitle='P300 direction cursor';selectedResult=null;renderRevision='';journeyFreshResult=true;journeySetStep('summary');render()}
  else prepareCursor();
  $('headsetSetup').open=false;toast(session?'Cursor task saved.':'Connect the headset, then try again.');
 };
 const hidden=()=>{if(document.hidden)void stop('presentation hidden')};
 const escape=e=>{if(e.key==='Escape'){e.preventDefault();void stop()}};document.addEventListener('keydown',escape);q('.speller-end').onclick=()=>stop();
 document.querySelector('main').append(dialog);document.body.classList.add('cursor-running');cursorRunning=true;personalBusy=true;journeyRun=true;journeySetStep('run');draw();
 try{
  await syncClock();session=await api('start',{protocol:'cursor',trials:2400,minimum:10,channels:['TP9','AF7','AF8','TP10'],allow_noisy_start:true,calibration:{arrows:4,grid:CURSOR_GRID,flash_ms:120,onset_interval_ms:300,repetitions:10,feature_window_ms:[100,800],feature_bin_ms:50,candidate_durations_ms:[100,150,200,250,300,350,400],window_selection:'nested held-out-move AUC',covariance_shrinkage:.3}});
  if(ended){await api('stop',{reason:'cancelled during startup'});return}
  personalBusy=true;journeyRun=true;journeySetStep('run');q('.speller-source').textContent=session.source==='simulation'?'SIMULATION — not real EEG; free moves are random':'';document.addEventListener('visibilitychange',hidden);
  q('.speller-evidence').title='Classifier gap: winning arrow score minus runner-up, in standardized classifier units. Larger means stronger separation, not probability of correctness. Calibration accuracy is shown separately.';
  const chart=data=>p300CalibrationChart(q('.speller-erps'),data);
  const sequence=async(cue,phase)=>{
   if(index+40>2400)throw Error('Session limit reached. Begin a new session to continue.');
   const thisGroup=group++;const order=cursorFlashOrder(10);setStatus('Count the flashes.');
   for(const [k,arrow]of order.entries()){
    await paint();arrows.forEach((a,i)=>a.classList.toggle('flash',i===arrow));
    const onset=now(),start=performance.now();
    // Send without waiting for IPC; flash length is independent of service round-trip.
    const pending=marker({kind:'stimulus',index:index++,condition_index:cue===null?0:Number(arrow===cue),onset,cursor:{group:thisGroup,arrow,phase,target:cue}}).then(()=>null,e=>e);
    await pause(120);await paint();clear();await pause(Math.max(0,300-(performance.now()-start)));
    const error=await pending;if(error)throw error;
    if(k%4===3)setStatus(`${phase==='calibration'?'Calibration':'Move'} · round ${(k+1)/4} / 10`);
   }
   await pause(1100);check();return thisGroup;
  };
  // Every block of four cues each arrow once, so calibration stays balanced at 8, 12, … 24 moves.
  const cues=[0,1,2,3,2,0,3,1,1,3,0,2,3,2,1,0,0,2,1,3,2,3,0,1];
  let calibrated=0,trained=null;
  const collect=async count=>{
   const limit=Math.min(24,calibrated+count);q('progress').max=limit;target=null;trail=[];draw();
   for(;calibrated<limit;calibrated++){
    const cue=cues[calibrated];arrows.forEach(a=>a.classList.remove('cue-target'));q('.speller-cue').classList.remove('cue-nudge');void q('.speller-cue').offsetWidth;arrows[cue].classList.add('cue-target');q('.speller-cue').classList.add('cue-nudge');
    q('.speller-cue').textContent=`Count flashes of ${CURSOR_GLYPHS[cue]} (${CURSOR_NAMES[cue]})`;q('progress').value=calibrated;
    setStatus(`${calibrated+1} / ${limit} · Blink now; flashes begin in three seconds.`);await pause(3000);
    arrows[cue].classList.remove('cue-target');await sequence(cue,'calibration');chart(await api('cursor',{action:'status'}));
   }
   q('progress').value=calibrated;setStatus('Checking held-out calibration moves…');
   try{trained=await api('cursor',{action:'fit'});chart(trained);
    const quality=trained.quality;q('.speller-validation').textContent=`${quality.correct} / ${quality.total} held-out moves correct (chance 25%) · attended/unattended AUC ${quality.auc===null?'unavailable':quality.auc.toFixed(2)} (chance 0.50) · about ${quality.bits_per_minute.toFixed(1)} bits/min. ${quality.message}`;q('.speller-validation').title=quality.rule;
    q('.speller-cue').textContent=quality.ready?'Steer toward the gold square':'More calibration recommended';setStatus(quality.message);
   }catch(e){trained=null;q('.speller-validation').textContent=e.message;setStatus('Check contact, then add calibration moves.');}
  };
  await collect(8);
  const action=(text,fn)=>{const b=personalButton(text,fn);q('.speller-actions').append(b);return b};
  const updateActions=()=>{q('.speller-actions').querySelectorAll('button').forEach(b=>b.disabled=busy);more.disabled=busy||calibrated>=24||index+160>2400;go.disabled=busy||!trained;go.textContent=trained?.quality?.ready?'Reach a target':'Try steering anyway';hold.disabled=!busy||!target;hold.textContent=pauseRequested?'Pausing after this move…':'Pause after this move';};
  const more=action('Add 4 calibration moves',async()=>{
   if(busy||ended||calibrated>=24)return;busy=true;updateActions();
   try{await collect(4)}catch(e){if(!ended){await stop(e.message);toast(e.message)}}finally{busy=false;updateActions()}
  });
  const go=action('Reach a target',async()=>{
   if(busy||ended)return;busy=true;pauseRequested=false;
   target=cursorTarget(position);targetNumber++;trail=[position.slice()];draw();updateActions();
   const fewest=Math.abs(target[0]-position[0])+Math.abs(target[1]-position[1]),limit=fewest*2+4;let moves=0;
   q('.speller-cue').textContent=`Reach the gold square · fewest moves ${fewest}`;
   try{
    for(;;){
     setStatus('Count the flashes of the arrow pointing toward the gold square. Starting in two seconds.');await pause(2000);
     const g=await sequence(null,'moving');
     const r=await api('cursor',{action:'move',group:g,position,target,target_number:targetNumber});check();
     const m=r.move;moves++;
     if(m.direction===null)setStatus(`${m.reason} The dot stayed put.`);
     else{position=m.end;trail.push(position.slice());setStatus(`Moved ${m.arrow}${m.blocked?' · at the edge, so it stayed put':m.toward?' · closer':' · not closer'}`)}
     q('.speller-evidence').textContent=Number.isFinite(m.margin)?`Arrow gap ${m.margin.toFixed(2)}`:'';q('.cursor-score').textContent=cursorScore(r.summary);draw();
     if(m.reached){setStatus(`Target reached in ${moves} moves (fewest possible ${fewest}).`);break}
     if(moves>=limit){setStatus(`Stopped after ${moves} moves without reaching the target (fewest possible ${fewest}).`);break}
     if(pauseRequested){setStatus('Paused. Reach a target starts a new one from here.');break}
     updateActions();
    }
    target=null;draw();q('.speller-cue').textContent='Steer toward the gold square';
   }catch(e){if(!ended){await stop(e.message);toast(e.message)}}finally{busy=false;pauseRequested=false;updateActions()}
  });
  const hold=action('Pause after this move',()=>{pauseRequested=true;updateActions()});
  updateActions();
 }catch(e){if(!ended){await stop(e.message);toast(e.message)}}
}

function renderCursorSummary(){
 let panel=$('cursorSummary');if(!panel){panel=personalElement('section',undefined,'panel');panel.id='cursorSummary';$('recordSection').prepend(panel)}
 const s=state?.session;panel.hidden=s?.protocol!=='cursor';if(panel.hidden)return;
 const v=s.cursor_validation||[],correct=v.filter(x=>x.expected===x.predicted).length,moves=s.cursor_moves||[];
 panel.querySelectorAll('.info-dot').forEach(b=>b._helpDialog?.remove());panel.replaceChildren(personalElement('h2','Cursor task'));
 const help=headsetHelp('Cursor evidence',[personalElement('p','Each move is decided only from EEG: the arrow whose flashes produced the strongest classifier score wins. The arrow gap compares it with the runner-up in standardized classifier units; it is not a probability. “Toward the target” counts moves that reduced the distance to the gold square; random moves would do this about as often as the number of helpful arrows allows, shown alongside. Held-out calibration tests whole cued moves the classifier never saw. Eight moves provide only a rough performance check; Muse cursor accuracy is unvalidated.')]);
 const heading=personalElement('h3','Targets');heading.append(help);panel.append(heading);
 const targets={};for(const m of moves)(targets[m.target_number]??=[]).push(m);
 const list=personalElement('div',undefined,'speller-history');
 for(const [n,ms]of Object.entries(targets)){const fewest=Math.abs(ms[0].target[0]-ms[0].start[0])+Math.abs(ms[0].target[1]-ms[0].start[1]),reached=ms.some(m=>m.reached);const item=personalElement('div');item.append(personalElement('strong',`Target ${n}: ${reached?'reached':'not reached'}`),personalElement('small',`${ms.length} moves · fewest possible ${fewest}`));list.append(item)}
 if(!moves.length)list.append(personalElement('p','No cursor moves were made in this recording.'));
 panel.append(list);
 if(moves.length){const decided=moves.filter(m=>m.direction!==null),toward=decided.filter(m=>m.toward).length,chance=decided.reduce((t,m)=>t+m.helpful/4,0);panel.append(personalElement('p',`Moves toward the target: ${toward} / ${decided.length} · random moves would give about ${chance.toFixed(1)}`))}
 panel.append(personalElement('h3',v.length?`${(100*correct/v.length).toFixed(1)}% moves correctly classified`:'Calibration was not completed.'),personalElement('p',v.length?`${correct} / ${v.length} held-out calibration moves · random guessing 25%`:'Complete calibration to measure accuracy.'));
 if(s.cursor_quality){const quality=s.cursor_quality;const note=personalElement('p',`Attended/unattended AUC: ${quality.auc===null?'unavailable':quality.auc.toFixed(2)} · about ${quality.bits_per_minute.toFixed(1)} bits/min at ${Math.round(quality.seconds_per_move)} s per move · ${quality.message}`);note.title=quality.rule;panel.append(note);}
 if(s.cursor_retrospective)panel.append(personalElement('p','Reanalysed calibration from the saved recording.','muted'));
}
