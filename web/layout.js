/* One hierarchy for all workspaces; acquisition remains a shared component. */
let cleanLayoutReady=false,labTypeChosen=false;
function arrangeWorkspace(kind){
 if(!cleanLayoutReady)return;
 const setup=$(kind==='personal'?'personalSetup':kind==='writing'?'writingParadigm':'experimentParadigm');
 if(setup&&$('headsetSetup')){setup.open=true;document.querySelector('main').prepend($('headsetSetup'))}
}
function initCleanLayout(){
 document.querySelector('main > header').hidden=true;
 const aside=document.querySelector('aside');
 const toggle=document.createElement('button');toggle.id='sidebarToggle';toggle.type='button';toggle.textContent='‹';toggle.title='Collapse navigation';toggle.setAttribute('aria-label','Collapse navigation');toggle.setAttribute('aria-expanded','true');
 toggle.onclick=()=>{const closed=document.body.classList.toggle('sidebar-collapsed');toggle.textContent=closed?'☰':'‹';toggle.setAttribute('aria-expanded',String(!closed));toggle.title=closed?'Expand navigation':'Collapse navigation';toggle.setAttribute('aria-label',toggle.title)};aside.prepend(toggle);
 const profile=document.createElement('button');profile.id='collapsedProfile';profile.type='button';profile.setAttribute('aria-label','Account');profile.title='Account';profile.innerHTML='<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 22v-3a8 8 0 0 1 16 0v3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';profile.onclick=()=>$('accountNav').click();aside.append(profile);
 const stageToggle=document.createElement('button');stageToggle.id='liveResultsToggle';stageToggle.type='button';stageToggle.textContent='∿';stageToggle.setAttribute('aria-label','Expand live results');stageToggle.title='Expand live results';stageToggle.setAttribute('aria-expanded','false');
 $('stage').classList.remove('results-collapsed');stageToggle.setAttribute('aria-expanded','true');stageToggle.textContent='Hide EEG';stageToggle.onclick=()=>{const closed=$('stage').classList.toggle('results-collapsed');stageToggle.setAttribute('aria-expanded',String(!closed));stageToggle.textContent=closed?'Show EEG':'Hide EEG';stageToggle.title=closed?'Expand live results':'Collapse live results';stageToggle.setAttribute('aria-label',stageToggle.title)};$('stage').append(stageToggle);
 for(const id of ['headsetSetup','writingResults','experimentResults','personalResults'])$(id).open=false;
 for(const id of ['writingParadigm','experimentParadigm','personalSetup']){$(id).open=true;$(id).querySelector('summary').textContent='Activity setup'}
 $('headsetSetup').querySelector('summary').textContent='Headset setup';for(const id of ['writingResults','experimentResults','personalResults'])$(id).querySelector('summary').textContent='Results';
 activitySetupStep('writingParadigm',true,()=>personalRoute('insights'));
 const tabs=document.createElement('div');tabs.className='activity-step-nav';tabs.setAttribute('role','tablist');$('designSection').prepend(tabs);
 const modes=document.createElement('div');modes.className='activity-types';modes.setAttribute('aria-label','Experiment type');
 for(const m of ['erp','tf']){const b=document.querySelector(`[data-mode="${m}"]`);modes.append(b)}
 document.querySelector('[data-mode="bio"]').hidden=true;tabs.after(modes);
 const tools=document.createElement('div');tools.hidden=true;tools.className='retired-research-tools';tools.append($('labLinks'));document.body.append(tools);
 const setup=document.querySelector('.setup'),advanced=document.createElement('details'),expected=document.createElement('details');advanced.id='advancedSettings';expected.id='expectedResults';advanced.className=expected.className='settings-disclosure';advanced.innerHTML='<summary>Advanced settings</summary>';expected.innerHTML='<summary>Expected results</summary>';
 advanced.append($('trialCount').closest('.form-grid'));for(const id of ['analysis','cleaning','timing']){const pane=$('setup-'+id);pane.classList.remove('hidden');const title=document.createElement('h3');title.textContent={analysis:'Analysis',cleaning:'Artifact rejection',timing:'Timing & display'}[id];pane.prepend(title);advanced.append(pane)}
 const notes=$('setup-notes');notes.classList.remove('hidden');expected.append($('protocolDescription'),notes);setup.querySelector('.setup-nav').remove();setup.querySelector('.start-row').before(advanced,expected);
 // The selected protocol supplies the scientific context; omit the duplicate fixed guide.
 for(const d of $('experimentParadigm').querySelectorAll(':scope > details:not(.lab-tools)'))d.remove();
 $('personalLinks').hidden=true;$('typingNav').hidden=true;
 for(const section of [expected]){const dialog=document.createElement('dialog');dialog.className='paradigm-dialog';const close=document.createElement('button');close.type='button';close.textContent='Close';close.onclick=()=>dialog.close();dialog.append(close,section);document.body.append(dialog);section.open=true}
 setup.querySelector('.panel-heading').hidden=true;
 const choose=document.createElement('button'),settings=document.createElement('button');choose.textContent='Select an activity';settings.textContent='Settings & start';
 for(const b of [choose,settings]){b.type='button';b.setAttribute('role','tab');tabs.append(b)}
 window.showLabStep=step=>{if(typeof journeySetStep==='function')journeySetStep(step==='settings'?'setup':'choose');const selected=step==='settings';modes.hidden=true;$('protocols').hidden=selected||!labTypeChosen;setup.hidden=!selected;choose.setAttribute('aria-selected',String(!selected));settings.setAttribute('aria-selected',String(selected));settings.disabled=!labTypeChosen;};
 choose.onclick=()=>{if(personalLeave())showLabStep('choose')};settings.onclick=()=>{if(personalLeave())showLabStep('settings')};addActivityPreview(tabs);showLabStep('choose');
 for(const b of modes.children){b.classList.remove('active');b.onclick=()=>{if(!personalLeave())return;labTypeChosen=true;setMode(b.dataset.mode);showLabStep('choose')}}
 const feedback=document.createElement('p');feedback.id='typingStartFeedback';feedback.setAttribute('role','status');feedback.className='typing-start-feedback';$('typingModes').after(feedback);
 $('typingStart').hidden=true;$('writingEditor').placeholder='Write here while recording. Your text saves automatically.';
 if(document.body.classList.contains('questionnaire-recording'))$('headsetSetup').open=true;
 cleanLayoutReady=true;initJourney();
 arrangeWorkspace(document.body.classList.contains('personal-view')?'personal':typingView?'writing':'lab');
}

function addActivityPreview(nav){
 const button=document.createElement('button');button.type='button';button.className='activity-eeg-preview';button.title='Open headset setup';button.setAttribute('aria-label','Live EEG preview — open headset setup');
 const c=document.createElement('canvas');c.width=120;c.height=30;const label=document.createElement('small');label.textContent='EEG';button.append(c,label);button.onclick=()=>{$('headsetSetup').open=true;$('headsetSetup').scrollIntoView({behavior:'smooth',block:'start'})};nav.append(button);
}
function drawActivityPreview(){
 for(const button of document.querySelectorAll('.activity-eeg-preview')){
  if(!button.offsetWidth)continue;
  const c=button.querySelector('canvas'),ctx=c.getContext('2d');ctx.clearRect(0,0,120,30);
  const t=state?.trace,live=!state?.stale&&t?.times?.length>1;button.querySelector('small').textContent=live?(state.source==='live'?'Live EEG':'Demo EEG'):'No EEG';
  if(!live)continue;
  const end=t.times.at(-1),start=end-2;
  for(let ch=0;ch<4;ch++){ctx.strokeStyle=['#258c7e','#c78b38','#599fb5','#9479ac'][ch];ctx.globalAlpha=.8;ctx.beginPath();let begun=false;for(let i=0;i<t.times.length;i++){if(t.times[i]<start)continue;const v=t.values[i]?.[ch];if(!Number.isFinite(v)){begun=false;continue}const x=(t.times[i]-start)*60,y=4+ch*7-Math.max(-3,Math.min(3,v*.05));if(begun)ctx.lineTo(x,y);else ctx.moveTo(x,y);begun=true}ctx.stroke()}
 }
}
