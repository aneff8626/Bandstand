/* Shared navigation and acquisition UI. Display controls never stop acquisition. */
let journeyReady=false,journeyStarting=false,journeyLastBrief='',journeyRun=false;
function journeySetup(){return $(document.body.classList.contains('personal-view')?'personalSetup':typingView?'writingParadigm':'experimentParadigm')}
function journeyResults(){return $(document.body.classList.contains('personal-view')?'personalResults':typingView?'writingResults':'experimentResults')}
let journeyStep='headset',journeyFreshResult=false;
function journeySetStep(step){
 if(!journeyReady)return;
 journeyStep=step;document.body.dataset.journeyStep=step;document.body.classList.remove('results-browser');
 $('headsetSetup').open=true;journeySetup().open=true;
 if(step==='summary')journeyResults().open=true;
 for(const b of document.querySelectorAll('#journeySteps button'))b.setAttribute('aria-current',b.dataset.step===step?'step':'false');
}
function journeyGo(step){
 if(['setup','run'].includes(step)&&!chosenActivityTitle){toast('Select an activity first.');return}
 if(step==='run'){journeySetStep(journeyRun?'run':'setup');return}
 if(step==='summary'&&!journeyFreshResult){showResultsBrowser();return}
 if(step==='headset'||step==='summary'){journeySetStep(step);return}
 if(!personalLeave())return;
 if(step==='choose'){if(document.body.dataset.area==='lab'){labTypeChosen=true;buildProtocols();showLabStep('choose')}else personalRoute(document.body.dataset.area||'insights')}
 else if(step==='setup'){if(document.body.dataset.area==='trainer'){show('developerPanel');}else if(document.body.dataset.area==='lab')showLabStep('settings');else if(!typingView){if(!activityResume[document.body.dataset.area]){toast('Choose an activity first.');return}activityResume[document.body.dataset.area]()}}
 journeySetStep(step);window.scrollTo({top:0,behavior:'smooth'});
}
function initJourney(){
 document.body.classList.add('journey-theme');
 const header=document.createElement('div');header.id='journeyHeader';header.innerHTML='<strong class="journey-brand"><img src="/bandstand-logo.png" alt=""> Bandstand</strong><nav aria-label="Recording workflow" id="journeySteps"></nav><div id="journeyAccount"></div>';
 for(const [id,label]of [['headset','1 Headset'],['choose','2 Activity'],['setup','3 Setup'],['run','4 Run'],['summary','5 Results']]){const b=personalButton(label,()=>journeyGo(id));b.dataset.step=id;header.querySelector('nav').append(b)}
 const branch=document.createElement('div');branch.id='activityBranch';branch.innerHTML='<span id="activityBranchName">Selected activity</span><div></div>';header.querySelector('nav').append(branch);for(const id of ['setup','run'])branch.lastChild.append(header.querySelector('[data-step='+id+']'));
 const resultsArrow=document.createElement('span');resultsArrow.className='results-step-arrow';resultsArrow.textContent='›';resultsArrow.setAttribute('aria-hidden','true');header.querySelector('nav').append(resultsArrow,header.querySelector('[data-step=summary]'));
 const account=$('accountNav'),contribute=$('contributeNav');header.querySelector('#journeyAccount').append(account,contribute);document.body.prepend(header);
 const areas=document.querySelector('.area-navigation');areas.id='journeyAreas';areas.setAttribute('aria-label','Activity collection');
 for(const b of areas.children){b.replaceChildren(activityCategoryIcon(b.dataset.area),document.createTextNode({lab:'Learn about your brain',insights:'Learn about your mind',bci:'BCI',growth:'Growth exercises',trainer:'Artifact trainer'}[b.dataset.area]));const original=b.onclick;b.onclick=async()=>{await original();journeyFreshResult=false;chosenActivityTitle=b.dataset.area==='trainer'?'Artifact trainer':'';if(b.dataset.area==='lab'){labTypeChosen=true;buildProtocols();showLabStep('choose')}journeySetup().open=true;journeySetStep('choose');journeyTick()}}
 $('headsetSetup').after(areas);
 const participant=document.createElement('details');participant.id='participantSetup';participant.className='settings-disclosure';participant.innerHTML='<summary><button type="button" id="participantDataToggle" aria-expanded="false"><span id="participantSetupLabel">Add participant data</span></button> <small>optional</small></summary><div class="form-grid"><label>Subject ID or name<input id="participantName" maxlength="120" autocomplete="off" placeholder="An ID is preferred"></label><label>Age<input id="participantAge" type="number" min="0" max="120"></label><label>Gender<input id="participantGender" maxlength="80"></label><label>Handedness<select id="participantHand"><option value="">Not specified</option><option>Right</option><option>Left</option><option>Both</option></select></label></div><fieldset><legend>Forms before the task</legend><label><input type="checkbox" value="extraversion"> Extraversion · 10 IPIP items</label><label><input type="checkbox" value="big5"> Big Five · 50 IPIP items</label><label><input type="checkbox" value="enneagram"> Enneagram · 9 prompts (not a validated type test)</label></fieldset><p class="muted">Forms appear in the activity screen and can be skipped. Form completion is a preparation phase; task recording starts afterward.</p>';
 const participantInfo=headsetHelp('Participant data',[personalElement('p','These details and answers are saved locally, separately from shared ERP data.')]);participantInfo.addEventListener('click',event=>{event.preventDefault();event.stopPropagation()});participant.append(participantInfo);const participantToggle=participant.querySelector('#participantDataToggle');participantToggle.onclick=event=>{event.preventDefault();participant.open=!participant.open;};participant.addEventListener('toggle',()=>participantToggle.setAttribute('aria-expanded',String(participant.open)));
 journeySetup().append(participant);
 const dock=document.createElement('section');dock.id='eegDock';dock.setAttribute('aria-label','Live EEG monitor');dock.innerHTML='<div class="dock-heading"><span id="dockState" role="status">Starting EEG service…</span><button id="dockToggle" aria-expanded="true">Hide EEG</button></div><div id="dockSignal"></div>';
 dock.querySelector('#dockSignal').append(createHeadsetMap('Open headset setup',()=>journeyGo('headset')));header.insertBefore(dock,header.querySelector('#journeyAccount'));
 $('dockToggle').onclick=()=>{const hidden=!$('dockSignal').hidden;$('dockSignal').hidden=hidden;$('dockToggle').textContent=hidden?'Show EEG':'Hide EEG';$('dockToggle').setAttribute('aria-expanded',String(!hidden));document.body.classList.toggle('eeg-view-hidden',hidden)};
 const brief=document.createElement('div');brief.id='journeyBrief';brief.innerHTML='<h2 id="briefTitle"></h2><p id="briefTask"></p><p id="briefDuration" class="muted"></p><div class="brief-actions"><button id="briefAdvanced">Advanced controls</button><button id="briefProtocol">Additional protocol details</button></div>';
 document.querySelector('.setup').prepend(brief);$('briefAdvanced').onclick=()=>$('advancedSettings').closest('dialog').showModal();$('briefProtocol').onclick=()=>$('expectedResults').closest('dialog').showModal();
 // Make both recording displays visible by default, while retaining one-click hiding.
 $('stage').classList.remove('results-collapsed');$('liveResultsToggle').textContent='Hide EEG & analysis';$('liveResultsToggle').setAttribute('aria-expanded','true');
 $('headsetSetup').open=true;labTypeChosen=true;buildProtocols();
 initHeadsetDisplay();initLabSetupSequence();journeyReady=true;journeySetStep('headset');journeyTick();setInterval(journeyTick,300);
}
function journeyTick(){
 if(!journeyReady)return;
 const running=Boolean(active||personalBusy||state?.typing?.running||state?.developer?.recording);
 if(running&&!journeyRun){journeyFreshResult=false;journeySetStep('run');$('dockSignal').hidden=false;$('dockToggle').textContent='Hide EEG';$('dockToggle').setAttribute('aria-expanded','true');document.body.classList.remove('eeg-view-hidden');$('stage').classList.remove('results-collapsed')}
 if(!running&&journeyRun){journeyFreshResult=true;journeySetStep('summary')}
 journeyRun=running;
 updateActivityBranch();
 const setup=journeySetup(),participant=$('participantSetup'),slot=journeyStep==='setup'?(document.body.classList.contains('personal-view')?$('participantSequenceSlot'):!typingView?$('labParticipantSequenceSlot'):null):null,target=slot||setup;if(participant.parentElement!==target)target.append(participant);$('participantSetupLabel').textContent='Add participant data';
 for(const input of participant.querySelectorAll('input,select'))input.disabled=running||journeyStarting;
 for(const input of participant.querySelectorAll('input[type=checkbox]')){const automatic=({big5:'Big Five',enneagram:'Enneagram'})[input.value]===chosenActivityTitle;if(automatic){if(!input.dataset.automatic)input.dataset.previous=String(input.checked);input.checked=true;input.disabled=true;input.dataset.automatic='true';input.title='Included automatically during this activity';}else if(input.dataset.automatic){input.checked=input.dataset.previous==='true';delete input.dataset.automatic;input.title='';}}
 const contribute=$('contributeNav');contribute.hidden=!contribute.classList.contains('needs-choice');
 const name=!state?'Starting EEG service…':state?.source==='simulation'?'Demo EEG':state&&!state.stale?'Live EEG · 4 channels':'Waiting for EEG';if($('dockState').textContent!==name)$('dockState').textContent=name;
 const runButton=document.querySelector('[data-step="run"]');runButton.disabled=!chosenActivityTitle;runButton.textContent=running?'4 Recording ●':'4 Run';
 drawHeadsetMaps();
 const connection=$('connectMuse');if(state&&!state.stale){connection.textContent=state.source==='simulation'?'◉ Demo':'● Streaming';connection.title='Device connected, streaming'}
 if(protocol){const key=protocol.id+'/'+$('trialCount').value;if(key!==journeyLastBrief){journeyLastBrief=key;$('briefTitle').textContent=protocol.title;$('briefTask').textContent='Task: '+participantInstruction(protocol.id);const duration=(Number($('trialCount').value)||protocol.trials)*((protocol.stim_ms[0]+protocol.stim_ms[1]+protocol.isi_ms[0]+protocol.isi_ms[1])/2)/60000+(protocol.mode==='erp'?Math.floor(((Number($('trialCount').value)||protocol.trials)-1)/40)/6:0)+2/60;$('briefDuration').textContent='Time: about '+Math.max(1,Math.ceil(duration))+(Math.max(1,Math.ceil(duration))===1?' minute':' minutes')+(protocol.mode==='erp'?' · ERP':' · Spectral power')}}
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
 el.innerHTML='<svg viewBox="0 0 240 155" role="img" aria-label="Four-electrode headset, viewed from above"><path class="head-outline" d="M108 22l12-12 12 12c39 5 61 33 61 65s-24 57-73 57-73-25-73-57 22-60 61-65z"/><path class="head-band" d="M48 93C45 10 195 10 192 93"/><path class="head-outline" d="M47 78c-15-10-15 29 2 28M193 78c15-10 15 29-2 28"/>'+[['TP9',50,99,22,126],['AF7',82,42,58,24],['AF8',158,42,158,24],['TP10',190,99,195,126]].map(([ch,x,y,tx,ty])=>`<g data-electrode="${ch}"><circle class="artifact-ring" cx="${x}" cy="${y}" r="14"/><circle class="electrode-glow" cx="${x}" cy="${y}" r="10"/><text x="${tx}" y="${ty}">${ch}</text><title>${ch}: waiting for EEG</title></g>`).join('')+'</svg>';
 return el;
}
function drawHeadsetMaps(){
 const trace=state?.trace,end=trace?.times?.at(-1),live=state&&!state.stale&&Number.isFinite(end);
 for(const node of document.querySelectorAll('[data-electrode]')){
  const ch=node.dataset.electrode,index=boot?.channels.indexOf(ch);let sum=0,n=0;
  if(live&&index>=0)for(let i=trace.times.length-1;i>=0&&trace.times[i]>=end-.25;i--){const v=trace.values[i]?.[index];if(Number.isFinite(v)){sum+=v*v;n++}}
  const rms=n?Math.sqrt(sum/n):0,level=n?.05+.95*Math.min(1,rms/20):.08;
  node.querySelector('.electrode-glow').style.opacity=level;node.querySelector('.electrode-glow').style.fill=typeof colors!=='undefined'?colors[index]:'#346a9d';
  const artifact=live&&(state.artifact_regions||[]).some(r=>r.channels?.includes(ch)&&r.onset<=end&&r.offset>=end-.2);
  node.classList.toggle('has-artifact',!!artifact);node.querySelector('title').textContent=ch+(n?': '+rms.toFixed(1)+' µV RMS'+(artifact?' · recent artifact':''):': no current signal');
 }
}
function headsetHelp(label,nodes){
 const button=personalButton('?',()=>dialog.showModal());button.className='info-dot';button.title=label;button.setAttribute('aria-label',label);
 const dialog=document.createElement('dialog');dialog.className='plain-help';const title=document.createElement('h2');title.textContent=label;dialog.append(title,...nodes,personalButton('Close',()=>dialog.close()));document.body.append(dialog);return button;
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
 const mapExplanation=document.createElement('p');mapExplanation.textContent='Dots match the voltage-trace colors. Brightness follows 250 ms RMS amplitude, saturating at 20 µV. A faint red ring marks a recent artifact. Brightness is not contact quality or a brain-state score.';const scalpHelp=headsetHelp('2D scalp view',[mapExplanation]);map.append(scalpHelp);
 $('showHeadset').onchange=()=>map.hidden=!$('showHeadset').checked;$('showMotion').onchange=()=>{motionPlot.hidden=!$('showMotion').checked;drawMotionTraces()};
 initLiveSpectrum(traceColumn);row.replaceChildren(toolbar);
 const preflightSection=$('preflightInstruction').closest('section');preflightSection.querySelector('h2').hidden=true;preflightSection.prepend(personalButton('Click for instructions',()=>{preflightSection.querySelector('h2').hidden=!preflightSection.querySelector('h2').hidden}));
 $('briefTask').hidden=true;$('briefTask').before(personalButton('Click for instructions',()=>{$('briefTask').hidden=!$('briefTask').hidden}));
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
 for(const ch of boot.channels){const card=document.createElement('div'),plot=document.createElement('canvas');plot.id='liveSpectrum'+ch;plot.height=190;card.append(plot);area.querySelector('.spectrum-grid').append(card)}
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
 text(ctx,ch,3,13,colors[i],12);if(bands||i===boot.channels.findIndex(ch=>!hiddenTraceChannels.has(ch)))text(ctx,bands?'µV²':'µV²/Hz',45,13);if(!entry||state?.stale){text(ctx,'Waiting for usable samples',l,65);return}
 const values=bands?entry.bands:entry.psd,max=bands?smoothSpectrumAxis('channel'+i,Math.max(.01,...values.filter((v,j)=>!hiddenSpectrumBands.has(j)))*1.1):psdMaximum(data);if(!bands)drawFrequencyGuides(ctx,l,r,t,b);for(let k=0;k<=3;k++){const y=b-k*(b-t)/3;line(ctx,[[l,y],[r,y]],'#e1e7ee');if(bands||i===boot.channels.findIndex(ch=>!hiddenTraceChannels.has(ch)))text(ctx,(max*k/3).toPrecision(2),1,y+3)}
 if(bands){const visible=visibleBandIndices(),step=(r-l)/Math.max(1,visible.length);visible.forEach((j,position)=>{const v=values[j];ctx.fillStyle=colors[i];ctx.globalAlpha=.75;ctx.fillRect(l+position*step+step*.15,b-Math.min(v/max,1)*(b-t),step*.7,Math.min(v/max,1)*(b-t));ctx.globalAlpha=1;text(ctx,labels[j],l+position*step,b+16,undefined,8)})}
 else{line(ctx,values.map((v,j)=>[frequencyX(data.frequencies[j],l,r),frequencyVisible(data.frequencies[j])?b-Math.min(v/max,1)*(b-t):NaN]),colors[i],1.6);drawFrequencyTicks(ctx,l,r,b)}
 });
}

function finishStartup(){
 if(!journeyReady||!state||!document.body.classList.contains('app-loading'))return;
 if(!active&&!personalBusy&&!state?.typing?.running&&!state?.developer?.recording){chosenActivityTitle='';for(const area of Object.keys(activityResume))delete activityResume[area];}
 updateActivityBranch();journeySetStep('headset');document.body.classList.remove('app-loading');
}
function startupProblem(message){
 const status=$('startupMessage');if(!status)return;status.textContent='Startup could not finish: '+message;
 for(const d of document.querySelectorAll('dialog[open]'))d.close();
 if(!$('startupRetry')){const retry=personalButton('Retry',()=>location.reload());retry.id='startupRetry';$('startupScreen').append(retry)}
}
setTimeout(()=>{if(document.body.classList.contains('app-loading')){$('startupMessage').textContent='Still starting the local service. Bluetooth will be available shortly.'}},8000);

function spectrumGroups(mode){return mode==='lr'?[{label:'Left',channels:['TP9','AF7']},{label:'Right',channels:['AF8','TP10']}]:mode==='ft'?[{label:'Frontal',channels:['AF7','AF8']},{label:'Temporal',channels:['TP9','TP10']}]:[{label:'',channels:boot.channels}] }
function drawCombinedSpectrum(data,id='combinedSpectrum',include=boot.channels,title='',labelAxis=true){
 const {ctx,w,h}=canvas(id),l=48,r=w-15,t=38,b=h-36;
 const channels=boot.channels.map((ch,i)=>({ch,i,entry:data?.channels[i]})).filter(c=>include.includes(c.ch)&&!hiddenTraceChannels.has(c.ch));
 if(labelAxis)text(ctx,'µV²/Hz',2,13);if(title)text(ctx,title,l,12);let legendX=l;channels.forEach(c=>{const label=c.ch+(c.entry?'':' · waiting');text(ctx,label,legendX,24,colors[c.i],11);legendX+=ctx.measureText(label).width+18});
 const max=psdMaximum(data);drawFrequencyGuides(ctx,l,r,t,b);
 for(let k=0;k<=4;k++){const y=b-k*(b-t)/4;line(ctx,[[l,y],[r,y]],'#e1e7ee');if(labelAxis)text(ctx,(max*k/4).toPrecision(2),2,y+3)}
 drawFrequencyTicks(ctx,l,r,b);
 if(state?.stale||!channels.some(c=>c.entry)){text(ctx,channels.length?'Waiting for usable samples':'Select an electrode above',l,65);return}
 for(const c of channels)if(c.entry)line(ctx,c.entry.psd.map((v,j)=>[frequencyX(data.frequencies[j],l,r),frequencyVisible(data.frequencies[j])?b-Math.min(v/max,1)*(b-t):NaN]),colors[c.i],1.7);
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

function drawCombinedBands(data,id,include,title,labelAxis){
 const {ctx,w,h}=canvas(id),l=48,r=w-15,t=55,b=h-35;
 const channels=boot.channels.map((ch,i)=>({ch,i,entry:data?.channels[i]})).filter(c=>include.includes(c.ch)&&!hiddenTraceChannels.has(c.ch));
 const byBand=true,names=['Delta','Theta','Alpha','Low β','High β','Gamma'],palette=['#839bb2','#8171a8','#3a9a8b','#ba984c','#be805c','#aa708d'];
 if(labelAxis)text(ctx,'µV²',2,13);if(title)text(ctx,title,l,13);
 const legend=byBand?channels.map(c=>[c.ch,colors[c.i]]):names.map((n,i)=>[n,palette[i]]);
 let legendX=l,legendY=29;legend.forEach(([n,color])=>{ctx.font='10px -apple-system,sans-serif';const width=ctx.measureText(n).width;if(legendX+width>r){legendX=l;legendY+=13}text(ctx,n,legendX,legendY,color,10);legendX+=width+18});
 const max=smoothSpectrumAxis('groupBands',Math.max(1,...(data?.channels||[]).flatMap((c,i)=>hiddenTraceChannels.has(boot.channels[i])?[]:(c?.bands||[]).filter((v,j)=>!hiddenSpectrumBands.has(j))))*1.15,Boolean(data?.channels?.some(Boolean)));
 for(let k=0;k<=4;k++){const y=b-k*(b-t)/4;line(ctx,[[l,y],[r,y]],'#e1e7ee');if(labelAxis)text(ctx,(max*k/4).toPrecision(2),2,y+3)}
 if(state?.stale||!channels.some(c=>c.entry)){text(ctx,channels.length?'Waiting for usable samples':'Select an electrode above',l,80);return}
 const visible=visibleBandIndices(),groups=visible.length,step=(r-l)/Math.max(1,groups),count=byBand?channels.length:6,width=step*.78/count;
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
 const result=journeyResults();let actions=result.querySelector('.result-navigation');if(!actions){actions=document.createElement('div');actions.className='result-navigation';actions.append(personalButton('Browse saved results',openPreviousActivities));result.querySelector('summary').after(actions)}
}
function showResultsBrowser(){
 journeySetStep('summary');document.body.classList.add('results-browser');
 let panel=$('savedResultsBrowser');if(!panel){panel=document.createElement('section');panel.id='savedResultsBrowser';panel.className='panel';panel.append(personalElement('h2','Results'),personalButton('Browse saved results',openPreviousActivities));document.querySelector('main').append(panel)}
}
async function openPreviousActivities(){
 if(!personalLeave())return;
 const dialog=document.createElement('dialog');dialog.className='plain-help';dialog.append(personalElement('h2','Previous activities'),personalButton('Close',()=>dialog.close()));document.body.append(dialog);dialog.showModal();dialog.addEventListener('close',()=>dialog.remove());
 const demoSection=personalElement('section');demoSection.append(personalElement('h3','Synthetic subjects · 100'),personalElement('p','Invented records for exploring results. Separate from real participants, training and uploads.','muted'));
 const subject=document.createElement('select');subject.setAttribute('aria-label','Synthetic subject');for(let i=1;i<=100;i++){const option=personalElement('option','Demo subject '+String(i).padStart(3,'0'));option.value=i;subject.append(option)}
 const kind=document.createElement('select');kind.setAttribute('aria-label','Questionnaire');for(const [value,title]of [['big5','Big Five'],['enneagram','Enneagram']]){const option=personalElement('option',title);option.value=value;kind.append(option)}
 demoSection.append(subject,kind,personalButton('Open results',()=>{const r=mindDemoDatabase.records.find(r=>r.kind===kind.value&&r.subject_id==='Demo subject '+String(subject.value).padStart(3,'0'));personalRoute('insights');renderPersonalResult(r);journeySetStep('summary');dialog.close()}));dialog.append(demoSection,personalElement('h3','Recorded activities'));
 try{const catalog=await api('personal/catalog',{});for(const r of catalog.history||[]){dialog.append(personalButton(r.kind.replaceAll('_',' ')+' · '+new Date(r.created*1000).toLocaleString(),()=>{personalRoute(['reset','meditation'].includes(r.kind)?'growth':'insights');chosenActivityTitle=r.kind.replaceAll('_',' ');renderPersonalResult(r);journeySetStep('summary');dialog.close()}))}
 const sessions=await api('sessions');if(!catalog.history?.length&&!sessions.length)dialog.append(personalElement('p','No saved activities yet. Run an activity to see results here.'));
 for(const r of sessions)dialog.append(personalButton(r.title+' · '+new Date(r.started*1000).toLocaleString(),async()=>{personalRoute('lab');selectedResult=await api('results/'+r.id);renderRevision='';updateResultExports();render();journeySetStep('summary');$('activityBranchName').textContent=r.title;dialog.close()}));
 }catch(e){dialog.append(personalElement('p',e.message))}
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
 const advanced=document.createElement('li');advanced.append($('briefAdvanced'));
 sequence.append(participant,advanced,instructions,start);brief.append(sequence,brief.querySelector('.brief-actions'));brief.classList.add('personal-setup-sequence');
}
