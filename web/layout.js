/* One hierarchy for all workspaces; acquisition remains a shared component. */
let cleanLayoutReady=false,labTypeChosen=false;
function arrangeWorkspace(kind){
 if(!cleanLayoutReady)return;
 const setup=$(kind==='personal'?'personalSetup':kind==='writing'?'writingParadigm':'experimentParadigm');
 if(setup&&$('headsetSetup')){setup.open=true;setup.after($('headsetSetup'))}
}
function initCleanLayout(){
 document.querySelector('main > header').hidden=true;
 const aside=document.querySelector('aside');
 const toggle=document.createElement('button');toggle.id='sidebarToggle';toggle.type='button';toggle.textContent='‹';toggle.title='Collapse navigation';toggle.setAttribute('aria-label','Collapse navigation');toggle.setAttribute('aria-expanded','true');
 toggle.onclick=()=>{const closed=document.body.classList.toggle('sidebar-collapsed');toggle.textContent=closed?'☰':'‹';toggle.setAttribute('aria-expanded',String(!closed));toggle.title=closed?'Expand navigation':'Collapse navigation';toggle.setAttribute('aria-label',toggle.title)};aside.prepend(toggle);
 const profile=document.createElement('button');profile.id='collapsedProfile';profile.type='button';profile.setAttribute('aria-label','Account');profile.title='Account';profile.innerHTML='<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 22v-3a8 8 0 0 1 16 0v3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';profile.onclick=()=>$('accountNav').click();aside.append(profile);
 const stageToggle=document.createElement('button');stageToggle.id='liveResultsToggle';stageToggle.type='button';stageToggle.textContent='∿';stageToggle.setAttribute('aria-label','Expand live results');stageToggle.title='Expand live results';stageToggle.setAttribute('aria-expanded','false');
 $('stage').classList.add('results-collapsed');stageToggle.onclick=()=>{const closed=$('stage').classList.toggle('results-collapsed');stageToggle.setAttribute('aria-expanded',String(!closed));stageToggle.title=closed?'Expand live results':'Collapse live results';stageToggle.setAttribute('aria-label',stageToggle.title)};$('stage').append(stageToggle);
 for(const id of ['headsetSetup','writingResults','experimentResults','personalResults'])$(id).open=false;
 for(const id of ['writingParadigm','experimentParadigm','personalSetup']){$(id).open=true;$(id).querySelector('summary').textContent='Activity setup'}
 $('headsetSetup').querySelector('summary').textContent='Headset setup';for(const id of ['writingResults','experimentResults','personalResults'])$(id).querySelector('summary').textContent='Results';
 const modes=document.createElement('div');modes.className='activity-types';modes.setAttribute('aria-label','Experiment type');
 for(const m of ['erp','tf']){const b=document.querySelector(`[data-mode="${m}"]`);modes.append(b)}
 document.querySelector('[data-mode="bio"]').hidden=true;$('designSection').prepend(modes);
 const tools=document.createElement('details');tools.className='settings-disclosure lab-tools';tools.innerHTML='<summary>Research tools</summary>';tools.append($('labLinks'));$('experimentParadigm').append(tools);
 const setup=document.querySelector('.setup'),advanced=document.createElement('details'),expected=document.createElement('details');advanced.id='advancedSettings';expected.id='expectedResults';advanced.className=expected.className='settings-disclosure';advanced.innerHTML='<summary>Advanced settings</summary>';expected.innerHTML='<summary>Expected results</summary>';
 advanced.append($('trialCount').closest('.form-grid'));for(const id of ['analysis','cleaning','timing']){const pane=$('setup-'+id);pane.classList.remove('hidden');const title=document.createElement('h3');title.textContent={analysis:'Analysis',cleaning:'Artifact rejection',timing:'Timing & display'}[id];pane.prepend(title);advanced.append(pane)}
 const notes=$('setup-notes');notes.classList.remove('hidden');expected.append($('protocolDescription'),notes);setup.querySelector('.setup-nav').remove();setup.querySelector('.start-row').before(advanced,expected);
 // The selected protocol supplies the scientific context; omit the duplicate fixed guide.
 for(const d of $('experimentParadigm').querySelectorAll(':scope > details:not(.lab-tools)'))d.remove();
 $('personalLinks').hidden=true;$('typingNav').hidden=true;
 for(const section of [advanced,expected]){const dialog=document.createElement('dialog');dialog.className='paradigm-dialog';const close=document.createElement('button');close.type='button';close.textContent='Close';close.onclick=()=>dialog.close();dialog.append(close,section);document.body.append(dialog);section.open=true}
 setup.querySelector('.panel-heading').hidden=true;
 $('protocols').hidden=true;setup.hidden=true;
 for(const b of modes.children){b.classList.remove('active');b.onclick=()=>{if(active||state?.typing?.running)return;labTypeChosen=true;$('protocols').hidden=false;setup.hidden=false;setMode(b.dataset.mode)}}
 if(document.body.classList.contains('questionnaire-recording'))$('headsetSetup').open=true;
 cleanLayoutReady=true;
 arrangeWorkspace(document.body.classList.contains('personal-view')?'personal':typingView?'writing':'lab');
}
