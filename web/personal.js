/* Consumer workspaces reuse the one headset component. All personal APIs are local. */
let personalCatalog=null,personalBusy=false,personalKind=null,personalTimer=null,personalLast=null;
const personalInstructions={Baseline:'Rest comfortably, eyes open. Keep your jaw and head relaxed.',Breathing:'Breathe comfortably with the circle. Keep your eyes open; do not force your breathing.', 'Quiet attention':'Keep your eyes open. Rest your attention on one spot and gently return when it wanders.',Gratitude:'Eyes open: silently recall something you appreciate. Keep your posture unchanged.',Meditation:'Keep your eyes open. Notice your breath and gently return your attention when it wanders.','Eyes-open rest':'Rest with your eyes open. Keep your head still and jaw relaxed.'};
function personalElement(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function personalButton(text,fn){const b=personalElement('button',text);b.type='button';b.onclick=async()=>{try{await fn()}catch(e){toast(e.message)}};return b}
function personalLeave(){if(personalBusy||active||state?.typing?.running||state?.developer?.recording||developerPhase){toast('Stop and save the current recording before switching activities.');return false}return true}
const activityResume={};
function activitySetupStep(id,selected,back){
 const participant=$('participantSetup');if(participant)$(id)?.append(participant);
 if(typeof journeySetStep==='function')journeySetStep(selected?'setup':'choose');
 const panel=$(id);if(!panel)return;
 let nav=panel.querySelector('.activity-step-nav');
 if(!nav){nav=personalElement('div',undefined,'activity-step-nav');panel.querySelector('summary').after(nav)}
 nav.replaceChildren();nav.setAttribute('role','tablist');nav.setAttribute('aria-label','Activity setup');
 const area=document.body.dataset.area||'insights';
 for(const [label,on,fn] of [['Select an activity',!selected,()=>{if(personalLeave())(back||(()=>personalHome(area)))()}],['Settings & start',selected,()=>{if(personalLeave())activityResume[area]?.()}]]){
  const button=personalButton(label,fn);button.setAttribute('role','tab');button.setAttribute('aria-selected',String(on));button.disabled=!on&&label==='Settings & start'&&!activityResume[area];nav.append(button);
 }
 if(typeof addActivityPreview==='function')addActivityPreview(nav);
}
function preparePersonalActivity(title,description,start){
 chosenActivityTitle=title;
 if(!personalLeave())return;
 activityResume[document.body.dataset.area]=()=>preparePersonalActivity(title,description,start);activitySetupStep('personalSetup',true,()=>personalHome(document.body.dataset.area));
 const heading=title==='Enneagram'?'Enneagram Personality type predictor':title==='Big Five'?'Big Five Personality dimensions':title;
 const body=$('personalSetupBody');body.replaceChildren();const wrapper=personalElement('section',undefined,'personal-setup-sequence');wrapper.append(personalElement('h2',heading));
 const steps=personalElement('ol',undefined,'setup-sequence');
 const participantStep=personalElement('li');participantStep.id='participantSequenceSlot';
 const taskInstructions=title==='Big Five'||title==='Enneagram'?'Read each statement and choose how accurately it describes you in everyday life. Answer honestly; there are no right or wrong answers. Keep your head still and jaw relaxed while EEG records.':title==='Meditation practice'?'Keep your eyes open and breathe comfortably. Relax your jaw and remain still. After the baseline, use the alpha-power feedback to practice gently increasing the target rhythm.':title==='Find Your Reset'?'Follow each cue for breathing, quiet attention and gratitude. Keep your eyes open and remain still during each activity and rest period.':description;
 const instructionStep=personalElement('li'),instructions=personalElement('p',taskInstructions);instructions.hidden=true;const instructionButton=personalButton('Click for instructions',()=>{instructions.hidden=!instructions.hidden;instructionButton.setAttribute('aria-expanded',String(!instructions.hidden))});instructionButton.setAttribute('aria-expanded','false');instructionStep.append(instructionButton,instructions);
 const startStep=personalElement('li'),startButton=personalButton('Start activity',start);startButton.className='primary';startStep.append(startButton);steps.append(participantStep,instructionStep,startStep);wrapper.append(steps);body.append(wrapper);
 if($('participantSetup')){participantStep.append($('participantSetup'));$('participantSetupLabel').textContent='Add participant data';}

}
function personalRoute(area,view='home'){
 
 if(!personalLeave())return;
 document.body.dataset.area=area;document.body.classList.toggle('personal-view',area!=='lab'&&view!=='writing');
 document.body.classList.toggle('growth-theme',area==='growth');document.body.classList.toggle('insight-theme',area==='insights');
 $('personalWorkspace').hidden=area==='lab'||view==='writing';$('personalLinks').hidden=true;$('labLinks').hidden=area!=='lab';$('typingNav').hidden=true;
 for(const b of document.querySelectorAll('[data-area]'))b.setAttribute('aria-current',b.dataset.area===area?'page':'false');
 if(area==='trainer'){selectTypingView(false);$('personalWorkspace').hidden=true;chosenActivityTitle='Artifact trainer';show('developerPanel');return}
 show('developerPanel',false);
 if(area==='lab'){selectTypingView(false);$('pageTitle').textContent='Learn About Your Brain';$('modeCrumb').textContent='RESEARCH LAB';return}
 if(view==='writing'){chosenActivityTitle='Writing decoder';activityResume.bci=()=>personalRoute('bci','writing');selectTypingView(true);activitySetupStep('writingParadigm',true,()=>personalRoute('bci'));return}
 selectTypingView(false);$('pageTitle').textContent=area==='growth'?'Growth Exercises':'Learn About Your Mind';$('modeCrumb').textContent=area==='growth'?'PRACTICE & EXPLORE':'DISCOVER YOUR PATTERNS';
 personalHome(area);
 try{localStorage.setItem('bandstandArea',area)}catch{}
}
function personalHome(area){
 chosenActivityTitle='';
 activitySetupStep('personalSetup',false);
 const setup=$('personalSetupBody');setup.replaceChildren();$('personalResultsBody').replaceChildren();
 const cards=personalElement('div',undefined,'personal-cards');setup.append(cards);
 const entries=area==='bci'?[['Writing decoder','Write in Bandstand or across your apps',()=>personalRoute('bci','writing')]]:area==='growth'?[
 ['Find Your Reset','Find the activity with the largest EEG change · about 4 minutes',()=>startPersonal('reset')],
 ['Meditation practice','Train alpha power (8–13 Hz) with live EEG feedback · 2½ minutes',()=>startPersonal('meditation')]
 ]:[
 ['Big Five','Five personality dimensions · about 5 minutes',()=>personalQuestionnaire('big5')],
 ['Enneagram','Explore nine personality motivations',()=>personalQuestionnaire('enneagram')]
 ];
 for(const [title,description,fn]of entries){const b=personalButton('',()=>title==='Writing decoder'||title==='Introversion & extraversion'?fn():preparePersonalActivity(title,description,fn));b.className='personal-card';b.append(personalElement('strong',title),personalElement('span',description));const card=personalElement('div',undefined,'personal-card-wrap');card.append(b);if(title==='Introversion & extraversion'){const help=personalButton('?',()=>{const dialog=personalElement('dialog',undefined,'paradigm-dialog');dialog.append(personalElement('h2','EEG and personality: what is supported?'),personalElement('p','Published frontal-asymmetry associations explain very little variation in extraversion. We have no validated prediction rule for the Muse montage. Questionnaire results and EEG measurements stay separate while paired local data help evaluate future predictions.'));const link=personalElement('a','Research: frontal asymmetry and personality');link.href='https://doi.org/10.1002/per.2197';link.target='_blank';link.rel='noreferrer';dialog.append(link,personalButton('Close',()=>dialog.close()));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal()});help.className='personality-help';help.setAttribute('aria-label','EEG and personality: what is supported?');card.append(help)}cards.append(card)}
 if(personalCatalog.connected?.enabled){const c=personalCatalog.connected;setup.append(personalElement('p',`Connected locally: ${c.questionnaires} questionnaires · ${c.eeg_sessions} EEG activities · ${c.writing_sessions} writing sessions. ${c.model_status}`,'muted'));}
 renderPersonalHistory(area);
}
async function personalQuestionnaire(kind,resume=null,related=null){
 if(!resume&&!personalLeave())return;
 let recording;try{recording=resume||await api('personal/start',{kind,related_activity:related})}catch(e){$('headsetSetup').open=true;$('headsetSetup').scrollIntoView({behavior:'smooth'});throw e}
 activitySetupStep('personalSetup',true,()=>personalHome('insights'));personalBusy=true;personalKind=kind;journeyRun=true;journeySetStep('run');$('personalResults').open=false;document.body.classList.add('questionnaire-recording');$('headsetSetup').open=true;
 const endQuestionnaire=()=>{$('headsetSetup').open=false;clearInterval(personalTimer);personalBusy=false;document.body.classList.remove('questionnaire-recording')};

 const items=personalCatalog.questionnaires[kind],answers=recording.answers?.length===items.length?recording.answers:new Array(items.length).fill(null);let at=Math.max(0,answers.findIndex(x=>x===null));
 const host=$('personalSetupBody');host.replaceChildren();const layout=personalElement('div',undefined,'questionnaire-run-layout'),setup=personalElement('section',undefined,'questionnaire-task'),viewer=personalElement('section',undefined,'questionnaire-viewer');viewer.setAttribute('aria-label','Live personality estimates');layout.append(setup,viewer);host.append(layout);const toggle=personalButton('Hide live estimates',()=>{const hidden=viewer.hidden=!viewer.hidden;layout.classList.toggle('viewer-hidden',hidden);toggle.textContent=hidden?'Show live estimates':'Hide live estimates';toggle.setAttribute('aria-expanded',String(!hidden))});toggle.setAttribute('aria-expanded','true');toggle.className='questionnaire-view-toggle';host.prepend(toggle);const title=personalElement('h2',kind==='extraversion'?'Introversion & extraversion':kind==='big5'?'Big Five':'Enneagram');setup.append(title,personalElement('p',kind==='enneagram'?'Original reflection prompts. These do not establish an Enneagram type.':'Choose how accurately each statement describes you in everyday life.'));
 const eegStatus=personalElement('p','● EEG recording · answers and EEG stay local','questionnaire-status');viewer.append(eegStatus);const prediction=personalElement('section');prediction.id='livePersonalityEstimate';viewer.append(prediction);renderEEGPersonality(prediction,kind,recording.summary);personalTimer=setInterval(async()=>{try{const r=await api('personal/status',{});if(r.running){renderEEGPersonality(prediction,kind,r.summary);}eegStatus.textContent=r.running?`● ${r.source==='simulation'?'SYNTHETIC EEG':'EEG'} recording · ${r.summary.clean_clips} usable clips`:'EEG stopped — partial recording saved. Restart to complete the questionnaire.';if(!r.running){endQuestionnaire();next.disabled=true;choices.querySelectorAll('button').forEach(b=>b.disabled=true)}}catch(e){eegStatus.textContent=e.message;next.disabled=true}},1000);
 const progress=personalElement('p'),question=personalElement('h3'),choices=personalElement('div',undefined,'personal-answers'),controls=personalElement('div',undefined,'button-row');setup.append(progress,question,choices,controls);
 let answering=false;
 const advance=async()=>{if(!personalBusy)return;if(at<items.length-1){const target=at+1;await api('personal/questionnaire-event',{index:target});at=target;draw();return}const result=await api('personal/questionnaire',{kind,answers});endQuestionnaire();personalCatalog=await api('personal/catalog',{});renderPersonalResult(result);journeyFreshResult=true;journeySetStep('summary');};
 const draw=()=>{progress.textContent=`${at+1} / ${items.length}`;question.textContent=items[at].text;choices.replaceChildren();['Very inaccurate','Moderately inaccurate','Neither','Moderately accurate','Very accurate'].forEach((label,i)=>{const b=personalButton(label,async()=>{
 if(answering||!personalBusy)return;answering=true;const index=at;
 for(const button of choices.querySelectorAll('button')){button.disabled=true;button.setAttribute('aria-pressed',String(button===b))}back.disabled=true;next.disabled=true;
 try{await Promise.all([api('personal/questionnaire-event',{index,value:i+1}),new Promise(resolve=>setTimeout(resolve,220))]);answers[index]=i+1;await advance();}
 catch(error){if(personalBusy)draw();throw error}finally{answering=false}
 });b.setAttribute('aria-pressed',String(answers[at]===i+1));choices.append(b)});next.disabled=answers[at]===null;next.textContent=at===items.length-1?'Save & view results':'Next';next.hidden=answers[at]===null;back.disabled=at===0;};
 const back=personalButton('Back',async()=>{if(answering||!personalBusy)return;const target=at-1;if(target<0)return;await api('personal/questionnaire-event',{index:target});at=target;draw()}),next=personalButton('Next',async()=>{if(answering||!personalBusy)return;answering=true;next.disabled=true;try{await advance()}catch(error){if(personalBusy)draw();throw error}finally{answering=false}});
 controls.append(back,next,personalButton('Stop & save partial',async()=>{if(answering)return;await api('personal/stop',{});endQuestionnaire();personalCatalog=await api('personal/catalog',{});personalHome('insights')}));await api('personal/questionnaire-event',{index:at});draw();

}
function renderPersonalResult(r){
 chosenActivityTitle=({big5:'Big Five',enneagram:'Enneagram',reset:'Find your reset',meditation:'Meditation practice'})[r.kind]||r.kind.replaceAll('_',' ');
 const out=$('personalResultsBody');out.replaceChildren();
 out.append(personalElement('h2',r.kind==='reset'?'Your reset comparison':r.kind==='meditation'?'Your meditation session':r.kind==='social_probe'?'Your messaging response':r.kind==='eeg_profile'?'Your EEG profile':r.kind==='enneagram'?'Motivations you endorsed':'Questionnaire results'));
 if(r.synthetic)out.append(personalElement('p',r.subject_id+' · SYNTHETIC SUBJECT · invented answers and EEG','mind-demo-warning'));
 out.append(personalElement('p',new Date(r.created*1000).toLocaleString()+(r.source==='simulation'?' · SYNTHETIC DEMO DATA':''),'muted'));
 if(r.scores&&r.raw_eeg_file)out.append(personalElement('p',`EEG recorded alongside answers · ${Math.round((r.ended||r.created)-r.created)} seconds · ${r.summary?.clean_clips||0} usable clips. Raw EEG and timestamped answers saved together locally.`));
 if(r.scores&&['big5','enneagram'].includes(r.kind)){out.append(personalElement('h3','A · Questionnaire dimensions'));renderMindSummary(out,r);const estimate=personalElement('section');out.append(estimate);renderEEGPersonality(estimate,r.kind,r.summary);return}
 if(r.scores){for(const [name,value]of Object.entries(r.scores)){const row=personalElement('div',undefined,'personal-score');const label=personalElement('label',`${name} · ${value.toFixed(1)} / 5`),meter=document.createElement('meter');meter.min=1;meter.max=5;meter.value=value;meter.setAttribute('aria-label',name);row.append(label,meter);out.append(row)}out.append(personalElement('p',r.kind==='enneagram'?'Higher bars mean stronger endorsement of these prompts. This is not an Enneagram diagnosis or a conversion from Big Five scores.':'Scores reflect your answers on a 1–5 scale. They are not probabilities, percentiles or EEG predictions. Higher Extraversion scores indicate more endorsement of outgoing/social behavior.'));
 }else{
  const summary=r.summary||{};if(r.kind==='meditation'){const phases=summary.phases||{},deltas=['TP9','AF7','AF8','TP10'].map(ch=>{const before=phases.Baseline?.[ch]?.db?.[1],after=phases.Meditation?.[ch]?.db?.[1];return Number.isFinite(before)&&Number.isFinite(after)?after-before:null}).filter(Number.isFinite);out.append(personalElement('h3','Training target: alpha · 8–13 Hz'),personalElement('p',deltas.length?`Mean alpha change: ${(deltas.reduce((a,b)=>a+b,0)/deltas.length).toFixed(2)} dB from baseline. This measures the session, not evidence of lasting training benefit.`:'Not enough clean baseline and training data.'));}if(summary.hypothesis){const h=summary.hypothesis;out.append(personalElement('h3',h.text));const d=personalElement('details');d.append(personalElement('summary','Evidence & limitations'),personalElement('p',h.basis));if(h.source){const a=personalElement('a','Workload research');a.href=h.source;a.target='_blank';d.append(a)}out.append(d)}if(r.kind==='social_probe'){out.append(personalButton('Add your personality questionnaire',()=>personalQuestionnaire('extraversion',null,r.id)));const form=personalElement('div');const inputs={};for(const [key,label]of [['effort','How mentally effortful was messaging?'],['social_ease','How comfortable did reaching out feel?']]){const l=personalElement('label',label+' (1 low – 5 high)');const input=document.createElement('select');for(let i=1;i<=5;i++){const o=personalElement('option',String(i));o.value=i;input.append(o)}input.value='3';l.append(input);form.append(l);inputs[key]=input}form.append(personalButton('Save reflection',async()=>{await api('personal/reflection',{id:r.id,effort:+inputs.effort.value,social_ease:+inputs.social_ease.value});form.replaceChildren(personalElement('p','Reflection saved alongside your EEG.'))}));out.append(form)}out.append(personalElement('p',`${summary.clean_clips||0} usable clips / ${summary.total_clips||0} collected · ${r.reason||''}`));
  if(summary.ranking?.length){const best=summary.ranking.find(x=>x.change_db!==null);if(best)out.append(personalElement('h3','Largest measured EEG change: '+best.activity));for(const [i,item]of summary.ranking.entries()){const row=personalElement('div',undefined,'personal-score');row.append(personalElement('strong',item.activity),personalElement('p',item.change_db===null?'Not enough clean data':`${item.change_db.toFixed(2)} dB average absolute spectral change · ${item.channels} electrodes`));out.append(row)}out.append(personalElement('p','Measured change from baseline, not necessarily the most helpful or desirable state. Repeat on other days before calling it a reliable personal pattern.'))}
  for(const [phase,channels]of Object.entries(summary.phases||{})){const chart=personalElement('div',undefined,'personal-band-grid');chart.append(personalElement('h3',phase));for(const [ch,v]of Object.entries(channels)){const row=personalElement('div',undefined,'personal-band-row');row.append(personalElement('strong',ch+' · '+v.n+' clips'));if(v.db){v.db.forEach((power,i)=>{const label=personalElement('span',['Theta 4–8','Alpha 8–13','Low beta 13–20','High beta 20–30'][i]+' Hz: '+power.toFixed(1)+' dB');const bar=document.createElement('meter');bar.min=-30;bar.max=40;bar.value=power;bar.setAttribute('aria-label',label.textContent);row.append(label,bar)})}else row.append(personalElement('span','No usable signal'));chart.append(row)}out.append(chart);}
  if(r.kind==='eeg_profile')out.append(personalElement('p','This is an EEG measurement, not a personality classification. Repeat at a similar time and posture to explore stability.'));
  const rating=personalElement('div',undefined,'button-row');rating.append(personalElement('span',r.helpfulness?'Helpfulness saved: '+r.helpfulness+'/5':'How helpful did this feel?'));for(let i=1;i<=5;i++)rating.append(personalButton(String(i),async()=>{await api('personal/rate',{id:r.id,rating:i});rating.replaceChildren(personalElement('p','Helpfulness saved: '+i+'/5'));}));out.append(rating);
 }
}
function renderPersonalHistory(area){const out=$('personalResultsBody');const history=(personalCatalog.history||[]).filter(r=>area==='growth'?['reset','meditation'].includes(r.kind):!['reset','meditation'].includes(r.kind));if(!history.length){out.append(personalElement('p','Your saved results will appear here.'));return}const menu=document.createElement('select');menu.setAttribute('aria-label','Personal activity history');menu.hidden=true;history.forEach((r,i)=>{const o=personalElement('option',r.kind.replaceAll('_',' ')+' · '+new Date(r.created*1000).toLocaleString());o.value=i;menu.append(o)});menu.onchange=()=>{renderPersonalResult(history[+menu.value]);out.prepend(menu)};out.append(personalElement('p','Choose a saved activity to explore its results.'),personalButton('Browse saved results',openPreviousActivities));out.prepend(menu)}
async function startPersonal(kind){
 if(!personalLeave())return;try{personalCueAudio=personalCueAudio||new (window.AudioContext||window.webkitAudioContext)();await personalCueAudio.resume()}catch{};const result=await api('personal/start',{kind});await mountPersonalActivity(kind,result);
}
async function mountPersonalActivity(kind,result){
 personalCuePhase=null;personalBusy=true;personalKind=kind;personalLast=result;if(typeof journeySetStep==='function'){journeyRun=true;journeySetStep('run')};$('personalResultsBody').replaceChildren(personalElement('p','Recording this activity. Results are saved automatically.'));
 const setup=personalExerciseScreen();setup.replaceChildren();const status=personalElement('p');status.id='personalLiveStatus';const prompt=personalElement('h2');prompt.id='personalPrompt';const orb=personalElement('div',undefined,'personal-orb');orb.setAttribute('aria-hidden','true');orb.id='personalOrb';const feedback=personalElement('p');feedback.id='personalFeedback';setup.append(status,prompt,orb,createPersonalFeedback(kind),feedback,personalButton('Stop & save',async()=>{await api('personal/stop',{});await personalTick()}));
 await personalTick();if(personalBusy)personalTimer=setInterval(()=>personalTick().catch(e=>{clearInterval(personalTimer);toast(e.message+' — use Stop & save to retry.')}),1000);
}
async function personalTick(){
 if(!personalBusy)return;const r=await api('personal/status',{});personalLast=r;
 if(!r.running){clearInterval(personalTimer);personalTimer=null;personalBusy=false;$('headsetSetup').open=false;closePersonalExercise();personalCatalog=await api('personal/catalog',{});const latest=personalCatalog.history.find(x=>x.kind===personalKind);$('personalSetupBody').replaceChildren(personalElement('p','Recording saved.'),personalButton('Choose another activity',()=>personalHome(document.body.dataset.area)));if(latest){renderPersonalResult(latest);$('personalResults').open=true}if(typeof journeySetStep==='function')journeySetStep('summary');return}
 drawPersonalFeedback(r);
 if(personalCuePhase!==r.phase){if(personalCuePhase&&personalCueAudio){try{const o=personalCueAudio.createOscillator(),g=personalCueAudio.createGain();g.gain.value=.06;o.frequency.value=660;o.connect(g);g.connect(personalCueAudio.destination);o.start();o.stop(personalCueAudio.currentTime+.15)}catch{}}personalCuePhase=r.phase}
 $('personalLiveStatus').textContent=`${r.source==='simulation'?'SYNTHETIC DEMO · ':''}${r.phase} · ${Math.ceil(r.phase_remaining)} s in this step · ${Math.ceil(r.remaining)} s total`;$('personalPrompt').textContent=personalInstructions[r.phase]||r.phase;
 $('personalOrb').classList.toggle('breathing',r.phase==='Breathing'||r.phase==='Meditation');
 if(personalKind==='meditation'){const phases=r.summary.phases||{},differences=['TP9','AF7','AF8','TP10'].map(ch=>{const baseline=phases.Baseline?.[ch]?.db?.[1],current=phases.Meditation?.[ch]?.db?.[1];return Number.isFinite(baseline)&&Number.isFinite(current)?current-baseline:null}).filter(Number.isFinite);const delta=differences.length?differences.reduce((a,b)=>a+b,0)/differences.length:null;$('personalFeedback').textContent=delta===null?'Alpha training · collecting a clean baseline':`Alpha (8–13 Hz): ${delta>=0?'+':''}${delta.toFixed(1)} dB from baseline · aim to gently increase it`;$('personalOrb').style.opacity=delta===null?'.4':String(.2+.8/(1+Math.exp(-delta/3)));return}
 const ranking=r.summary.ranking||[],current=ranking.find(x=>x.activity===r.phase);$('personalFeedback').textContent=state?.motion?.moving?'Keep your head still; relax your jaw.':current?.change_db!==null&&current?.change_db!==undefined?`Spectral change from baseline: ${current.change_db.toFixed(2)} dB · change is not a calmness score`:`${r.summary.clean_clips} clean clips · keep your eyes open`;
 if(current?.change_db!==null&&current?.change_db!==undefined)$('personalOrb').style.opacity=String(.35+Math.min(.65,current.change_db/10));
}
async function openPersonalSettings(){
 const data=await api('personal/catalog',{}),d=$('personalSettings');$('personalizeChoice').checked=data.preferences.personalize;$('personalResearchChoice').checked=data.preferences.research_interest;d.showModal();
}
async function initPersonal(){
 personalCatalog=await api('personal/catalog',{});
 const nav=document.querySelector('aside nav'),lab=personalElement('div');lab.id='labLinks';for(const node of [...nav.children])if(node.id!=='typingNav')lab.append(node);nav.append(lab);
 const areas=personalElement('div',undefined,'area-navigation');for(const [id,title]of [['insights','👤 Learn About Your Mind'],['growth','🧘 Growth Exercises'],['bci','💻 BCI'],['lab','🧠 Learn About Your Brain'],['trainer','👁 Artifact trainer']]){const b=personalButton(title,()=>personalRoute(id));b.dataset.area=id;areas.append(b)}nav.prepend(areas);
 const links=personalElement('div');links.id='personalLinks';links.append(personalButton('Choose an activity',()=>personalRoute(document.body.dataset.area)),personalButton('Connected-data settings',openPersonalSettings));nav.append(links);
 $('typingNav').addEventListener('click',e=>{if(!personalLeave()){e.stopImmediatePropagation();return}document.body.classList.remove('personal-view');$('personalWorkspace').hidden=true;},true);
 const workspace=personalElement('section');workspace.id='personalWorkspace';workspace.hidden=true;
 for(const [id,title]of [['personalSetup','2 · Activity setup'],['personalResults','3 · Results']]){const d=personalElement('details',undefined,'panel workspace-section');d.id=id;d.open=id==='personalSetup';d.append(personalElement('summary',title));const body=personalElement('div');body.id=id+'Body';d.append(body);workspace.append(d)}$('headsetSetup').after(workspace);
 const d=personalElement('dialog');d.id='personalSettings';d.className='account-screen';d.innerHTML='<button class="dialog-close" id="closePersonalSettings" aria-label="Close connected-data settings">×</button><h2>Connected-data settings</h2><label class="check-label"><input id="personalizeChoice" type="checkbox"> Personalize my insights</label><p>Connect my activity data—including EEG, questionnaire answers, and locally recorded writing—to develop personal insights on this computer. Existing data may be included. Raw writing and embeddings remain local. This prototype records your choice; it does not yet predict personality from writing.</p><label class="check-label"><input id="personalResearchChoice" type="checkbox"> Contribute to research</label><p>Record my interest in future protected learning across these activities. Personal-insight and writing uploads are disabled. New consent describing the implemented sharing method will be required before they are enabled. ERP sharing is managed separately in Data Sharing Settings.</p><p>Both choices are optional. Turning personalization off stops future cross-activity linking; original activity records remain local.</p><button id="savePersonalSettings" class="primary">Save choices</button><p id="personalSettingsStatus" role="status"></p>';
 document.body.append(d);if($('sharingSettings')){const link=personalButton('Personal Insights & Growth settings',()=>{$('sharingSettings').close();openPersonalSettings()});link.className='info-link';$('sharingSettings').append(link)}$('closePersonalSettings').onclick=()=>d.close();$('savePersonalSettings').onclick=async()=>{try{await api('personal/preferences',{version:'personal-v1',personalize:$('personalizeChoice').checked,research_interest:$('personalResearchChoice').checked});personalCatalog=await api('personal/catalog',{});d.close();toast('Connected-data choices saved.')}catch(e){$('personalSettingsStatus').textContent=e.message}};
 let area='insights';try{area=localStorage.getItem('bandstandArea')||area}catch{};personalRoute(['insights','growth','lab','bci'].includes(area)?area:'insights');
 if(personalCatalog.running){const r=await api('personal/status',{});if(r.running){personalRoute(['reset','meditation'].includes(r.kind)?'growth':'insights');if(['extraversion','big5','enneagram'].includes(r.kind))await personalQuestionnaire(r.kind,r);else await mountPersonalActivity(r.kind,r)}}
 window.addEventListener('beforeunload',e=>{if(personalBusy){e.preventDefault();e.returnValue=''}});
}

personalInstructions['Browse messages']='Open your usual messenger app and browse existing conversations for one minute. Read naturally; keep your head and jaw relaxed. No message contents are captured by this activity.';
personalInstructions['Send a message']='For one minute, compose and send someone an ordinary message you choose. If you finish early, stay with the conversation. You control the recipient and the message; Bandstand does not send or record it.';
function socialIntro(){activityResume.insights=socialIntro;activitySetupStep('personalSetup',true,()=>personalHome('insights'));const setup=$('personalSetupBody');setup.replaceChildren(personalElement('h2','Your response to social interaction'),personalElement('p','Two steps, one minute each. First browse your messages; then compose and send a message. Keep Bandstand visible beside your messenger, or use your phone. EEG records throughout. Afterwards, add your questionnaire and rate your experience to build a paired personal dataset.'),personalElement('p','This new task explores differences in your response; it is not a validated EEG test of introversion or extraversion.'),personalButton('Start messaging activity',()=>startPersonal('social_probe')))}
function personalExerciseScreen(){let screen=$('personalExercise');if(!screen){screen=personalElement('section');screen.id='personalExercise';screen.setAttribute('aria-label','Activity recording');screen.setAttribute('role','region');document.body.append(screen)}screen.hidden=false;document.body.classList.add('personal-exercising');return screen}
function closePersonalExercise(){if($('personalExercise')){$('personalExercise').hidden=true;$('personalExercise').replaceChildren()}document.body.classList.remove('personal-exercising')}
document.addEventListener('keydown',async e=>{if(e.key==='Escape'&&personalBusy&&document.body.classList.contains('personal-exercising')){await api('personal/stop',{});await personalTick()}});

let personalCueAudio=null,personalCuePhase=null;

function createPersonalFeedback(kind){
 const box=personalElement('section',undefined,'personal-live-feedback');box.id='personalLiveFeedback';
 const title=personalElement('h3',kind==='meditation'?'Meditation · live EEG':kind==='reset'?'Your response to this exercise':kind==='social_probe'?'Your EEG during social interaction':'Your EEG while you respond');
 const select=document.createElement('select');select.id='personalLiveBand';select.setAttribute('aria-label','Live EEG frequency band');['Theta · 4–8 Hz','Alpha · 8–13 Hz','Low beta · 13–20 Hz','High beta · 20–30 Hz'].forEach((t,i)=>{const o=personalElement('option',t);o.value=i;select.append(o)});select.value=['meditation','reset','eeg_profile'].includes(kind)?'1':'0';if(kind==='meditation'){select.disabled=true;select.title='Training target: alpha power, 8–13 Hz';}select.onchange=()=>{if(box._data)drawPersonalFeedback(box._data)};
 const plot=personalElement('div');plot.id='personalLivePlot';plot.setAttribute('aria-live','off');box.append(title,select,plot,personalElement('small','Last 60 seconds · 2-second EEG clips · gaps mark rejected data. Dashed line: baseline when available. Power is not a personality or calmness score.'));return box;
}
function drawPersonalFeedback(r){
 const box=$('personalLiveFeedback');if(!box)return;box._data=r;const host=$('personalLivePlot');host.replaceChildren();const band=+$('personalLiveBand').value,clips=r.recent_clips||[],channels=['TP9','AF7','AF8','TP10'],palette=['#198574','#c78e48','#679bb1','#9b83b0'];
 const vals=clips.flatMap(c=>channels.map(ch=>c.power[ch]?.[band]).filter(Number.isFinite));const refs=channels.map(ch=>r.summary?.phases?.Baseline?.[ch]?.db?.[band]);const all=vals.concat(refs.filter(Number.isFinite));let low=all.length?Math.floor(Math.min(...all)/5)*5:0,high=all.length?Math.ceil(Math.max(...all)/5)*5:20;if(high-low<10)high=low+10;
 const end=clips.at(-1)?.time||0,start=end-60;
 channels.forEach((ch,i)=>{const row=personalElement('div',undefined,'live-band-row'),last=clips.at(-1),value=last?.power[ch]?.[band];row.append(personalElement('strong',ch),personalElement('span',Number.isFinite(value)?value.toFixed(1)+' dB':last?'No clean clip':'Collecting…'));
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 500 70');svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('role','img');svg.setAttribute('aria-label',`${ch} band power over the last 60 seconds, ${low} to ${high} dB`);
 const y=v=>60-(v-low)/(high-low)*50;let d='',pen=false,prior=null;for(const c of clips){const v=c.power[ch]?.[band];if(!Number.isFinite(v)){pen=false;continue}if(prior!==null&&c.time-prior>3)pen=false;d+=(pen?'L':'M')+(30+(c.time-start)/60*460).toFixed(1)+' '+y(v).toFixed(1)+' ';pen=true;prior=c.time}
 const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);path.setAttribute('fill','none');path.setAttribute('stroke',palette[i]);path.setAttribute('stroke-width','2');svg.append(path);
 if(Number.isFinite(refs[i])){const line=document.createElementNS(svg.namespaceURI,'path');line.setAttribute('d',`M30 ${y(refs[i])}H490`);line.setAttribute('stroke','#8b9290');line.setAttribute('stroke-dasharray','4 4');svg.append(line)}
 for(const [v,pos]of [[high,12],[low,61]]){const text=document.createElementNS(svg.namespaceURI,'text');text.textContent=v;text.setAttribute('x','0');text.setAttribute('y',pos);text.setAttribute('font-size','12');text.setAttribute('fill','currentColor');svg.append(text)}row.append(svg);host.append(row)});
}

function renderMindSummary(out,result){
 const fixture=mindDemoData.datasets[result.kind],preview=Boolean(result.synthetic)||result.source==='synthetic-preview';
 const warning=personalElement('p','SYNTHETIC REFERENCE DATA · 120 invented profiles. These comparisons are for testing the display, not population norms or validated EEG predictions.','mind-demo-warning');out.append(warning);
 const controls=personalElement('div',undefined,'live-view-tabs'),body=personalElement('div');out.append(controls,body);
 const help=personalElement('p',result.kind==='enneagram'?'These nine single-item reflection scores do not establish an Enneagram type. Reference scores and EEG are independently invented; there is no learned prediction model.':'Scores use your IPIP answers on a 1–5 scale. The reference scores and EEG are independently invented, not research norms or a learned prediction model.');controls.append(headsetHelp('About these results',[help]));
 const draw=mode=>{body.replaceChildren();for(const button of controls.querySelectorAll('[data-summary]'))button.setAttribute('aria-pressed',String(button.dataset.summary===mode));
 if(mode==='scores'){
 body.append(personalElement('p',preview?'Example answers · synthetic':'Your questionnaire answers','muted'));
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 720 '+(fixture.domains.length*46+48));svg.setAttribute('role','img');svg.setAttribute('aria-label','Questionnaire scores compared with synthetic reference profiles');svg.style.width='100%';body.append(svg);
 const node=(name,attrs,text)=>{const n=document.createElementNS(svg.namespaceURI,name);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n)};
 const x=v=>210+(v-1)*116;
 for(let v=1;v<=5;v++){node('line',{x1:x(v),x2:x(v),y1:10,y2:fixture.domains.length*46,stroke:'#e1e7ee'});node('text',{x:x(v),y:fixture.domains.length*46+25,fill:'#7c8995','font-size':12},String(v))}
 fixture.domains.forEach((name,i)=>{const y=26+i*46,values=fixture.participants.map(p=>p.scores[name]).sort((a,b)=>a-b),value=result.scores[name];node('text',{x:0,y:y+4,fill:'#28465f','font-size':13},name);node('line',{x1:x(values[3]),x2:x(values[116]),y1:y,y2:y,stroke:'#bac6d1','stroke-width':10,'stroke-linecap':'round'});node('circle',{cx:x(value),cy:y,r:6,fill:'#198574'});node('text',{x:690,y:y+4,fill:'#28465f','font-size':12},value.toFixed(1))});
 body.append(personalElement('p','Green: '+(preview?'example':'your')+' answers · Gray: middle 95% of invented reference scores (not a confidence interval).','muted'));
 }else{
 body.append(personalElement('p','SYNTHETIC EEG · example profile, not your recording','mind-demo-warning'));const chart=document.createElement('canvas');chart.id='mindDemoSpectrum';chart.height=300;body.append(chart);
 requestAnimationFrame(()=>{if(!chart.isConnected)return;const {ctx,w,h}=canvas(chart.id),l=48,r=w-15,t=40,b=h-35,entry=result.psd?{psd:result.psd}:fixture.participants[0],max=Math.max(...entry.psd.flat())*1.15;drawFrequencyGuides(ctx,l,r,t,b,false);text(ctx,'µV²/Hz',0,14);boot.channels.forEach((ch,i)=>{text(ctx,ch,l+i*70,24,colors[i],11);line(ctx,entry.psd[i].map((v,j)=>[l+(fixture.frequencies[j]-1)/39*(r-l),b-v/max*(b-t)]),colors[i],1.6)});for(let i=0;i<=4;i++){const y=b-i*(b-t)/4;line(ctx,[[l,y],[r,y]],'#e1e7ee');text(ctx,(max*i/4).toFixed(1),0,y+3)}for(const f of [1,10,20,30,40])text(ctx,String(f),l+(f-1)/39*(r-l),b+17);text(ctx,'Hz',r-12,b+30)});
 }
 };
 for(const [mode,title] of [['scores','Questionnaire'],['eeg','Example power spectrum']]){const b=personalButton(title,()=>draw(mode));b.dataset.summary=mode;controls.prepend(b)}draw('scores');
}

// Display-only synthetic nearest-neighbor demonstration. Answers never enter this function.
function eegPersonalityDemo(kind,summary){
 const fixture=mindDemoData.datasets[kind];if(!fixture||!summary||summary.clean_clips<3)return null;
 const bands=[[4,8],[8,13],[13,20],[20,30]],channels=['TP9','AF7','AF8','TP10'],features=[];
 channels.forEach((ch,c)=>bands.forEach(([lo,hi],b)=>{const rows=Object.values(summary.phases||{}).map(p=>p[ch]).filter(v=>v?.n>0&&Number.isFinite(v.db?.[b]));const n=rows.reduce((a,v)=>a+v.n,0);if(n)features.push({c,b,lo,hi,value:rows.reduce((a,v)=>a+v.db[b]*v.n,0)/n})}));if(!features.length)return null;
 const neighbors=fixture.participants.map(p=>({p,d:features.reduce((sum,f)=>{const power=p.psd[f.c].reduce((a,v,j)=>a+(fixture.frequencies[j]>=f.lo&&fixture.frequencies[j]<f.hi?v*.5:0),0);return sum+(10*Math.log10(Math.max(power,1e-12))-f.value)**2},0)/features.length})).sort((a,b)=>a.d-b.d).slice(0,5);
 return Object.fromEntries(fixture.domains.map(name=>[name,neighbors.reduce((sum,n)=>sum+n.p.scores[name],0)/neighbors.length]));
}
function renderEEGPersonality(host,kind,summary){
 host.replaceChildren(personalElement('h3','B · EEG-only dimensions · synthetic model demo'),personalElement('p','Demo only: EEG is matched to invented profiles whose personality scores were assigned independently. These values have no demonstrated personality accuracy. Questionnaire answers are not used.','mind-demo-warning'));
 const scores=eegPersonalityDemo(kind,summary);if(!scores){host.append(personalElement('p','Waiting for at least 3 usable EEG clips.'));return}
 for(const [name,value]of Object.entries(scores)){const row=personalElement('div',undefined,'personal-score'),meter=document.createElement('meter');meter.min=1;meter.max=5;meter.value=value;meter.setAttribute('aria-label',name+' synthetic estimate');row.append(personalElement('label',name+' · '+value.toFixed(1)+' / 5'),meter);host.append(row)}
}
