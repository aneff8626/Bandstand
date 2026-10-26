/* Writing acquisition is scoped to Run; headset display controls do not stop EEG. */
let journeyReady=false,journeyStarting=false,journeyLastBrief='',journeyRun=false;
function journeySetup(){return $(document.body.classList.contains('personal-view')?'personalSetup':typingView?'writingParadigm':'experimentParadigm')}
function journeyResults(){return $(document.body.classList.contains('personal-view')?'personalResults':typingView?'writingResults':'experimentResults')}
let journeyStep='headset',journeyFreshResult=false,journeyLeavingTyping=false;
function journeySetStep(step){
 if(!journeyReady)return;
 if(step!=='run'&&state?.typing?.running){void leaveTypingRun(step);return}
 journeyStep=step;document.body.dataset.journeyStep=step;document.body.classList.remove('results-browser');
 $('headsetSetup').open=true;journeySetup().open=true;
 if(step==='summary'||step==='run'&&typingView)journeyResults().open=true;
 arrangeWritingWorkspace(step);if(step==='summary')ensureResultsNavigation();
 for(const b of document.querySelectorAll('#journeySteps button'))b.setAttribute('aria-current',b.dataset.step===step?'step':'false');
}
async function journeyGo(step){
 if(typeof spellerRunning!=='undefined'&&spellerRunning&&step!=='run'){toast('End & save spelling before leaving Run.');return}
 if(['setup','run'].includes(step)&&chosenActivityTitle==='P300 speller'&&!spellerRunning){prepareSpeller();if(step==='run')await startSpeller();return}
 if(typingStarting){toast('Starting recording — please wait.');return}
 if(step!=='run'&&state?.typing?.running){await leaveTypingRun(step,true);return}
 if(['setup','run'].includes(step)&&!chosenActivityTitle){toast('Select an activity first.');return}
 if(step==='run'){if(!journeyRun&&!typingView&&document.body.dataset.area==='lab'){preflightOverride=true;await beginRun();return}journeySetStep(journeyRun||typingView?'run':'setup');return}
 if(step==='summary'&&(!journeyFreshResult||typingView)){showResultsBrowser();return}
 if(step==='headset'||step==='summary'){journeySetStep(step);return}
 if(!personalLeave())return;
 if(step==='choose'){if(document.body.dataset.area==='lab'){labTypeChosen=true;buildProtocols();showLabStep('choose')}else personalRoute(document.body.dataset.area||'insights')}
 else if(step==='setup'){if(document.body.dataset.area==='trainer'){show('developerPanel');}else if(document.body.dataset.area==='lab')showLabStep('settings');else if(!typingView){if(!activityResume[document.body.dataset.area]){toast('Choose an activity first.');return}activityResume[document.body.dataset.area]()}}
 journeySetStep(step);window.scrollTo({top:0,behavior:'smooth'});
}
// Step buttons keep their plain text ("4 Run"); the number gets its own badge for styling.
function setJourneyStepLabel(button,text){
 if(button.textContent===text&&button.querySelector('.step-number'))return;
 const [number,...words]=text.split(' '),badge=document.createElement('span'),name=document.createElement('span');badge.className='step-number';badge.textContent=number;name.className='step-name';name.textContent=words.join(' ');button.replaceChildren(badge,' ',name);
}
function initJourney(){
 document.body.classList.add('journey-theme');
 const header=document.createElement('div');header.id='journeyHeader';header.innerHTML='<strong class="journey-brand"><img src="/bandstand-logo.png" alt=""> Bandstand</strong><nav aria-label="Recording workflow" id="journeySteps"></nav><div id="journeyAccount"></div>';
 for(const [id,label]of [['headset','1 Headset'],['choose','2 Activity'],['setup','3 Setup'],['run','4 Run'],['summary','5 Results']]){const b=personalButton(label,()=>journeyGo(id));setJourneyStepLabel(b,label);b.dataset.step=id;header.querySelector('nav').append(b)}
 const branch=document.createElement('div');branch.id='activityBranch';branch.innerHTML='<span id="activityBranchName">Selected activity</span><div></div>';header.querySelector('nav').append(branch);for(const id of ['setup','run'])branch.lastChild.append(header.querySelector('[data-step='+id+']'));
 const resultsArrow=document.createElement('span');resultsArrow.className='results-step-arrow';resultsArrow.textContent='›';resultsArrow.setAttribute('aria-hidden','true');header.querySelector('nav').append(resultsArrow,header.querySelector('[data-step=summary]'));
 const account=$('accountNav'),contribute=$('contributeNav');header.querySelector('#journeyAccount').append(account,contribute);document.body.prepend(header);new ResizeObserver(()=>document.documentElement.style.setProperty('--journey-header-height',header.getBoundingClientRect().height+'px')).observe(header);
 const areas=document.querySelector('.area-navigation');areas.id='journeyAreas';areas.setAttribute('aria-label','Activity collection');
 for(const b of areas.children){b.replaceChildren(activityCategoryIcon(b.dataset.area),document.createTextNode({lab:'Learn about your brain',insights:'Learn about your mind',bci:'BCI',growth:'Growth exercises',trainer:'Artifact trainer'}[b.dataset.area]));const original=b.onclick;b.onclick=async()=>{await original();journeyFreshResult=false;chosenActivityTitle='';if(b.dataset.area==='lab'){labTypeChosen=true;buildProtocols();showLabStep('choose')}journeySetup().open=true;journeySetStep('choose');journeyTick()}}
 $('headsetSetup').after(areas);
 const participant=document.createElement('details');participant.id='participantSetup';participant.className='settings-disclosure';participant.innerHTML='<summary><button type="button" id="participantDataToggle" aria-expanded="false"><span id="participantSetupLabel">Add participant data</span> <small>(optional)</small></button></summary><div class="form-grid"><label>Subject ID or name<input id="participantName" maxlength="120" autocomplete="off" placeholder="An ID is preferred"></label><label>Age<input id="participantAge" type="number" min="0" max="120"></label><label>Gender<input id="participantGender" maxlength="80"></label><label>Handedness<select id="participantHand"><option value="">Not specified</option><option>Right</option><option>Left</option><option>Both</option></select></label></div><fieldset><legend>Forms before the task</legend><label><input type="checkbox" value="extraversion"> Extraversion · 10 IPIP items</label><label><input type="checkbox" value="big5"> Big Five · 50 IPIP items</label><label><input type="checkbox" value="enneagram"> Enneagram · extended questionnaire (unvalidated)</label></fieldset><p class="muted">Forms appear in the activity screen and can be skipped. Form completion is a preparation phase; task recording starts afterward.</p>';
 const participantInfo=headsetHelp('Participant data',[personalElement('p','These details and answers are saved locally, separately from shared ERP data.')]);participantInfo.addEventListener('click',event=>{event.preventDefault();event.stopPropagation()});participant.append(participantInfo);const participantToggle=participant.querySelector('#participantDataToggle');participantToggle.onclick=event=>{event.preventDefault();participant.open=!participant.open;};participant.addEventListener('toggle',()=>participantToggle.setAttribute('aria-expanded',String(participant.open)));
 journeySetup().append(participant);
 const dock=document.createElement('section');dock.id='eegDock';dock.setAttribute('aria-label','Live EEG monitor');dock.innerHTML='<div class="dock-heading"><span id="dockState" role="status">Starting EEG service…</span><button id="dockToggle" aria-expanded="true">Hide EEG</button></div><div id="dockSignal"></div>';
 dock.querySelector('#dockSignal').append(createHeadsetMap('Open headset setup',()=>{if(!state||state.stale||$('dockSignal')?.querySelector('.map-disconnected')){const button=$('connectMuse');if(button&&!button.disabled)button.click();else toast('Preparing Bluetooth — please wait.')}else journeyGo('headset')}));header.insertBefore(dock,header.querySelector('#journeyAccount'));
 $('dockToggle').onclick=()=>{const hidden=!$('dockSignal').hidden;$('dockSignal').hidden=hidden;$('dockToggle').textContent=hidden?'Show EEG':'Hide EEG';$('dockToggle').setAttribute('aria-expanded',String(!hidden));document.body.classList.toggle('eeg-view-hidden',hidden)};
 const brief=document.createElement('div');brief.id='journeyBrief';brief.innerHTML='<h2 id="briefTitle"></h2><p id="briefTask"></p><p id="briefDuration" class="muted"></p><div class="brief-actions"><button id="briefAdvanced">Advanced controls</button><button id="briefProtocol">Additional protocol details</button></div>';
 document.querySelector('.setup').prepend(brief);$('briefAdvanced').onclick=event=>{event.preventDefault();const panel=$('advancedSettings');panel.open=!panel.open;};$('briefProtocol').onclick=()=>$('expectedResults').closest('dialog').showModal();
 // Make both recording displays visible by default, while retaining one-click hiding.
 $('stage').classList.remove('results-collapsed');$('liveResultsToggle').textContent='Hide EEG & analysis';$('liveResultsToggle').setAttribute('aria-expanded','true');
 $('headsetSetup').open=true;labTypeChosen=true;buildProtocols();
 initWritingRunWorkspace();initHeadsetDisplay();initLabSetupSequence();journeyReady=true;journeySetStep('headset');journeyTick();setInterval(journeyTick,300);
}
function journeyTick(){
 if(!journeyReady||journeyLeavingTyping)return;
 const running=Boolean(active||personalBusy||state?.typing?.running||state?.developer?.recording);
 if(running&&!journeyRun){journeyFreshResult=false;journeySetStep('run');$('dockSignal').hidden=false;$('dockToggle').textContent='Hide EEG';$('dockToggle').setAttribute('aria-expanded','true');document.body.classList.remove('eeg-view-hidden');$('stage').classList.remove('results-collapsed')}
 if(!running&&journeyRun){journeyFreshResult=true;if(!typingView)journeySetStep('summary')}
 journeyRun=running;
 updateActivityBranch();
 const setup=journeySetup(),participant=$('participantSetup'),slot=journeyStep==='setup'?(document.body.classList.contains('personal-view')?$('participantSequenceSlot'):!typingView?$('labParticipantSequenceSlot'):null):null,target=slot||setup;if(participant.parentElement!==target)target.append(participant);$('participantSetupLabel').textContent='Add participant data';
 for(const input of participant.querySelectorAll('input,select'))input.disabled=running||journeyStarting;
 for(const input of participant.querySelectorAll('input[type=checkbox]')){const automatic=({big5:'Big Five',enneagram:'Enneagram'})[input.value]===chosenActivityTitle;if(automatic){if(!input.dataset.automatic)input.dataset.previous=String(input.checked);input.checked=true;input.disabled=true;input.dataset.automatic='true';input.title='Included automatically during this activity';}else if(input.dataset.automatic){input.checked=input.dataset.previous==='true';delete input.dataset.automatic;input.title='';}}
 const contribute=$('contributeNav');contribute.hidden=!contribute.classList.contains('needs-choice');
 const name=!state?'Starting EEG service…':state?.source==='simulation'?'Demo EEG':state&&!state.stale?'Live EEG · 4 channels':'Waiting for EEG';if($('dockState').textContent!==name)$('dockState').textContent=name;
 const runButton=document.querySelector('[data-step="run"]');runButton.disabled=!chosenActivityTitle;setJourneyStepLabel(runButton,running?'4 Recording ●':'4 Run');runButton.classList.toggle('step-recording',running);
 drawHeadsetMaps();
 const connection=$('connectMuse');if(state&&!state.stale){connection.textContent=state.source==='simulation'?'◉ Demo':'● Streaming';connection.title='Device connected, streaming'}
 if(protocol){const design=['custom','custom_erp'].includes(protocol.id)?customDraft(protocol):null;const key=protocol.id+'/'+$('trialCount').value+JSON.stringify(design);if(key!==journeyLastBrief){journeyLastBrief=key;$('briefTitle').textContent=protocol.title;$('briefTask').textContent=participantInstruction(protocol.id);const duration=design?(design.conditions.length*design.repetitions*(design.duration_ms+design.interval_ms)+(design.break_every?Math.floor((design.conditions.length*design.repetitions-1)/design.break_every)*design.break_ms:0))/60000:(Number($('trialCount').value)||protocol.trials)*((protocol.stim_ms[0]+protocol.stim_ms[1]+protocol.isi_ms[0]+protocol.isi_ms[1])/2)/60000+(protocol.mode==='erp'?Math.floor(((Number($('trialCount').value)||protocol.trials)-1)/40)/6:0)+2/60;$('briefDuration').textContent='Time: about '+Math.max(1,Math.ceil(duration))+(Math.max(1,Math.ceil(duration))===1?' minute':' minutes')+(protocol.mode==='erp'?' · ERP':' · Spectral power')}}
}
async function journeyCapture(path,body){

 if(journeyStarting)throw Error('Preparing recording — please wait.');
 journeyStarting=true;
 try{
  if(!await runInstructionGate(path,body))throw Error('Recording cancelled.');
  const fields={subject:$('participantName')?.value.trim()||'',age:$('participantAge')?.value||'',gender:$('participantGender')?.value.trim()||'',handedness:$('participantHand')?.value||''};
  const forms=[...document.querySelectorAll('#participantSetup input[type=checkbox]:checked')].map(e=>e.value).filter(kind=>!(path==='personal/start'&&kind===body.kind));
  const answers=forms.length?await journeyForms(forms):[];
  if(answers===null)throw Error('Recording cancelled.');
  const context=Object.values(fields).some(Boolean)||forms.length?await rawApi('personal/context',{fields,forms:answers}):null;
  if(path==='start')await syncClock();
  const result=await rawApi(path,body);
  if(context)try{await rawApi('personal/context-link',{context_id:context.id,session_id:result.id||result.session?.id||result.session_id||'',kind:path})}catch(e){toast('Recording started; participant-link save failed: '+e.message)}
  return result;
 }catch(e){journeySetStep('setup');throw e}finally{journeyStarting=false}
}
function journeyForms(forms){
 return new Promise(resolve=>{
  const d=document.createElement('dialog');d.className='run-forms';d.innerHTML='<h2>Before your task</h2><p>Optional forms · skip any question or the whole form. EEG preview is live; task recording starts after the forms.</p><div class="form-eeg"></div><h3></h3><p class="form-question"></p><div class="form-answers"></div><div class="button-row"></div>';
  addActivityPreview(d.querySelector('.form-eeg'));
  let f=0,q=0,results=[],values=[],done=false;
  const finish=value=>{if(done)return;done=true;d.close();d.remove();resolve(value)};
  const nextForm=skipped=>{results.push({kind:forms[f],answers:values,skipped});f++;q=0;values=[];draw()};
  const draw=()=>{if(f>=forms.length){finish(results);return}const kind=forms[f],items=personalCatalog.questionnaires[kind];d.querySelector('h3').textContent=kind==='enneagram'?'Enneagram (unvalidated)':kind==='big5'?'Big Five · IPIP':'Extraversion · IPIP';d.querySelector('.form-question').textContent=`${q+1} / ${items.length} · ${items[q].text}`;const choices=d.querySelector('.form-answers');choices.replaceChildren();['Very inaccurate','Moderately inaccurate','Neither','Moderately accurate','Very accurate'].forEach((label,i)=>choices.append(personalButton(label,()=>{values[q]=i+1;q++;if(q===items.length)nextForm(false);else draw()})));const controls=d.querySelector('.button-row');controls.replaceChildren(personalButton('Cancel recording',()=>finish(null)),personalButton('Skip form',()=>nextForm(true)),personalButton('Skip question',()=>{values[q]=null;q++;if(q===items.length)nextForm(false);else draw()}));};
  d.addEventListener('cancel',e=>{e.preventDefault();finish(null)});document.body.append(d);d.showModal();draw();
 });
}

function createHeadsetMap(label,action){
 const el=document.createElement(action?'button':'div');el.className='headset-map';el.setAttribute('aria-label',label);if(action){el.type='button';el.onclick=action}
 el.innerHTML='<svg viewBox="0 0 240 155" role="img" aria-label="Four-electrode headset, viewed from above"><path class="head-outline" d="M108 22l12-12 12 12c39 5 61 33 61 65s-24 57-73 57-73-25-73-57 22-60 61-65z"/><path class="head-band" d="M48 93C45 10 195 10 192 93"/><path class="head-outline" d="M47 78c-15-10-15 29 2 28M193 78c15-10 15 29-2 28"/>'+[['TP9',50,99,22,126],['AF7',82,42,58,24],['AF8',158,42,158,24],['TP10',190,99,195,126]].map(([ch,x,y,tx,ty])=>`<g data-electrode="${ch}"><circle class="artifact-ring" cx="${x}" cy="${y}" r="14"/><circle class="electrode-glow" cx="${x}" cy="${y}" r="10"/><text x="${tx}" y="${ty}">${ch}</text><title>${electrodeLabel(ch)}: waiting for EEG</title></g>`).join('')+'<path class="map-bluetooth" d="M115 67l17 16-12 11V61l12 11-17 16"/></svg>';
 return el;
}
let mapLastSample=null,mapLastChange=0;
function drawHeadsetMaps(){
 const trace=state?.trace,end=trace?.times?.at(-1),fresh=Number.isFinite(end);if(fresh&&end!==mapLastSample){mapLastSample=end;mapLastChange=performance.now()}const live=state&&!state.stale&&fresh&&performance.now()-mapLastChange<2000;document.querySelectorAll('.headset-map').forEach(m=>{m.classList.toggle('map-disconnected',!live);if(m.closest('#eegDock')){m.title=live?'EEG streaming · open headset setup':'No current EEG · connect Bluetooth';m.setAttribute('aria-label',m.title)}});
 for(const node of document.querySelectorAll('[data-electrode]')){
  const ch=node.dataset.electrode,index=boot?.channels.indexOf(ch);let sum=0,total=0,n=0;
  if(live&&index>=0)for(let i=trace.times.length-1;i>=0&&trace.times[i]>=end-.25;i--){const v=trace.values[i]?.[index];if(Number.isFinite(v)){sum+=v*v;total+=v;n++}}
  const rms=n?Math.sqrt(Math.max(0,sum/n-(total/n)**2)):0,level=n?Math.min(3,Math.max(.03,rms/8)):.03;
  const glow=node.querySelector('.electrode-glow');glow.style.fill=typeof colors!=='undefined'?colors[index]:'#346a9d';glow.style.filter=`saturate(${live?level:0})`;
  const artifact=live&&(state.artifact_regions||[]).some(r=>r.channels?.includes(ch)&&r.onset<=end&&r.offset>=end-.2);
  glow.style.opacity=!live?.08:artifact?.25:1;node.classList.toggle('has-artifact',!!artifact);node.querySelector('title').textContent=ch+(n?': '+rms.toFixed(1)+' µV RMS'+(artifact?' · recent artifact':''):': no current signal');
 }
}
function headsetHelp(label,nodes){
 const button=personalButton('?',()=>dialog.showModal());button.className='info-dot';button.title=label;button.setAttribute('aria-label',label);
 const dialog=document.createElement('dialog');dialog.className='plain-help';const title=document.createElement('h2');title.textContent=label;dialog.append(title,...nodes,personalButton('Close',()=>dialog.close()));document.body.append(dialog);button._helpDialog=dialog;button.addEventListener('click',event=>event.stopPropagation());
 queueMicrotask(()=>{const previous=button.previousElementSibling;if(previous?.classList.contains('info-dot')&&previous._helpDialog){const target=previous._helpDialog,close=target.lastElementChild;target.insertBefore(personalElement('h3',label),close);for(const node of nodes)target.insertBefore(node,close);previous.setAttribute('aria-label','More information');previous.title='More information';button.remove();dialog.remove()}});return button;
}
function initHeadsetDisplay(){
 const panel=$('signalPanel'),row=panel.querySelector('.signal-help-row');
 document.body.classList.add('show-raw-eeg');
 const map=createHeadsetMap('Live EEG amplitude by electrode');map.id='headsetAmplitude';map.hidden=true;$('traceScaleLabel').after(map);
 const oldContact=[...row.children].find(d=>d.querySelector('summary')?.textContent==='Electrode contact'),oldSignal=[...row.children].find(d=>d.querySelector('summary')?.textContent==='Signal details');
 const scale=$('displayScale').closest('label'),filters=panel.querySelector('.display-filter-controls');
 const toolbar=document.createElement('div');toolbar.className='signal-toolbar';
 const contactNodes=oldContact?[...oldContact.querySelector('.signal-help-body').children].filter(n=>!n.textContent.includes('Click an electrode')):[];
 const contactHead=document.createElement('div');contactHead.className='contact-help-row';contactHead.append(headsetHelp('Estimated electrode contact',contactNodes));$('contactReadout').before(contactHead);
 const motion=$('motionReadout');motion.hidden=true;map.after(motion);const motionPlot=document.createElement('canvas');motionPlot.id='motionTrace';motionPlot.height=260;motionPlot.hidden=true;motion.after(motionPlot);
 scale.remove();
 const detail=document.createElement('div');detail.innerHTML='<p>Reference: FPz. Separate reference/ground traces are unavailable.</p><p>Dotted edges indicate off-scale voltage. Artifact labels are estimates; events under 150 ms are hidden but retained.</p>';
 const loss=$('loss');if(loss){const line=document.createElement('p');line.append(loss);detail.append(line)}
 const signalNodes=[detail];
 toolbar.append(headsetHelp('Signal details',signalNodes));
 const settings=document.createElement('aside');settings.id='headsetDisplaySettings';settings.hidden=true;settings.className='display-settings-dialog';settings.innerHTML='<h2>Display settings</h2><label class="setting-switch"><input id="showHeadset" type="checkbox"> Show 2D scalp view</label><label class="setting-switch"><input id="showMotion" type="checkbox"> Show rotation / acceleration</label><h3>Display filters</h3><div id="displayFiltersSlot"></div>';
 settings.querySelector('#displayFiltersSlot').append(filters);scale.hidden=true;panel.append(scale);
 const motionHelp=document.createElement('p');motionHelp.textContent='Motion traces use 0.5-second display smoothing, a 150 ms playback buffer, and smoothly adjusting scales. Recorded motion and artifact detection are unchanged. Acceleration includes gravity.';settings.querySelector('#showMotion').closest('label').after(headsetHelp('Motion display',[motionHelp]));
 const filterHelp=document.createElement('p');filterHelp.textContent='Display only; recorded data and analysis filters are unchanged.';settings.querySelector('h3').append(headsetHelp('Display filters',[filterHelp]));
 const traceGroup=document.createElement('div');traceGroup.className='trace-and-settings';const traceColumn=document.createElement('div');traceColumn.className='trace-column';$('trace').before(traceGroup);traceGroup.append(traceColumn,settings);for(const el of [$('trace'),$('traceEmpty'),$('traceScaleLabel'),map,motion,motionPlot])traceColumn.append(el);
 const toggleSettings=visible=>{settings.hidden=!visible;traceGroup.classList.toggle('settings-open',visible);window.dispatchEvent(new Event('resize'))};
 settings.append(personalButton('Close',()=>toggleSettings(false)));
 const open=personalButton('Display settings',()=>toggleSettings(settings.hidden));open.className='text-action';toolbar.prepend(open);
 const trace=$('trace');let drag=null;
 trace.addEventListener('pointerdown',e=>{if(e.clientX-trace.getBoundingClientRect().left>40)return;drag={y:e.clientY,value:Number($('displayScale').value)||75};trace.setPointerCapture(e.pointerId);trace.style.cursor='grabbing';e.preventDefault()});
 trace.addEventListener('pointermove',e=>{if(!drag){trace.style.cursor=e.clientX-trace.getBoundingClientRect().left<=40?'grab':'default';return}const value=Math.max(5,Math.min(2000,drag.value*Math.exp((e.clientY-drag.y)/120)));const select=$('displayScale');let option=select.querySelector('[data-drag]');if(!option){option=document.createElement('option');option.dataset.drag='true';select.append(option)}option.value=value;select.value=String(value);$('traceScaleLabel').textContent='±'+value.toFixed(1)+' µV per channel';drawTrace()});
 const stop=()=>{drag=null;trace.style.cursor='grab'};trace.addEventListener('pointerup',stop);trace.addEventListener('pointercancel',stop);trace.style.touchAction='none';
 const mapExplanation=document.createElement('p');mapExplanation.textContent='Dots match the voltage-trace colors. Color saturation follows the variation around the mean over the latest 250 ms; it reaches full display saturation at 24 µV. This removes a constant baseline from the display indicator only. Recent artifacts fade the dot; clean samples restore full opacity. No animation is generated when samples stop. A faint red ring marks a recent artifact. Saturation is not contact quality or a brain-state score.';const scalpHelp=headsetHelp('2D scalp view',[mapExplanation]);map.append(scalpHelp);
 $('showHeadset').onchange=()=>map.hidden=!$('showHeadset').checked;$('showMotion').onchange=()=>{motionPlot.hidden=!$('showMotion').checked;drawMotionTraces()};
 initLiveSpectrum(traceColumn);row.replaceChildren(toolbar);
 $('start').onclick=()=>{preflightOverride=true;preflightContactRejected=false;void beginRun()};
 $('briefTask').hidden=true;const instructionToggle=personalButton('Click for instructions',()=>{$('briefTask').hidden=!$('briefTask').hidden;instructionToggle.setAttribute('aria-expanded',String(!$('briefTask').hidden))});instructionToggle.setAttribute('aria-expanded','false');instructionToggle.setAttribute('aria-controls','briefTask');$('briefTask').before(instructionToggle);
 const next=personalButton('Choose an activity →',()=>journeyGo('choose'));next.className='primary';next.id='headsetNext';$('headsetSetup').append(next);
 $('disconnectMuse').textContent='Disconnect';$('disconnectMuse').title='Disconnect headset';
}

function drawMotionTraces(){
 const el=$('motionTrace');if(!el||el.hidden)return;const {ctx,w,h}=canvas('motionTrace'),end=now()-.15,series=state?.motion_trace||{};
 for(const [i,key,label,unit] of [[0,'gyro','Rotation','°/s'],[1,'acc','Acceleration','g']]){
 const rows=smoothMotionRows(key,series[key]||[]).filter(r=>r[0]>=end-8&&r[0]<=end),top=i*h/2+22,bottom=(i+1)*h/2-24,mid=(top+bottom)/2;
 const max=smoothMotionScale(key,Math.max(key==='gyro'?10:1.2,...rows.flatMap(r=>r[1].map(Math.abs))));text(ctx,label+' · XYZ · ±'+max.toFixed(1)+' '+unit,2,i*h/2+12);
 for(let t=0;t<=8;t++){const x=42+t*(w-55)/8;line(ctx,[[x,top],[x,bottom]],'#e5e9ef');text(ctx,(t-8)+'s',x-5,bottom+15)}line(ctx,[[42,mid],[w-13,mid]],'#d4dce5');
 if(!rows.length||end-rows.at(-1)[0]>1){text(ctx,'Waiting for motion sensor data',48,mid);continue}
 ctx.save();ctx.beginPath();ctx.rect(42,top,w-55,bottom-top);ctx.clip();for(let axis=0;axis<3;axis++)line(ctx,rows.map(r=>[42+(r[0]-end+8)*(w-55)/8,mid-r[1][axis]*(bottom-top)/(2*max)]),['#198574','#c78e48','#679bb1'][axis],1);ctx.restore();
 }
}

function initLiveSpectrum(column){
 const nav=document.createElement('div');nav.className='live-view-tabs';nav.setAttribute('aria-label','Headset visualization');
 const area=document.createElement('section');area.id='liveSpectrum';area.hidden=true;
 area.innerHTML='<div class="spectrum-controls"><label>Recent window<select id="spectrumWindow"><option>2</option><option>4</option><option selected>8</option><option>16</option><option>30</option></select> seconds</label></div><p id="spectrumStatus" class="muted"></p><div id="groupedSpectra"><canvas id="combinedSpectrum" height="300" aria-label="Power spectral density by electrode"></canvas><canvas id="pairedSpectrum" height="300" hidden></canvas></div><div class="spectrum-grid"></div>';
 const help=document.createElement('p');help.textContent='Recomputed every 250 ms, with approximately 0.5-second visual smoothing of curves. The Y-axis is set from the first available samples and stays fixed as power changes; larger values clip at the top. Changing visible electrodes or frequency bands sets a new scale. Display smoothing does not change recordings or analysis. Uses 2-second Hann windows with 50% overlap, on the 60 Hz notched signal before the EEG display bandpass. PSD is in µV²/Hz; band power is in µV². Gaps are omitted per electrode. Other artifacts remain included and can raise power; this is a live monitor, not an artifact-cleaned result. The recent window selects how many seconds of EEG contribute; during startup, the available duration may be shorter. A longer recent window smooths the estimate. Gamma is particularly sensitive to muscle activity.';
 const layout=document.createElement('label');layout.id='spectrumLayout';layout.innerHTML='Group <select id="spectrumGrouping"><option value="all">All electrodes</option><option value="lr">Left / Right</option><option value="ft">Frontal / Temporal</option><option value="separate">Separate electrodes</option></select>';layout.querySelector('select').onchange=drawLiveSpectrum;area.querySelector('.spectrum-controls').append(layout,headsetHelp('Live spectral estimates',[help]));
 const bandGroup=personalButton('Group by frequency bands',()=>{const grouped=bandGroup.getAttribute('aria-pressed')!=='true';bandGroup.setAttribute('aria-pressed',String(grouped));bandGroup.textContent=grouped?'Display all frequency values':'Group by frequency bands';drawLiveSpectrum()});bandGroup.id='bandGrouping';bandGroup.setAttribute('aria-pressed','false');area.querySelector('.spectrum-controls').append(bandGroup);
 const bandControls=document.createElement('div');bandControls.id='spectrumBandControls';area.querySelector('.spectrum-controls').after(bandControls);renderBandControls();
 for(const ch of electrodeNames(boot.channels)){const card=document.createElement('div');electrodeGridPosition(card,ch);const plot=document.createElement('canvas');plot.id='liveSpectrum'+ch;plot.height=190;card.append(plot);area.querySelector('.spectrum-grid').append(card)}
 const change=kind=>{const spectral=kind==='spectral';area.hidden=!spectral;const legend=$('signalPanel').querySelector('.artifact-key');if(legend)legend.hidden=spectral;$('trace').hidden=spectral;$('traceScaleLabel').hidden=spectral;$('traceEmpty').classList.toggle('spectral-hidden',spectral);for(const b of nav.children)b.setAttribute('aria-pressed',String(b.dataset.view===kind));drawLiveSpectrum();if(!spectral)drawTrace()};
 for(const [kind,label] of [['voltage','Voltage'],['spectral','Power spectrum']]){const b=personalButton(label,()=>change(kind));b.dataset.view=kind;b.setAttribute('aria-pressed',String(kind==='voltage'));nav.append(b)}column.prepend(nav);$('traceScaleLabel').after(area);renderBandControls();$('spectrumWindow').onchange=drawLiveSpectrum;
}
function drawLiveSpectrum(){
 if(!$('liveSpectrum')||$('liveSpectrum').hidden)return;
 const seconds=$('spectrumWindow').value,data=smoothSpectrum(state?.stale?null:state?.live_spectra?.[seconds],seconds),bands=$('bandGrouping').getAttribute('aria-pressed')==='true';
 $('spectrumStatus').textContent=state?.stale?'Waiting for live EEG':data?'':'Collecting at least 2 seconds of continuous EEG…';$('spectrumStatus').hidden=!$('spectrumStatus').textContent;
 const grouping=$('spectrumGrouping').value,combined=grouping!=='separate';$('spectrumLayout').hidden=false;$('groupedSpectra').hidden=!combined;$('liveSpectrum').querySelector('.spectrum-grid').hidden=combined;
 if(combined){const groups=spectrumGroups(grouping);$('pairedSpectrum').hidden=groups.length<2;groups.forEach((g,i)=>(bands?drawCombinedBands:drawCombinedSpectrum)(data,i?'pairedSpectrum':'combinedSpectrum',g.channels,g.label,i===0));return}
 const labels=['δ 1–4','θ 4–8','α 8–13','β 13–20','β 20–30','γ 30–40'];
 boot.channels.forEach((ch,i)=>{const el=$('liveSpectrum'+ch);el.parentElement.hidden=hiddenTraceChannels.has(ch);if(el.parentElement.hidden)return;const {ctx,w,h}=canvas(el.id),entry=data?.channels[i],l=46,r=w-12,t=30,b=h-35;
 text(ctx,electrodeLabel(ch),48,13,colors[i],11);if(bands||i===boot.channels.findIndex(ch=>!hiddenTraceChannels.has(ch)))text(ctx,bands?'µV²':'µV²/Hz',2,13);if(!entry||state?.stale){text(ctx,'Waiting for usable samples',l,65);return}
 const values=bands?entry.bands:entry.psd,max=bands?smoothSpectrumAxis('channel'+i,Math.max(.01,...values.filter((v,j)=>!hiddenSpectrumBands.has(j)))*1.1):psdMaximum(data);if(!bands)drawFrequencyGuides(ctx,l,r,t,b);for(let k=0;k<=3;k++){const y=b-k*(b-t)/3;line(ctx,[[l,y],[r,y]],'#e1e7ee');if(bands||i===boot.channels.findIndex(ch=>!hiddenTraceChannels.has(ch)))text(ctx,(max*k/3).toPrecision(2),1,y+3)}
 if(bands){const visible=visibleBandIndices(),step=(r-l)/Math.max(1,visible.length);visible.forEach((j,position)=>{const v=values[j];ctx.fillStyle=colors[i];ctx.globalAlpha=.75;ctx.fillRect(l+position*step+step*.15,b-Math.min(v/max,1)*(b-t),step*.7,Math.min(v/max,1)*(b-t));ctx.globalAlpha=1;text(ctx,labels[j],l+position*step,b+16,undefined,8)})}
 else{line(ctx,values.map((v,j)=>[frequencyX(data.frequencies[j],l,r),frequencyVisible(data.frequencies[j])?b-Math.min(v/max,1)*(b-t):NaN]),colors[i],1.6);drawFrequencyTicks(ctx,l,r,b)}
 });
}

function finishStartup(){
 if(!journeyReady||!state||!document.body.classList.contains('app-loading'))return;
 if(!active&&!personalBusy&&!state?.typing?.running&&!state?.developer?.recording){chosenActivityTitle='';for(const area of Object.keys(activityResume))delete activityResume[area];}
 updateActivityBranch();journeySetStep(personalBusy&&personalKind==='matrix'?'run':'headset');document.body.classList.remove('app-loading');
}
function startupProblem(message){
 const status=$('startupMessage');if(!status)return;status.dataset.startupError='true';status.textContent='Startup could not finish: '+message;
 for(const d of document.querySelectorAll('dialog[open]'))d.close();
 if(!$('startupRetry')){const retry=personalButton('Retry',()=>location.reload());retry.id='startupRetry';$('startupScreen').append(retry)}
}
setTimeout(()=>{if(document.body.classList.contains('app-loading')&&!$('startupMessage')?.dataset.startupError){$('startupMessage').textContent='Still starting the local service. Bluetooth will be available shortly.'}},8000);

function spectrumGroups(mode){return mode==='lr'?[{label:'Left',channels:['AF7','TP9']},{label:'Right',channels:['AF8','TP10']}]:mode==='ft'?[{label:'Frontal',channels:['AF7','AF8']},{label:'Temporal',channels:['TP9','TP10']}]:[{label:'',channels:['AF7','TP9','AF8','TP10'].filter(ch=>boot.channels.includes(ch))}] }
function drawCombinedSpectrum(data,id='combinedSpectrum',include=boot.channels,title='',labelAxis=true,options={}){
 const {ctx,w,h}=canvas(id),l=48,r=w-15,b=h-36;let t=38;
 const channels=boot.channels.map((ch,i)=>({ch,i,entry:data?.channels[i]})).sort((a,b)=>include.indexOf(a.ch)-include.indexOf(b.ch)).filter(c=>include.includes(c.ch)&&(options.training||options.recorded||!hiddenTraceChannels.has(c.ch)));
 if(labelAxis)text(ctx,'µV²/Hz',2,13);if(title)text(ctx,title,l,12);let legendX=l,legendY=24;channels.forEach(c=>{const label=electrodeLabel(c.ch)+(c.entry?'':' · waiting');ctx.font='10px -apple-system,sans-serif';const width=ctx.measureText(label).width;if(legendX+width>r){legendX=l;legendY+=13}text(ctx,label,legendX,legendY,colors[c.i],10);legendX+=width+18});t=Math.max(t,legendY+15);
 const hidden=options.hiddenBands||hiddenSpectrumBands,visible=f=>{const i=spectrumBandDefinitions.findIndex(([,lo,hi],i)=>f>=lo&&(f<hi||i===5&&f<=hi));return i>=0&&!hidden.has(i)},bands=spectrumBandDefinitions.filter((_,i)=>!hidden.has(i)),total=bands.reduce((sum,[,lo,hi])=>sum+hi-lo,0),rx=f=>l+bands.reduce((sum,[,lo,hi])=>sum+Math.max(0,Math.min(f,hi)-lo),0)/Math.max(1,total)*(r-l);const max=options.recorded?(options.axes[options.key]??=Math.max(.01,...channels.flatMap(c=>(c.entry?.psd||[]).filter((v,j)=>visible(data.frequencies[j]))))*1.15):options.training?smoothSpectrumAxis('feedback-preview',Math.max(.01,...channels.flatMap(c=>c.entry?.psd||[]))*1.1,!!data):psdMaximum(data);const x=f=>options.training?l+f/40*(r-l):options.recorded?rx(f):frequencyX(f,l,r);if(options.recorded){bands.forEach(([name,lo,hi],i)=>{ctx.fillStyle=i%2?'#34567804':'#34567809';ctx.fillRect(x(lo),t,x(hi)-x(lo),b-t);text(ctx,name,(x(lo)+x(hi))/2-10,t+12,'#8796a6',9)})}else if(!options.training)drawFrequencyGuides(ctx,l,r,t,b);
 for(let k=0;k<=4;k++){const y=b-k*(b-t)/4;line(ctx,[[l,y],[r,y]],'#e1e7ee');if(labelAxis)text(ctx,(max*k/4).toPrecision(2),2,y+3)}
 if(options.training||options.recorded){for(const f of (options.recorded?[1,4,8,12,20,30,40].filter(visible):[0,4,8,13,20,30,40]))text(ctx,String(f),x(f)-5,b+16);text(ctx,'Hz',r-12,b+31)}else drawFrequencyTicks(ctx,l,r,b);
 if((!options.recorded&&state?.stale)||!channels.some(c=>c.entry)){text(ctx,channels.length?'Waiting for usable samples':'Select an electrode above',l,65);return}
 if(options.recorded){ctx.save();ctx.beginPath();ctx.rect(l,t,r-l,b-t);ctx.clip();for(const c of channels){if(!c.entry?.ci_low||!c.entry?.ci_high)continue;for(const [,lo,hi]of bands){const ids=data.frequencies.map((f,i)=>f>=lo&&f<=hi?i:-1).filter(i=>i>=0);if(ids.length<2)continue;ctx.beginPath();ids.forEach((j,k)=>{const px=x(data.frequencies[j]),py=b-c.entry.ci_high[j]/max*(b-t);k?ctx.lineTo(px,py):ctx.moveTo(px,py)});[...ids].reverse().forEach(j=>ctx.lineTo(x(data.frequencies[j]),b-c.entry.ci_low[j]/max*(b-t)));ctx.closePath();ctx.fillStyle=colors[c.i];ctx.globalAlpha=.13;ctx.fill()}}ctx.restore()}
 if(options.references?.length){ctx.save();ctx.beginPath();ctx.rect(l,t,r-l,b-t);ctx.clip();for(const reference of options.references){ctx.setLineDash(reference.dash);for(const c of channels){line(ctx,reference.psd[c.i].map((v,j)=>[x(1+j*.5),visible(1+j*.5)?b-Math.min(v/max,1)*(b-t):NaN]),colors[c.i],1.4)}}ctx.restore()}
 for(const c of channels)if(c.entry)line(ctx,c.entry.psd.map((v,j)=>[x(data.frequencies[j]),(options.training||(options.recorded?visible(data.frequencies[j]):frequencyVisible(data.frequencies[j])))?b-Math.min(v/max,1)*(b-t):NaN]),colors[c.i],1.7);
}

const fixedSpectrumAxes={};
let spectrumAnimation={key:null,time:0,data:null,axes:{}};
function smoothSpectrum(target,key,clock=performance.now()){
 if(!target){spectrumAnimation={key:null,time:clock,data:null,axes:{}};return null}
 const old=spectrumAnimation;
 if(old.key!==key||!old.data||clock-old.time>1500){spectrumAnimation={key,time:clock,data:JSON.parse(JSON.stringify(target)),axes:{}};return spectrumAnimation.data}
 const alpha=1-Math.exp(-Math.max(0,clock-old.time)/500);old.time=clock;
 old.data={...target,channels:target.channels.map((entry,i)=>{if(!entry)return null;const previous=old.data.channels[i];if(!previous)return {...entry,psd:[...entry.psd],bands:[...entry.bands]};return {...entry,psd:entry.psd.map((v,j)=>previous.psd[j]+alpha*(v-previous.psd[j])),bands:entry.bands.map((v,j)=>previous.bands[j]+alpha*(v-previous.bands[j]))}})};
 return old.data;
}
function smoothSpectrumAxis(key,target,ready=true){
 // Scale only on an explicit visibility change, never in response to evolving EEG.
 key=$('bandGrouping').getAttribute('aria-pressed')+'/'+key+'/'+[...hiddenSpectrumBands].sort().join(',')+'/'+[...hiddenTraceChannels].sort().join(',');
 if(!ready)return fixedSpectrumAxes[key]||target;
 if(fixedSpectrumAxes[key]===undefined)fixedSpectrumAxes[key]=target;
 return fixedSpectrumAxes[key];
}

function psdMaximum(data){
 return smoothSpectrumAxis('sharedPSD',Math.max(1,...(data?.channels||[]).flatMap((c,i)=>hiddenTraceChannels.has(boot.channels[i])?[]:(c?.psd||[]).filter((v,j)=>frequencyVisible(data.frequencies[j]))))*1.15,Boolean(data?.channels?.some(Boolean)));
}
function drawFrequencyGuides(ctx,l,r,t,b,condensed=true){
 const bands=[['δ',1,4],['θ',4,8],['α',8,13],['Low β',13,20],['High β',20,30],['γ',30,40]];
 ctx.save();ctx.font='10px -apple-system,sans-serif';ctx.textAlign='center';
 bands.forEach(([label,lo,hi],i)=>{if(condensed&&hiddenSpectrumBands.has(i))return;const x=condensed?frequencyX(lo,l,r):l+(lo-1)/39*(r-l),right=condensed?frequencyX(hi,l,r):l+(hi-1)/39*(r-l);ctx.fillStyle=i%2?'rgba(77,108,145,.025)':'rgba(77,108,145,.045)';ctx.fillRect(x,t,right-x,b-t);ctx.fillStyle='rgba(67,89,115,.45)';ctx.fillText(label,(x+right)/2,t+13)});ctx.restore();
}
function visibleBandIndices(){return spectrumBandDefinitions.map((_,i)=>i).filter(i=>!hiddenSpectrumBands.has(i))}
function frequencyX(f,l,r){const indices=visibleBandIndices(),total=indices.reduce((n,i)=>n+spectrumBandDefinitions[i][2]-spectrumBandDefinitions[i][1],0);let distance=0;for(const i of indices){const [,lo,hi]=spectrumBandDefinitions[i];distance+=Math.max(0,Math.min(f,hi)-lo)}return l+distance/Math.max(1,total)*(r-l)}
function drawFrequencyTicks(ctx,l,r,b){
 const ticks=[1,4,8,12,20,30,40].filter(f=>visibleBandIndices().some(i=>{const [,lo,hi]=spectrumBandDefinitions[i];return f>=lo&&f<=hi}));let previous=-Infinity;
 for(const f of ticks){const x=frequencyX(f,l,r);if(x-previous<16)continue;text(ctx,String(f),x-3,b+16);previous=x}
 text(ctx,'Hz',r-12,b+30);
 if(!visibleBandIndices().length)text(ctx,'Restore a frequency band above',l,b-25);
}

function drawCombinedBands(data,id,include,title,labelAxis,options={}){
 const {ctx,w,h}=canvas(id),l=48,r=w-15,b=h-35;let t=55;
 const channels=boot.channels.map((ch,i)=>({ch,i,entry:data?.channels[i]})).sort((a,b)=>include.indexOf(a.ch)-include.indexOf(b.ch)).filter(c=>include.includes(c.ch)&&(options.recorded||!hiddenTraceChannels.has(c.ch)));
 const byBand=true,names=['Delta','Theta','Alpha','Low β','High β','Gamma'],palette=['#839bb2','#8171a8','#3a9a8b','#ba984c','#be805c','#aa708d'];
 if(labelAxis)text(ctx,'µV²',2,13);if(title)text(ctx,title,l,13);
 const legend=byBand?channels.map(c=>[electrodeLabel(c.ch),colors[c.i]]):names.map((n,i)=>[n,palette[i]]);
 let legendX=l,legendY=29;legend.forEach(([n,color])=>{ctx.font='10px -apple-system,sans-serif';const width=ctx.measureText(n).width;if(legendX+width>r){legendX=l;legendY+=13}text(ctx,n,legendX,legendY,color,10);legendX+=width+18});t=Math.max(t,legendY+15);
 const hidden=options.hiddenBands||hiddenSpectrumBands;const max=options.recorded?(options.axes[options.key]??=Math.max(.01,...channels.flatMap(c=>(c.entry?.bands||[]).filter((v,j)=>!hidden.has(j))))*1.15):smoothSpectrumAxis('groupBands',Math.max(1,...(data?.channels||[]).flatMap((c,i)=>hiddenTraceChannels.has(boot.channels[i])?[]:(c?.bands||[]).filter((v,j)=>!hiddenSpectrumBands.has(j))))*1.15,Boolean(data?.channels?.some(Boolean)));
 for(let k=0;k<=4;k++){const y=b-k*(b-t)/4;line(ctx,[[l,y],[r,y]],'#e1e7ee');if(labelAxis)text(ctx,(max*k/4).toPrecision(2),2,y+3)}
 if((!options.recorded&&state?.stale)||!channels.some(c=>c.entry)){text(ctx,channels.length?'Waiting for usable samples':'Select an electrode above',l,80);return}
 const visible=options.recorded?spectrumBandDefinitions.map((_,i)=>i).filter(i=>!hidden.has(i)):visibleBandIndices(),groups=visible.length,step=(r-l)/Math.max(1,groups),count=byBand?channels.length:6,width=step*.78/count;
 for(let g=0;g<groups;g++){const bandIndex=visible[g];
 text(ctx,byBand?names[bandIndex]:channels[g].ch,l+g*step+step*.1,b+17,undefined,10);
 for(let j=0;j<count;j++){const c=byBand?channels[j]:channels[g],band=byBand?bandIndex:j;if(!c.entry)continue;const height=Math.min(1,c.entry.bands[band]/max)*(b-t);ctx.fillStyle=byBand?colors[c.i]:palette[band];ctx.globalAlpha=.8;ctx.fillRect(l+g*step+step*.1+j*width,b-height,width*.85,height);ctx.globalAlpha=1}
 }
}

const motionDisplayCache={};
function smoothMotionRows(key,rows){
 if(!rows.length){delete motionDisplayCache[key];return []}
 let cache=motionDisplayCache[key];
 if(!cache||rows.at(-1)[0]<cache.time||rows[0][0]>cache.time+.25)cache=motionDisplayCache[key]={time:-Infinity,value:null,rows:new Map()};
 for(const [t,value] of rows){if(t<=cache.time)continue;
 const reset=!cache.value||t-cache.time>.25,alpha=reset?1:1-Math.exp(-(t-cache.time)/.5);
 cache.value=value.map((v,i)=>reset?v:cache.value[i]+alpha*(v-cache.value[i]));cache.time=t;cache.rows.set(t,[...cache.value]);
 }
 for(const t of cache.rows.keys())if(t<rows[0][0])cache.rows.delete(t);
 return rows.map(([t,v])=>[t,cache.rows.get(t)||v]);
}
const motionScaleCache={};
function smoothMotionScale(key,target,clock=performance.now()){
 const old=motionScaleCache[key],value=!old||clock-old.time>1500?target:old.value+(1-Math.exp(-Math.max(0,clock-old.time)/500))*(target-old.value);
 motionScaleCache[key]={value,time:clock};return value;
}

const hiddenSpectrumBands=new Set();
const spectrumBandDefinitions=[['Delta',1,4],['Theta',4,8],['Alpha',8,13],['Low beta',13,20],['High beta',20,30],['Gamma',30,40]];
function frequencyVisible(f){const index=spectrumBandDefinitions.findIndex(([,lo,hi],i)=>f>=lo&&(f<hi||i===5&&f<=hi));return index>=0&&!hiddenSpectrumBands.has(index)}
function renderBandControls(){
 const root=$('spectrumBandControls');if(!root)return;root.replaceChildren();
 const row=document.createElement('div');row.className='band-chips';row.setAttribute('aria-label','Frequency band visibility');
 spectrumBandDefinitions.forEach(([name,lo,hi],i)=>{const off=hiddenSpectrumBands.has(i),button=personalButton(name,()=>{hiddenSpectrumBands.has(i)?hiddenSpectrumBands.delete(i):hiddenSpectrumBands.add(i);renderBandControls();drawLiveSpectrum()});button.classList.toggle('band-disabled',off);button.title=(off?'Restore ':'Hide ')+name+' · '+lo+'–'+hi+' Hz';button.setAttribute('aria-pressed',String(!off));row.append(button)});root.append(row);
}

let chosenActivityTitle='';
function updateActivityBranch(){
 const title=chosenActivityTitle;
 if($('activityBranchName'))$('activityBranchName').textContent=title||'Activity not yet selected';
 $('activityBranch')?.classList.toggle('activity-locked',!title);
 for(const step of ['setup','run']){const button=document.querySelector('[data-step="'+step+'"]');button.disabled=!title;button.setAttribute('aria-disabled',String(!title));button.title=title?'':'Select an activity first';}
 journeyResults().querySelector('.result-navigation')?.remove();
}
// Browser history contains opaque view IDs only; session data stays in memory.
let individualSessionReturn=null;const deletedSessionIds=new Set();
const resultsViews=new Map();let resultsViewSequence=0,resultsHistoryIndex=0,resultsReplaying=false,resultsSwipe=0,resultsSwipeAt=0,resultsSwipeCooldown=0;
function rememberResultsView(restore){
 if(resultsReplaying)return;const id=++resultsViewSequence;resultsViews.set(id,restore);
 if(!history.state?.bandstandResults){resultsHistoryIndex=0;history.replaceState({bandstandResults:id,index:0},'')}else{resultsHistoryIndex++;history.pushState({bandstandResults:id,index:resultsHistoryIndex},'')}
 updateResultsBack();
}
function updateResultsBack(){const button=$('resultsBack');if(button)button.disabled=!individualSessionReturn&&resultsHistoryIndex<=0}
function goResultsBack(){if(individualSessionReturn){const restore=individualSessionReturn;individualSessionReturn=null;restore();rememberResultsView(restore);updateResultsBack();return}if(resultsHistoryIndex>0)history.back();else showResultsBrowser('library')}

window.bandstandNavigate=direction=>{if(journeyStep!=='summary')return false;if(direction<0)goResultsBack();else history.forward();return true};
window.addEventListener('mousedown',event=>{if(journeyStep==='summary'&&(event.button===3||event.button===4)){event.preventDefault();event.stopPropagation()}},true);
window.addEventListener('mouseup',event=>{if(journeyStep==='summary'&&(event.button===3||event.button===4)){event.preventDefault();event.stopPropagation();window.bandstandNavigate(event.button===3?-1:1)}},true);
window.addEventListener('auxclick',event=>{if(journeyStep==='summary'&&(event.button===3||event.button===4))event.preventDefault()},true);
window.addEventListener('keydown',event=>{if(journeyStep!=='summary'||event.target.closest('input,textarea,[contenteditable=true]'))return;const back=(event.altKey&&event.key==='ArrowLeft')||(event.metaKey&&event.key==='['),forward=(event.altKey&&event.key==='ArrowRight')||(event.metaKey&&event.key===']');if(back||forward){event.preventDefault();window.bandstandNavigate(back?-1:1)}},true);

window.addEventListener('popstate',async event=>{const saved=event.state,restore=resultsViews.get(saved?.bandstandResults);if(!restore||journeyStep!=='summary')return;resultsHistoryIndex=saved.index||0;resultsReplaying=true;try{await restore()}finally{resultsReplaying=false;updateResultsBack()}});
window.addEventListener('wheel',event=>{
 if(journeyStep!=='summary'||document.querySelector('dialog[open]')||resultsHistoryIndex<=0||event.ctrlKey||event.target.closest('canvas,svg,input,select,textarea,[contenteditable=true]'))return;
 if(Math.abs(event.deltaX)<Math.abs(event.deltaY)*2||Math.abs(event.deltaX)<3)return;
 const now=performance.now();if(now<resultsSwipeCooldown)return;event.preventDefault();if(now-resultsSwipeAt>200)resultsSwipe=0;resultsSwipeAt=now;resultsSwipe+=event.deltaX;
 if(resultsSwipe < -120){resultsSwipe=0;resultsSwipeCooldown=now+800;goResultsBack()}
},{passive:false});
function setResultsNavigation(mode){
 const nav=$('resultsNavigation');if(!nav)return;const combined=mode==='combined';let banner=$('combinedProvisional');if(!banner){banner=personalElement('aside','This section is ultraprovisional — needs much attention.','combined-provisional');banner.id='combinedProvisional';document.querySelector('main').prepend(banner)}banner.hidden=!combined;document.body.dataset.resultsSection=combined?'combined':'individual';
 nav.querySelectorAll('[data-results-tab]').forEach(button=>{const selected=button.dataset.resultsTab===(combined?'combined':'individual');button.setAttribute('aria-pressed',String(selected));button.setAttribute('aria-selected',String(selected))});

}
function ensureResultsNavigation(){
 let nav=$('resultsNavigation');if(!nav){
 nav=personalElement('section');nav.id='resultsNavigation';const tabs=personalElement('div',undefined,'results-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Results');tabs.setAttribute('aria-orientation','vertical');
 for(const [key,label]of [['individual','Browse individual sessions'],['combined','Combined Results']]){const button=personalButton(label,()=>{if(key==='individual'&&individualSessionReturn)goResultsBack();else showResultsBrowser(key==='combined'?'combined':'library')});button.dataset.resultsTab=key;button.setAttribute('role','tab');button.onkeydown=event=>{if(['ArrowUp','ArrowDown','Home','End'].includes(event.key)){event.preventDefault();const buttons=[...tabs.children],at=buttons.indexOf(button),target=buttons[event.key==='Home'?0:event.key==='End'?buttons.length-1:(at+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length];target.focus();target.click()}};tabs.append(button)}
 const toolbar=personalElement('div',undefined,'results-toolbar'),back=personalButton('‹ Back',goResultsBack);back.id='resultsBack';back.title='Previous Results view · swipe right to go back';toolbar.append(back);nav.append(tabs,toolbar);document.querySelector('main').prepend(nav)
 }setResultsNavigation('session');updateResultsBack();return nav;
}


// Conservative browsing heuristics, never a scientific validation or a deletion rule.
function sessionQuality(r){
 const reasons=[],duration=Number(r.ended)-Number(r.created??r.started??r.date),m=r.quality_metrics;
 if(r.synthetic||r.source==='simulation'||r.source==='synthetic-preview')return {category:'test',reason:'Simulated or invented session'};
 if(Number.isFinite(duration)&&duration<60)reasons.push('Less than 60 seconds');
 if(m&&m.usable<10)reasons.push('Fewer than 10 usable EEG clips or trials');
 if(m&&m.total>0&&m.usable/m.total<.5)reasons.push('Fewer than half the clips or trials usable on any channel');
 if(['big5','enneagram','extraversion','matrix'].includes(r.kind)){
  if(m&&m.answers<10)reasons.push('Fewer than 10 answers');
  if(m?.median_answer_seconds!=null&&m.median_answer_seconds<1)reasons.push('Median answer time below one second');
 }
 if(reasons.length)return {category:'test',reason:reasons.join(' · ')};
 const knownSource=['live','muse','ble','bluetooth'].includes(r.source),timingKnown=!['big5','enneagram','extraversion','matrix'].includes(r.kind)||m?.median_answer_seconds!=null;
 if(!knownSource||!Number.isFinite(duration)||!m||!timingKnown)return {category:'review',reason:'Not enough saved quality metadata to classify'};
 return {category:'clean',reason:'Meets the browsing criteria; does not establish artifact-free or valid results'};
}

function mountSessionActions(host,record,onDeleted){
 host.dataset.actionSession=record.id;host.querySelector('.session-actions')?.remove();const header=personalElement('div',undefined,'session-actions'),buttons=personalElement('div',undefined,'button-row');header.append(buttons);
 const readStars=()=>{try{return new Set(JSON.parse(localStorage.getItem('bandstandStarredSessions')||'[]'))}catch{return new Set()}};
 const star=personalButton('',()=>{const stars=readStars();stars.has(record.id)?stars.delete(record.id):stars.add(record.id);localStorage.setItem('bandstandStarredSessions',JSON.stringify([...stars]));updateStar()});
 const updateStar=()=>{const selected=readStars().has(record.id);star.textContent=selected?'★ Starred':'☆ Star';star.setAttribute('aria-pressed',String(selected))};updateStar();buttons.append(star);
 const remove=personalButton('Delete local data',()=>{
  const dialog=personalElement('dialog',undefined,'session-delete-dialog');dialog.setAttribute('aria-label','Delete local session data');dialog.append(personalElement('h2','Delete this session?'),personalElement('p',`${record.title||record.kind} · ${new Date(record.date*1000).toLocaleString()}`),personalElement('p','This permanently removes this session’s local recording, answers, processed data and app-managed exports. Shared ERP copies and files you copied elsewhere are not removed.'));
  if(record.recordType==='writing')dialog.append(personalElement('p','Local decoder caches and learned models will also be cleared and can be rebuilt from your remaining recordings.'));
  const status=personalElement('p');status.setAttribute('role','status');const actions=personalElement('div',undefined,'button-row'),cancel=personalButton('Cancel',()=>dialog.close()),confirm=personalButton('Delete this session',async()=>{confirm.disabled=true;try{await api('sessions/delete',{id:record.id,kind:record.recordType,confirmation:record.id});const stars=readStars();stars.delete(record.id);localStorage.setItem('bandstandStarredSessions',JSON.stringify([...stars]));deletedSessionIds.add(record.id);resultsViews.clear();resultsHistoryIndex=0;history.replaceState({},'');individualSessionReturn=null;selectedResult=null;journeyFreshResult=false;renderRevision='';$('personalResultsBody')?.replaceChildren();$('savedWritingSession')?.replaceChildren();dialog.close();onDeleted();showResultsBrowser('library')}catch(error){status.textContent=error.message;confirm.disabled=false}});confirm.className='danger';actions.append(cancel,confirm);dialog.append(status,actions);dialog.addEventListener('close',()=>dialog.remove(),{once:true});document.body.append(dialog);dialog.showModal();cancel.focus();
 });remove.className='session-delete';remove.disabled=Boolean(record.synthetic||record.importedResult||String(record.id).startsWith('import-'));if(remove.disabled)remove.title='This is an imported or invented preview, not a local recorded session.';buttons.append(remove);
 const summary=host.querySelector(':scope > summary');if(summary)summary.after(header);else host.prepend(header);
}

function showResultsBrowser(initialMode='library'){
 individualSessionReturn=null;document.body.classList.remove('individual-session-open','writing-session-open');
 journeySetStep('summary');document.body.classList.add('results-browser');let panel=$('savedResultsBrowser');if(!panel){panel=personalElement('section',undefined,'panel');panel.id='savedResultsBrowser';document.querySelector('main').append(panel)}buildResultsBrowser(panel,initialMode);
}
function openPreviousActivities(){if(!personalLeave())return;showResultsBrowser('library')}
async function buildResultsBrowser(panel,initialMode='latest'){
 panel.replaceChildren();const nav=personalElement('div'),body=personalElement('div');panel.append(body);body.textContent='Loading saved sessions…';
 try{
 const [catalog,sessions,contexts]=await Promise.all([api('personal/catalog',{}),api('sessions'),api('personal/context-list',{})]);const subjects=contexts.subjects||{};
 const records=[...(mindDemoDatabase.records||[]).map(r=>({...r,recordType:'personal',date:r.created||0,title:r.kind==='big5'?'Big Five':'Enneagram',source:'synthetic-preview',synthetic:true})),...(contexts.writing||[]).map(r=>({...r,recordType:'writing',date:r.started,kind:'writing',title:'Writing decoder'})),...(catalog.history||[]).map(r=>({...r,recordType:'personal',date:r.created,title:({matrix:'Matrix reasoning',big5:'Big Five',enneagram:'Enneagram',meditation:'Meditation',biofeedback:'Biofeedback',reset:'Find your reset'})[r.kind]||r.kind})),...sessions.filter(r=>!r.running).map(r=>({...r,recordType:'lab',date:r.started,kind:r.protocol||r.title}))].map(r=>({...r,subject:subjects[r.id]||r.subject_id||''})).sort((a,b)=>b.date-a.date);
 let browserRefresh=()=>{};
 const open=async r=>{if(deletedSessionIds.has(r.id)){showResultsBrowser('library');return}const browserNodes=[...panel.childNodes],listNodes=[...body.childNodes];const restore=()=>{individualSessionReturn=null;document.body.classList.remove('individual-session-open','writing-session-open');journeySetStep('summary');document.body.classList.add('results-browser');panel.replaceChildren(...browserNodes);body.replaceChildren(...listNodes);setResultsNavigation('library');browserRefresh();window.scrollTo({top:0,behavior:'instant'})};individualSessionReturn=restore;rememberResultsView(()=>open(r));
 try{if(r.recordType==='writing'){let writing=$('savedWritingSession');if(!writing){writing=personalElement('section',undefined,'panel');writing.id='savedWritingSession';document.querySelector('main').append(writing)}const body=writing;body.replaceChildren();body.append(personalElement('h3','Writing decoder'),personalElement('p',`${Math.max(0,(r.ended-r.started)/60).toFixed(1)} minutes recorded`));const metrics=personalElement('div',undefined,'training-score-metrics');for(const [value,label]of [[r.session_metrics?.words??'—','Words recorded'],[r.session_metrics?.usable_words??'—','Usable word epochs'],[Math.max(0,(r.ended-r.started)/60).toFixed(1),'Minutes']]){const metric=personalElement('div');metric.append(personalElement('strong',String(value)),personalElement('span',label));metrics.append(metric)}body.append(metrics);const spectrum=personalElement('p','Decoder performance is evaluated across sessions, not separately for this recording.','muted');body.append(spectrum,personalButton('View cumulative decoder results',()=>{personalRoute('bci','writing');journeyFreshResult=true;journeySetStep('run')}));mountSessionActions(body,r,()=>{deletedSessionIds.add(r.id);showResultsBrowser('library')});document.body.classList.remove('results-browser');document.body.classList.add('individual-session-open','writing-session-open');updateResultsBack();return}
 if(r.recordType==='personal'){personalRoute(['reset','meditation','biofeedback'].includes(r.kind)?'growth':'insights');renderPersonalResult(r)}else{personalRoute('lab');chosenActivityTitle=r.title;selectedResult=r.importedResult||await api('results/'+r.id);renderRevision='';updateResultExports()}
 journeyFreshResult=true;journeySetStep('summary');document.body.classList.remove('writing-session-open');document.body.classList.add('individual-session-open');const target=r.recordType==='personal'?$('personalResultsBody'):$('experimentResults');mountSessionActions(target,r,()=>{deletedSessionIds.add(r.id);selectedResult=null;showResultsBrowser('library')});window.scrollTo({top:0,behavior:'instant'});requestAnimationFrame(()=>{if(r.recordType==='lab'){renderRevision='';render()}target.querySelectorAll('details.insight-disclosure').forEach(d=>d.open=true)});updateResultsBack();
 }catch(error){restore();toast('Could not open session: '+error.message)}};
 const importFiles=document.createElement('input');importFiles.type='file';importFiles.accept='.json,application/json';importFiles.multiple=true;importFiles.hidden=true;panel.append(importFiles);importFiles.onchange=async()=>{try{const additions=[];for(const file of importFiles.files){if(file.size>10*1024*1024)throw Error('Choose JSON session summaries smaller than 10 MB.');const data=JSON.parse(await file.text()),id='import-'+crypto.randomUUID();if(data.session&&data.analysis?.channels){additions.push({id,recordType:'lab',kind:data.session.protocol,title:data.session.title||data.session.protocol||file.name,date:data.session.started||0,source:data.session.source||'imported',subject:data.session.subject_id||'',importedResult:data})}else if(['matrix','big5','enneagram','reset','meditation','biofeedback'].includes(data.kind)&&(data.scores||data.summary)){additions.push({...data,id,recordType:'personal',kind:data.kind,title:data.kind,date:data.created||0,source:data.source||'imported',subject:data.subject_id||''})}else throw Error('Choose an exported ERP result or personal-session summary JSON. Raw EEG and writing files are not supported here.')}records.push(...additions);draw('combined')}catch(error){toast(error.message)}finally{importFiles.value=''}};
 const draw=mode=>{ensureResultsNavigation();setResultsNavigation(mode);body.replaceChildren();for(const b of nav.children)b.setAttribute('aria-pressed',String(b.dataset.mode===mode));
 if(mode==='latest'){const r=records.find(r=>!r.synthetic);if(r){void open(r).then(()=>setResultsNavigation('latest')).catch(error=>toast(error.message))}else body.append(personalElement('p','No saved sessions yet.'));return}
 const controls=personalElement('div',undefined,'results-filters'),activity=document.createElement('select'),subject=document.createElement('select'),source=document.createElement('select'),sort=document.createElement('select'),list=personalElement('div');
 const option=(select,value,text)=>{const o=personalElement('option',text);o.value=value;select.append(o)};
 option(activity,'','All activities');for(const kind of [...new Set(records.map(r=>r.kind))])option(activity,kind,records.find(r=>r.kind===kind).title);
 option(subject,'','All participants');for(const name of [...new Set(records.map(r=>r.subject).filter(Boolean))])option(subject,name,name);option(subject,'__unknown','No participant ID');
 for(const [value,text]of [['','All recorded sources'],['real','Headset recordings'],['simulation','Simulated recordings']])option(source,value,text);
 if(mode==='library')option(source,'examples','Invented examples');option(sort,'new','Newest first');option(sort,'old','Oldest first');for(const [el,label]of [[activity,'Activity'],[subject,'Participant'],[source,'Source'],[sort,'Sort sessions']]){el.setAttribute('aria-label',label);controls.append(el)}const quality=document.createElement('select');quality.setAttribute('aria-label','Recording quality');for(const [value,label]of [['clean','Clean headset recordings'],['test','Test sessions'],['review','Needs review'],['all','All session qualities']])option(quality,value,label);controls.prepend(quality);controls.append(headsetHelp('Session classification',[personalElement('p','Clean is a browsing rule, not scientific validation: at least 60 seconds, 10 usable clips/trials, half usable on one or more channels; questionnaires need 10 answers and median response time of at least one second. Simulated, sparse, short or fast sessions are tests. Unknown metadata needs review.')]));body.append(controls,list);
 const selected=new Set(),combined=personalElement('div'),aggregation=document.createElement('select');aggregation.setAttribute('aria-label','Combine sessions');for(const [v,t]of [['group','Across people'],['within','Within one person / over time']]){const o=personalElement('option',t);o.value=v;aggregation.append(o)}if(mode==='combined'){body.prepend(personalElement('h3','Select saved sessions'));controls.append(aggregation,personalButton('Import files',()=>importFiles.click()))}if(mode==='combined'){body.append(combined);body.append(headsetHelp('How sessions are combined',[personalElement('p','Only matching activities, sources and measurement settings are combined. Each session contributes its summary, not its individual EEG clips. Sessions with the same participant ID are averaged first; records without an ID remain separate and may belong to one person. These are descriptive means and ranges, not group significance tests. Invented personality references are excluded.')]));}
 const proceed=personalButton('Proceed to combined results',async()=>{const selectionNodes=[...body.childNodes];proceed.disabled=true;combined.textContent='Checking session compatibility…';try{const prepared=await prepareCombinedSessions(records.filter(r=>selected.has(r.id)),aggregation.value),nodes=[...body.childNodes],back=()=>{body.replaceChildren(...nodes);refreshCombined()};const show=()=>renderCombinedViewer(body,prepared,aggregation.value,()=>{rememberResultsView(back);back()});rememberResultsView(back);rememberResultsView(show);await show()}catch(error){if(!combined.isConnected)body.replaceChildren(...selectionNodes);combined.textContent=error.message;proceed.disabled=false}});
 if(mode==='combined')body.append(proceed);
 const refreshCombined=()=>{const rows=records.filter(r=>selected.has(r.id)),same=new Set(rows.map(r=>`${r.recordType}/${r.kind}/${r.source}`)).size<=1,subjectOK=aggregation.value!=='within'||rows.every(r=>r.subject)&&new Set(rows.map(r=>r.subject)).size<=1;proceed.disabled=rows.length<2||!same||!subjectOK;combined.textContent=!same?'Select the same activity and recording source.':!subjectOK?'Select the same participant ID for a within-person comparison.':rows.length<2?'Select at least two compatible sessions.':`${rows.length} selected · ready to check protocols and proceed`;};
 let starred;try{starred=new Set(JSON.parse(localStorage.getItem('bandstandStarredSessions')||'[]'))}catch{starred=new Set()}const onlyStars=document.createElement('select');onlyStars.setAttribute('aria-label','Session stars');option(onlyStars,'all','All sessions');option(onlyStars,'starred','Starred sessions');controls.append(onlyStars);aggregation.onchange=()=>refreshCombined();const refresh=()=>{try{starred=new Set(JSON.parse(localStorage.getItem('bandstandStarredSessions')||'[]'))}catch{}list.replaceChildren();selected.clear();const filtered=records.filter(r=>!deletedSessionIds.has(r.id)&&(quality.value==='all'||quality.value===sessionQuality(r).category)&&(onlyStars.value!=='starred'||starred.has(r.id))&&(source.value==='examples'?r.synthetic:!r.synthetic)&&(!activity.value||r.kind===activity.value)&&(!subject.value||(subject.value==='__unknown'?!r.subject:r.subject===subject.value))&&(!source.value||source.value==='examples'||(source.value==='simulation'?r.source==='simulation':r.source!=='simulation'&&r.source!=='synthetic-preview'))).sort((a,b)=>sort.value==='old'?a.date-b.date:b.date-a.date);
 if(!filtered.length)list.append(personalElement('p','No sessions match. Choose Test sessions, Needs review or All session qualities to see other recordings.'));
 if(mode==='combined'){const all=personalButton('Select displayed sessions',()=>{for(const cb of list.querySelectorAll('input')){cb.checked=true;selected.add(cb.value)}refreshCombined()});list.append(all)}
 for(const r of filtered){const row=personalElement('div',undefined,'saved-session-row'),star=personalButton(starred.has(r.id)?'★':'☆',()=>{starred.has(r.id)?starred.delete(r.id):starred.add(r.id);try{localStorage.setItem('bandstandStarredSessions',JSON.stringify([...starred]))}catch{toast('Could not save session stars on this device.')}star.textContent=starred.has(r.id)?'★':'☆';star.setAttribute('aria-pressed',String(starred.has(r.id)));if(onlyStars.value==='starred')refresh()});star.setAttribute('aria-label','Star '+r.title+' '+new Date(r.date*1000).toLocaleString());star.setAttribute('aria-pressed',String(starred.has(r.id)));star.className='session-star';row.append(star);if(mode==='combined'){const cb=document.createElement('input');cb.type='checkbox';cb.value=r.id;cb.setAttribute('aria-label','Include '+r.title+' '+new Date(r.date*1000).toLocaleString());cb.onchange=()=>{if(cb.checked)selected.add(r.id);else selected.delete(r.id);refreshCombined()};row.append(cb)}const entry=personalButton('',()=>open(r));entry.className='session-open';entry.append(personalElement('strong',r.title),personalElement('span',new Date(r.date*1000).toLocaleString()));entry.setAttribute('aria-label',r.title+' · '+new Date(r.date*1000).toLocaleString());row.append(entry,personalElement('small',[r.subject||'No participant ID',r.source==='simulation'?'Simulated':r.source].join(' · ')));const quality=sessionQuality(r);const badge=personalElement('small',({clean:'Clean headset recording',test:'Test session',review:'Needs review'})[quality.category],'session-quality');badge.title=quality.reason;row.append(badge);list.append(row)}if(mode==='combined')refreshCombined();};for(const el of [activity,subject,source,sort,quality,onlyStars])el.onchange=refresh;browserRefresh=refresh;refresh();
 };
 draw(initialMode);
 if(initialMode!=='latest'){const nodes=[...panel.childNodes];rememberResultsView(()=>{journeySetStep('summary');document.body.classList.add('results-browser');panel.replaceChildren(...nodes);setResultsNavigation(initialMode)})}
 }catch(e){body.textContent='Could not load saved sessions: '+e.message}
}
async function combinedSessionMetrics(records){
 const grouped={};const add=(r,label,value)=>{if(!Number.isFinite(value))return;const key=`${r.title} · ${r.source} · ${label}`,subject=r.subject||'session:'+r.id;((grouped[key]??={})[subject]??=[]).push(value)};
 for(const r of records){if(r.recordType==='writing'){add(r,'recording duration (minutes)',Math.max(0,(r.ended-r.started)/60));continue}if(r.recordType==='personal'){
 for(const [name,v]of Object.entries(r.scores||{}))add(r,name+' (survey score)',v);
 for(const [phase,channels]of Object.entries(r.summary?.phases||{}))for(const [ch,data]of Object.entries(channels))if(data.n>0)data.db?.forEach((v,i)=>add(r,`${phase} · ${ch} · ${['theta','alpha','low beta','high beta'][i]} (dB)`,v));
 }else{const full=r.importedResult||await api('results/'+r.id),a=full.analysis;for(const [ch,data]of Object.entries(a.channels||{}))for(const group of data.groups||[])if(group.accepted>0)add(r,`${ch} · ${group.label} · window ${(full.session.window||[]).join('–')} · band ${(a.band||[]).join('–')} · ${a.metric||full.session.metric||'mean'} (${data.unit||a.unit||'µV'})`,group.mean)}}
 return Object.fromEntries(Object.entries(grouped).map(([key,subjects])=>[key,Object.values(subjects).map(v=>v.reduce((a,b)=>a+b,0)/v.length)]));
}

function sessionCompatibilityKey(row,full){
 const r=full?.session||row;
 const stable=value=>Array.isArray(value)?value.map(stable):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])])):value??null;
 const key={type:row.recordType,activity:row.kind,source:row.source};
 if(row.recordType==='lab')Object.assign(key,{protocol:r.protocol,mode:r.mode,conditions:r.conditions,window:r.window,metric:r.metric,polarity:r.polarity,band:r.mode==='tf'?full.analysis.band||r.band:null,channels:[...(r.channels||[])].sort(),thresholds:r.thresholds,reference:r.reference||'Muse hardware reference',filters:r.filters||null});
 if(row.recordType==='personal')Object.assign(key,{questionnaire:row.questionnaire_version||row.questionnaire_items?.map(i=>[i.text,i.domain,i.reverse])||null,phases:row.plan?.map(p=>p[0])||Object.keys(row.summary?.phases||{}),feedback:row.feedback||null});
 return JSON.stringify(stable(key));
}
async function prepareCombinedSessions(rows,mode){
 if(rows.length<2)throw Error('Select at least two sessions.');
 if(new Set(rows.map(r=>`${r.recordType}/${r.kind}/${r.source}`)).size!==1)throw Error('Choose the same activity and recording source for every session.');
 if(mode==='within'&&(rows.some(r=>!r.subject)||new Set(rows.map(r=>r.subject)).size!==1))throw Error('Choose sessions with the same participant ID.');
 const prepared=await Promise.all(rows.map(async row=>{
  const full=row.recordType==='lab'?(row.importedResult||await api('results/'+row.id)):null;
  let spectra=row.summary?.spectra;
  if(row.recordType==='personal'&&!Object.keys(spectra||{}).length&&!row.synthetic){const result=await api('personal/spectral-results',{id:row.id});spectra=result.spectra}
  return {row,full,spectra,key:sessionCompatibilityKey(row,full)};
 }));
 if(new Set(prepared.map(r=>r.key)).size!==1)throw Error('These sessions use different protocols, conditions, questionnaire versions or analysis settings. Choose matching sessions.');
 return prepared;
}
function renderSessionOverlay(host,prepared){
 const channels=document.createElement('select'),condition=document.createElement('select'),layout=document.createElement('select'),controls=personalElement('div',undefined,'spectrum-controls'),legend=personalElement('div',undefined,'combined-session-legend'),plots=personalElement('div');
 channels.setAttribute('aria-label','Overlay electrode');condition.setAttribute('aria-label','Overlay phase or condition');layout.setAttribute('aria-label','Session plot layout');
 const add=(el,value,label)=>{const o=personalElement('option',label);o.value=value;el.append(o)};
 ['TP9','AF7','AF8','TP10'].forEach(ch=>add(channels,ch,electrodeLabel(ch)));add(layout,'overlay','Overlay sessions');add(layout,'separate','Separate sessions');
 const lab=prepared[0].row.recordType==='lab',spectral=!lab||prepared[0].full.session.mode==='tf';
 const conditions=lab?prepared[0].full.session.conditions||[]:Object.keys(prepared[0].spectra||{});
 conditions.forEach(name=>add(condition,name,name));controls.append(channels,condition,layout);host.append(controls,legend,plots);
 const enabled=new Set(prepared.map((_,i)=>i)),palette=['#315c9e','#b77b26','#548f7b','#955f98','#b25e5e','#587b8c'];
 prepared.forEach(({row},i)=>{const label=personalElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=true;check.onchange=()=>{check.checked?enabled.add(i):enabled.delete(i);draw()};label.style.color=palette[i%palette.length];label.append(check,document.createTextNode(`${i+1} · ${row.subject||'No ID'} · ${new Date(row.date*1000).toLocaleString()}`));legend.append(label)});
 function curves(){return prepared.flatMap(({row,full,spectra},i)=>{
  if(!enabled.has(i))return [];let x,y,lower,upper;
  if(!lab){const data=spectra?.[condition.value],entry=data?.channels[['TP9','AF7','AF8','TP10'].indexOf(channels.value)];x=data?.frequencies;y=entry?.psd;lower=entry?.ci_low;upper=entry?.ci_high}
  else{const group=full.analysis.channels?.[channels.value]?.groups?.find(g=>g.label===condition.value);x=spectral?full.analysis.frequencies:full.analysis.times?.map(t=>t*1000);const estimate=spectral?group?.psd:group?.erp;y=estimate?.mean;if(estimate?.ci95){lower=y.map((v,j)=>v-estimate.ci95[j]);upper=y.map((v,j)=>v+estimate.ci95[j])}}
  return x?.length&&y?.length&&x.length===y.length?[{x,y,i,lower,upper}]:[];
 })}
 function draw(){plots.replaceChildren();const rows=curves();if(!rows.length){plots.append(personalElement('p','No usable data for this electrode and condition.'));return}
  const all=rows.flatMap(r=>[...r.y,...(r.lower||[]),...(r.upper||[])]).filter(Number.isFinite),xmin=Math.min(...rows.map(r=>r.x[0])),xmax=Math.max(...rows.map(r=>r.x.at(-1))),low=Math.min(0,...all),high=Math.max(...all),pad=Math.max(.01,(high-low)*.08),ymin=spectral&&!lab?0:low-pad,ymax=high+pad;
  for(const panel of layout.value==='overlay'?[rows]:rows.map(r=>[r])){
   const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 900 310');svg.setAttribute('role','img');svg.setAttribute('aria-label',`${channels.value} · ${condition.value} · ${spectral?'Power spectrum':'ERP'} · ${panel.length} sessions`);svg.style.width='100%';
   const node=(name,attrs,textValue)=>{const e=document.createElementNS(svg.namespaceURI,name);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);if(textValue!==undefined)e.textContent=textValue;svg.append(e);return e};
   const x=v=>65+(v-xmin)/Math.max(.001,xmax-xmin)*810,y=v=>260-(v-ymin)/(ymax-ymin)*225;
   for(let k=0;k<=4;k++){const v=ymin+k*(ymax-ymin)/4;node('line',{x1:65,x2:875,y1:y(v),y2:y(v),stroke:'#e1e7ee'});node('text',{x:4,y:y(v)+4,fill:'#718292','font-size':12},v.toPrecision(3))}
   for(let k=0;k<=5;k++){const v=xmin+k*(xmax-xmin)/5;node('text',{x:x(v)-8,y:283,fill:'#718292','font-size':12},Math.round(v))}
   node('text',{x:65,y:18,fill:'#526a80','font-size':13},`${channels.value} · ${condition.value} · ${spectral?(lab?'dB re 1 µV²/Hz':'µV²/Hz'):'µV'}`);node('text',{x:790,y:306,fill:'#718292','font-size':12},spectral?'Frequency (Hz)':'Time (ms)');
   for(const row of panel){if(row.lower?.length===row.x.length&&row.upper?.length===row.x.length){const band=row.x.map((v,j)=>`${j?'L':'M'}${x(v)},${y(row.upper[j])}`).join(' ')+row.x.map((v,j)=>`L${x(v)},${y(row.lower[j])}`).reverse().join(' ')+' Z';node('path',{d:band,fill:palette[row.i%palette.length],'fill-opacity':.10,stroke:'none'})}let pen=false;const d=row.x.map((v,j)=>{if(!Number.isFinite(row.y[j])){pen=false;return ''}const command=pen?'L':'M';pen=true;return `${command}${x(v).toFixed(2)},${y(row.y[j]).toFixed(2)}`}).join(' ');node('path',{d,fill:'none',stroke:palette[row.i%palette.length],'stroke-width':2,'stroke-dasharray':row.i>=palette.length?'5 3':'none'})}plots.append(svg);
  }
 }
 const available=['TP9','AF7','AF8','TP10'].find(ch=>prepared.some(p=>lab?p.full.analysis.channels?.[ch]?.groups?.some(g=>g.erp?.mean||g.psd?.mean):Object.values(p.spectra||{}).some(d=>d.channels[['TP9','AF7','AF8','TP10'].indexOf(ch)])));if(available)channels.value=available;channels.onchange=condition.onchange=layout.onchange=draw;draw();
}
async function renderCombinedViewer(body,prepared,mode,back){
 body.replaceChildren();window.scrollTo({top:0,behavior:'instant'});body.append(personalButton('‹ Change selected sessions',back),personalElement('h3',`${prepared[0].row.title} · ${prepared.length} sessions`));
 const rows=prepared.map(p=>p.row),plotHost=personalElement('section');body.append(plotHost);if(rows[0].recordType!=='writing')renderSessionOverlay(plotHost,prepared);
 const details=personalElement('details',undefined,'combined-statistics');details.append(personalElement('summary','Summary statistics'));body.append(details);
 const metrics=await combinedSessionMetrics(mode==='within'?rows.map(r=>({...r,subject:'session:'+r.id})):rows),table=personalElement('table',undefined,'combined-metrics'),header=personalElement('tr');for(const label of ['Measurement','Mean','Range','Summaries'])header.append(personalElement('th',label));table.append(header);
 for(const [key,values]of Object.entries(metrics)){const row=personalElement('tr');for(const value of [key,(values.reduce((a,b)=>a+b,0)/values.length).toFixed(2),`${Math.min(...values).toFixed(2)}–${Math.max(...values).toFixed(2)}`,String(values.length)])row.append(personalElement('td',value));table.append(row)}details.append(table,personalElement('p','Descriptive summaries. Across people, sessions sharing a participant ID are averaged first. The overlay shows individual sessions, not independent participant observations.'));
}

function activityInstructions(path,body){
 if(path==='start')return participantInstruction(body.protocol||protocol.id);
 if(path==='typing/start')return 'Write naturally in your selected app. Stop and save when you finish.';
 const kind=body.kind;if(kind==='big5'||kind==='enneagram'||kind==='extraversion')return 'Describe yourself as you generally are. Choose one response, then Next. EEG records while you answer.';
 if(kind==='reset')return 'Compare breathing, quiet attention, and gratitude. Keep your eyes open and follow each cue.';
 if(kind==='meditation')return 'Keep your eyes open. Notice your breath and gently return your attention when it wanders.';
 return 'Follow each activity cue. Keep your head still and your jaw relaxed.';
}
function runInstructionGate(path,body){
 if(path==='personal/start'||path==='typing/start'||path==='start')return Promise.resolve(true);
 return new Promise(resolve=>{const previous=journeyStep;journeySetStep('run');const d=document.createElement('dialog');d.className='plain-help run-instruction-gate';const title=personalElement('h2',$('activityBranchName')?.textContent||'Ready to begin'),instruction=personalElement('p',activityInstructions(path,body));instruction.hidden=true;
 const start=personalButton('Begin recording',()=>finish(true));start.hidden=true;const reveal=personalButton('Click for instructions',()=>{instruction.hidden=false;start.hidden=false;reveal.hidden=true});
 const finish=ok=>{d.close();d.remove();if(!ok)journeySetStep(previous);resolve(ok)};d.append(title,reveal,instruction,start,personalButton('Back',()=>finish(false)));d.addEventListener('cancel',e=>{e.preventDefault();finish(false)});document.body.append(d);d.showModal();reveal.focus();});
}

function activityCategoryIcon(kind){
 const paths={
 insights:'<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
 lab:'<path d="M12 5c-2-5-7-2-6 1-5 0-5 7-2 8-2 5 3 8 6 6l2-2V5Zm0 0c2-5 7-2 6 1 5 0 5 7 2 8 2 5-3 8-6 6l-2-2M6 6l2 3M4 14l4-2m10-6-2 3m4 5-4-2"/>',
 bci:'<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M8 1v4m8-4v4M8 19v4m8-4v4M1 8h4m-4 8h4M19 8h4m-4 8h4"/>',
 trainer:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
 growth:'<circle cx="12" cy="4" r="2"/><path d="m8 9 4-1 4 1 2 5 4 2m-14-7-2 5-4 2m8-4 2 4 2-4m-2 4-6 2c-5 2-2 5 6 3 8 2 11-1 6-3l-6-2"/>'
 };
 const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');icon.setAttribute('class','activity-category-icon');icon.innerHTML=paths[kind]||paths.insights;return icon;
}

function initLabSetupSequence(){
 const brief=$('journeyBrief'),sequence=document.createElement('ol');sequence.className='setup-sequence';
 const participant=document.createElement('li');participant.id='labParticipantSequenceSlot';
 const instructions=document.createElement('li'),task=$('briefTask'),button=task.previousElementSibling;
 if(button?.tagName==='BUTTON')instructions.append(button);instructions.append(task);
 const start=document.createElement('li'),startRow=document.querySelector('.setup .start-row');startRow.querySelector('#start').textContent='Start activity';start.append(startRow);
 const advanced=document.createElement('li'),advancedPanel=$('advancedSettings'),advancedButton=$('briefAdvanced');
 advancedPanel.open=false;advancedPanel.querySelector('summary').replaceChildren(advancedButton);
 advancedButton.setAttribute('aria-expanded','false');advancedButton.setAttribute('aria-controls','advancedSettings');
 advancedPanel.addEventListener('toggle',()=>advancedButton.setAttribute('aria-expanded',String(advancedPanel.open)));
 advanced.append(advancedPanel);
 sequence.append(participant,advanced,instructions,start);const protocolHelp=$('briefProtocol');protocolHelp.textContent='?';protocolHelp.className='protocol-info-button';protocolHelp.setAttribute('aria-label','Additional protocol details');advancedPanel.append(protocolHelp);brief.append(sequence,brief.querySelector('.brief-actions'));brief.classList.add('personal-setup-sequence');
}

async function leaveTypingRun(step,throughNavigation=false){
 if(journeyLeavingTyping)return;
 journeyLeavingTyping=true;
 try{
  await stopTyping('Left the Run tab');
  if(state?.typing?.running)throw Error('Recording is still stopping. Please try again.');
  journeyRun=false;
  if(throughNavigation)await journeyGo(step);else journeySetStep(step);
 }catch(error){toast('Could not stop recording: '+error.message);journeySetStep('run')}
 finally{journeyLeavingTyping=false}
}
function initWritingRunWorkspace(){
 const run=personalElement('section',undefined,'panel');run.id='writingRun';$('writingParadigm').after(run);
 const context=$('writingModelSettings');if(context){
  context.querySelector('summary').textContent='Decoder settings';
  const options=personalElement('div',undefined,'model-options');
  for(const id of ['typingHistory','typingDelay'])options.append($(id).closest('label'));
  const information=[...context.children].filter(el=>el.tagName!=='SUMMARY'&&el.type!=='hidden');
  for(const el of information)el.remove();
  const captureInfo=information.find(el=>el.tagName==='DETAILS');if(captureInfo)captureInfo.querySelector('p').textContent='Across-app capture records new typing while the Run tab is active. Password fields and unsupported editors are excluded. Switching to another Bandstand workflow tab stops and saves the recording. Switching to another application does not stop across-app capture.';
  for(const el of information){if(el.textContent.startsWith('Later phrases are evaluated'))el.textContent='Evaluation holds out time blocks with gaps between training and testing. Exact phrase repeats are excluded. Motor and eye activity may still contribute; above-baseline performance does not establish thought decoding.'}
  context.append(options,headsetHelp('Decoder model and evaluation',information));
 }
 const performance=$('writingAnalysis').querySelector('.performance-panel');const explanation=performance?.querySelector(':scope > p:last-child');if(explanation){explanation.remove();performance.querySelector('h2').after(headsetHelp('Reading decoder performance',[explanation]));}
 const metrics=$('stageMetrics');if(metrics){const notes=[$('stageStats'),metrics.querySelector(':scope > small')].filter(Boolean);notes.forEach(n=>n.remove());metrics.querySelector('h3')?.remove();metrics.prepend(headsetHelp('Live plots and annotations',notes));}
 const trainer=$('developerPanel');trainer.append(personalElement('p','Not available yet.','trainer-unavailable'));
 // The old diagnostic controls keep their IDs for compatibility but are not exposed.
 for(const input of trainer.querySelectorAll('button,input,select'))input.disabled=true;
}
function arrangeWritingWorkspace(step){
 const run=$('writingRun'),setup=$('writingParadigm');if(!run||!setup)return;
 const target=step==='run'&&typingView?run:setup;
 for(const id of ['typingModes','writingEditor','typingCapturePreview'])if($(id)&&$(id).parentElement!==target)target.append($(id));
 const controls=$('typingStop')?.closest('.writing-controls');if(controls&&controls.parentElement!==run)run.append(controls);
 if($('typingStartFeedback')&&$('typingStartFeedback').parentElement!==target)target.append($('typingStartFeedback'));
 for(const id of ['typingHistory','typingDelay'])if($(id))$(id).disabled=Boolean(state?.typing?.running);
}
async function showRunTaskIntro(instruction,id){
 const stimulus=$('stimulus');$('stageInstruction').textContent='';stimulus.textContent=instruction;stimulus.classList.add('run-task-intro');
 try{await delay(Math.min(6500,Math.max(3000,instruction.split(/\s+/).length*240)),id);stimulus.classList.add('fade-out');await delay(350,id)}
 finally{stimulus.classList.remove('run-task-intro','fade-out');stimulus.textContent=''}
}
