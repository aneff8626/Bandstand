let typingStaleSince=null;
const inferenceFeed=createInferenceFeed();
let typingWasRunning=false,typingStarting=false;
/* Free-writing acquisition. Text is sent as labels; it is never a decoder input. */
let typingAccessState=null,typingMarkerSequence=0,typingStopping=false,typingView=false,typingWord=null,typingChain=Promise.resolve(),typingDocTimer=null,typingPlotRevision=-1;
function typingEvent(body){typingChain=typingChain.then(()=>api('typing/event',body)).catch(e=>{toast(e.message);$('typingStatus').textContent='Recording issue: '+e.message});return typingChain}
function updateTypingMode(){
 const running=!!state?.typing?.running,system=(running?state.typing.session?.capture:$('typingCapture').value)==='system';
 $('writingEditor').hidden=system;
 for(const [id,on] of [['typingModeEditor',!system],['typingModeSystem',system]]){$(id).setAttribute('aria-pressed',String(on));$(id).disabled=running||typingStarting;$(id).textContent=running&&on?'● Recording '+(system?'across apps':'in Bandstand'):typingStarting&&on?'Starting…':id==='typingModeEditor'?'Write in Bandstand app':'Write across all apps';}
 if((typeof boot!=='undefined'&&boot?.capabilities?.windows_preview)){$('typingModeSystem').disabled=true;$('typingModeSystem').title='Not available in the Windows preview';}
 $('typingAccess').hidden=!system||!!typingAccessState?.available;
 $('typingCheckAccess').hidden=!system||!window.museNative||!!typingAccessState?.available;
}
function chooseTypingMode(capture){
 if(state?.typing?.running)return;
 $('typingCapture').value=capture;updateTypingMode();
 if(capture==='system')checkTypingAccess();
}
$('typingModeEditor').onclick=()=>startWriting('editor');
$('typingModeSystem').onclick=()=>startWriting('system');
function selectTypingView(on){
 if(active)return toast('Finish the experiment before changing workspace.');
 if(state?.typing?.running&&!on)return toast('Stop the typing recording before changing workspace.');
 if(typeof arrangeWorkspace==='function')arrangeWorkspace(on?'writing':document.body.classList.contains('personal-view')?'personal':'lab');
 typingView=on;if(on)document.querySelectorAll('[data-mode]').forEach(b=>b.classList.remove('active'));document.body.classList.toggle('typing-view',on);show('typingWorkspace',on);$('typingNav').classList.toggle('active',on);
 if(on){$('modeCrumb').textContent='WRITING DECODER';$('pageTitle').textContent='Writing decoder';$('pageSubtitle').textContent='';show('developerPanel',false)}else setMode(mode);
}
function closeTypingWord(cancel=false){
 if(!typingWord)return Promise.resolve();const w=typingWord;typingWord=null;
 return typingEvent({kind:cancel?'cancel':'commit',id:w.id,text:w.text,onset:now(),edited:w.edited,unsupported:w.unsupported});
}
async function stopTyping(reason='Stopped by writer'){
 if(typingStopping)return;typingStopping=true;try{
 clearTimeout(typingDocTimer);if(state.typing?.session?.capture!=='system'){await closeTypingWord();await typingEvent({kind:'document',onset:now(),text:$('writingEditor').value});}await typingChain;
 if(state.typing?.session?.capture==='system')await api('system_typing/stop',{}).catch(()=>{});state.typing=await api('typing/stop',{reason});$('headsetSetup').open=false;renderTyping();await checkTypingAccess();}finally{typingStopping=false}
}
function renderTyping(){
 const d=state?.typing;if(!d)return;const running=d.running;updateTypingMode();const feedback=$('typingStartFeedback');if(feedback&&running)feedback.textContent=(d.capture_status?.paused?'● EEG recording · typing paused · ':'● Recording · ')+Math.floor(Math.max(0,Date.now()/1000-(d.session?.started||Date.now()/1000))/60)+' min · '+(d.lifetime_words??d.total??0)+' dataset words · '+(d.semantic_phrases||0)+' phrases · '+(d.session?.capture==='system'?'Across apps':'In Bandstand')+' · saved automatically';if(feedback&&!running&&typingWasRunning)feedback.textContent='Recording saved. Choose where to write to start a new session.';if(running&&state.stale){typingStaleSince??=Date.now()}else typingStaleSince=null;if(running&&state.stale&&Date.now()-typingStaleSince>=3000){typingStaleSince=null;stopTyping('EEG signal lost').catch(e=>toast(e.message));return}
 $('typingExport').disabled=running||!d.session;
 $('typingStart').textContent=running?(d.capture_status?.paused?'Keystroke monitoring paused':'Keystroke monitoring in progress'):'Start recording';
 const preview=$('typingCapturePreview');if(preview){preview.hidden=!running;const last=d.session?.capture==='system'?d.capture_preview:{text:$('writingEditor').value.slice(-160),app:'Bandstand',at:Date.now()/1000};preview.textContent=last?.text?'Last captured: “'+redactPhrase(last.text)+'” · '+(last.app||'Another app')+' · '+new Date(last.at*1000).toLocaleTimeString():(d.session?.capture==='system'?'Waiting for typing in another app…':'Ready for your writing below…');}
 $('typingRestart').textContent=running?'Save session & continue':'Continue recording';
 $('typingRequirements').textContent=typingAccessState?.available?'Typing access available.':'Enable typing access to record across apps.';
 $('typingStart').disabled=running||active||!!state.developer?.recording||state.stale||(state.source!=='live'&&!(typeof boot!=='undefined'&&boot?.capabilities?.windows_preview));show('typingStop',true);$('typingStop').disabled=!running;$('typingWindow').disabled=running;
 $('typingStatus').textContent=running?'Recording locally · space or Enter completes a word':d.session?(d.session.stop_reason||'Recording saved locally'):'Ready when you are';
 $('writingEditor').readOnly=running&&d.session?.capture==='system';
 for(const id of ['typingHistory','typingDelay','typingCapture']){$(id).disabled=running||typingStarting;}
 if(running&&d.session?.capture==='system'){
  const capture=d.capture_status||{},paused=!!capture.paused;
  $('typingStatus').textContent=(paused?'EEG recording · typing paused: ':'')+(capture.reason||'Recording EEG · type in another app');
  if(paused&&/Secure input/i.test(capture.reason||''))$('typingStatus').textContent+=' · Another app has enabled macOS Secure Keyboard Entry. An ordinary open Terminal does not block capture.';
  $('typingStatus').classList.toggle('capture-paused',paused);
 }else $('typingStatus').classList.remove('capture-paused');
 $('typingCounts').textContent=`${d.accepted} usable · ${d.rejected} excluded · ${d.pending} pending`;
 $('typingPrediction').textContent=(d.prediction?.word?redactPhrase(d.prediction.word):null)||(d.decoder?.ready?'No confident estimate':'Collecting evidence');
 $('typingPredictionNote').textContent=d.prediction?.reason||d.decoder?.reason||'No EEG prediction yet.';
 const r=d.decoder;$('typingEvidence').textContent=r?.accuracy!==undefined?`Later-block accuracy ${(r.accuracy*100).toFixed(1)}% · balanced ${(r.balanced_accuracy*100).toFixed(1)}% · chance ${(r.chance*100).toFixed(1)}% · majority ${(r.majority_accuracy*100).toFixed(1)}% · ${r.validation_trials} validation words. ${r.reason}`:r?.reason||'';
 if(r?.kind==='semantic')$('typingEvidence').textContent=r.cosine!==undefined?`${r.training_phrases} live-model training phrases · ${r.validation_trials} held-out phrases · EEG cosine ${r.cosine.toFixed(3)} · text-history baseline ${r.text_history_baseline.toFixed(3)} · quality baseline ${r.mask_baseline.toFixed(3)} · gain over strongest baseline ${r.gain.toFixed(3)}. ${r.reason}`:r.reason;
 const feed=inferenceFeed.update(d.prediction,performance.now());
 if(feed.current){$('typingPrediction').textContent=feed.current.gist?redactPhrase(feed.current.gist):'Meaning unclear';$('typingPredictionNote').textContent=(feed.current.validated?'Exploratory':'Ultra-tentative · unvalidated')+' · similarity '+feed.current.score.toFixed(3)+' · '+(running?'Receiving live EEG matches':'Recording stopped; last match shown')+'. Similarity is not probability.';}
 $('semanticCandidates').textContent=feed.mode==='best'?'Stronger or repeated matches, held for reading time plus up to 5 seconds.':'All received matches in history; the headline stays long enough to read.';
 const details=$('gistMatches');if(details){const key=JSON.stringify(feed.current?.matches||[]);if(details.dataset.key!==key){details.dataset.key=key;const list=$('gistMatchList');list.replaceChildren(...(feed.current?.matches||[]).map(m=>{const p=document.createElement('p');p.textContent=redactPhrase(m.text)+' · similarity '+m.similarity.toFixed(3);return p}));}}
 const historyKey=feed.mode+JSON.stringify(feed.previous.map(x=>[redactPhrase(x.text),x.time]));
 if($('inferenceHistory').dataset.key!==historyKey){$('inferenceHistory').dataset.key=historyKey;$('inferenceHistory').replaceChildren(...feed.previous.map(item=>{const row=document.createElement('div');const phrase=document.createElement('p');phrase.textContent=item.gist?redactPhrase(item.gist):'Meaning unclear';const meta=document.createElement('small');meta.textContent=new Date(item.time*1000).toLocaleTimeString()+' · similarity '+item.score.toFixed(3);row.append(phrase,meta);return row}));}
 renderLearningCurve(r?.learning_curve);
 $('typingUpdateTest').disabled=!!d.fitting;
 $('typingUpdateTest').textContent=d.fitting?'Updating test…':'Update test';
 $('typingTestStatus').textContent=(r?.evaluated_at?'Last updated '+new Date(r.evaluated_at*1000).toLocaleTimeString()+'. ':'')+'Automatically checks every 5 minutes when enough new data are available. Repeated tests are exploratory; accuracy may rise or fall.';
 const score=r?.four_choice;
 $('typingProgress').textContent=`${d.lifetime_words??d.total} words recorded · ${d.semantic_phrases||0} phrases indexed for cumulative training · ${d.session_count??0} sessions · ${(d.recording_minutes||0).toFixed(1)} minutes recording${d.fitting?' · Updating model…':''}`;
 $('performanceHeadline').textContent=score?Math.round(score.eeg*100)+'% correct on the phrase test':'First test pending';
 $('performanceSummary').textContent=score?`${score.correct} of ${score.n} held-out block phrases selected correctly. ${score.eeg>Math.max(score.typical,score.text_history,score.signal_quality)?'EEG led the simple comparisons on this test.':'EEG has not beaten the strongest simple comparison.'} Results are preliminary.`:'Keep writing freely. All eligible archived sessions contribute to local training; a separate model is tested on randomly held-out time blocks with gaps to prevent overlapping EEG.';
 if(score?.chance_range)$('performanceSummary').textContent+=` Shading shows the 95% random-guessing range: ${Math.round(score.chance_range.low*100)}–${Math.round(score.chance_range.high*100)}%. Highlighting is exploratory; overlapping EEG and repeated checks limit statistical conclusions.`;
 const comparisons=score?[['Random guessing',.25],['Your EEG',score.eeg],['Typical meaning (no EEG)',score.typical],['Previous writing (no EEG)',score.text_history],['Signal quality alone',score.signal_quality]]:[];
 $('performanceBars').replaceChildren(...comparisons.map(([label,value])=>{const row=document.createElement('div');row.className='performance-row'+(label==='Random guessing'?' random-baseline':'');const name=document.createElement('span');name.textContent=label;const bar=document.createElement('progress');bar.max=1;bar.value=value;bar.setAttribute('aria-label',label+': '+Math.round(value*100)+' percent correct');const n=document.createElement('strong');n.textContent=Math.round(value*100)+'%';const track=document.createElement('div');track.className='performance-track';track.append(bar);if(score.chance_range){const band=document.createElement('span');band.className='chance-band';band.style.left=(score.chance_range.low*100)+'%';band.style.width=((score.chance_range.high-score.chance_range.low)*100)+'%';band.title='95% range expected from independent random guesses';track.append(band);if(label!=='Random guessing'){const above=Math.round(value*score.n)>=score.chance_range.minimum_above;row.classList.add(above?'above-chance':'within-chance')}}else if(label!=='Random guessing'){row.classList.add('within-chance')}row.append(name,track,n);return row}));
 $('typingStorage').textContent=d.session?`Saved in data/typing/${d.session.id} · continuous EEG, text, edit events and word epochs`:'Ready for a new recording.';
 if(running){$('source').disabled=true;$('start').disabled=true;$('developerStart').disabled=true;$('developerFree').disabled=true}
 if(!running&&typingWasRunning)api('system_typing/stop',{}).catch(()=>{});typingWasRunning=running;

}
$('typingNav').onclick=()=>selectTypingView(true);
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{if(typingView)selectTypingView(false)}));
async function checkTypingAccess(){
 if(!window.museNative){typingAccessState={available:false,reason:'Across-app capture requires the Bandstand desktop app.'};}
 else try{typingAccessState=await api('system_typing/status',{});}catch(e){typingAccessState={available:false,reason:'Could not check typing access: '+e.message+'. Quit and reopen Bandstand, then try again.'};}
 const p=typingAccessState;
 $('typingAccess').hidden=!!p.available;
 $('typingAccess').textContent=p.available?'':(window.museNative?'Typing access needed. Enable '+(!p.accessibility?'Accessibility':'Input Monitoring')+' in macOS Settings, then return to Bandstand.':p.reason);
 $('typingCheckAccess').hidden=!window.museNative||!!p.available;
 $('typingCheckAccess').textContent=p.accessibility?'Open Input Monitoring':'Open Accessibility';
 updateTypingMode();

}
async function enableTypingAccess(){if(!window.museNative||typingAccessState?.available)return checkTypingAccess();try{await api('system_typing/request_access',{});await checkTypingAccess()}catch(e){toast(e.message)}}
$('typingCheckAccess').onclick=enableTypingAccess;
window.addEventListener('focus',()=>checkTypingAccess());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkTypingAccess()});
async function startWriting(capture=$('typingCapture').value){
 if(typingStarting||state?.typing?.running)return;
 // Writing records live EEG only; say so before the instruction gate and participant forms, not after.
 if((state?.source!=='live'&&!(typeof boot!=='undefined'&&boot?.capabilities?.windows_preview))||state?.stale)return toast('Writing needs the live headset. Demo EEG cannot be used for writing; connect your Muse first.');
 chooseTypingMode(capture);typingStarting=true;updateTypingMode();
 let started=false;
 const feedback=$('typingStartFeedback');if(feedback)feedback.textContent='Checking recording readiness…';
 try{
  if(active||state?.developer?.recording||personalBusy)throw new Error('Stop the current activity before starting a writing recording.');
  if(capture==='system'){await checkTypingAccess();if(!typingAccessState?.available)throw new Error(typingAccessState?.reason||'Enable typing access first.');}
  await syncClock();
  state.typing=await api('typing/start',{window:'context',history:Number($('typingHistory').value),delay:Number($('typingDelay').value),capture});started=true;if(typeof journeySetStep==='function'){journeyRun=true;journeySetStep('run')};
  typingWord=null;typingPlotRevision=-1;clearTimeout(typingDocTimer);
  if(capture==='system'){
   const result=await api('system_typing/start',{});if(!result.active)throw new Error(result.reason||'Typing capture could not start.');
  }else{
   const el=$('writingEditor');el.value='';el.readOnly=false;el.hidden=false;el.focus();el.setSelectionRange(0,0);
   await typingEvent({kind:'document',onset:now(),text:''});
  }
  if(feedback)feedback.textContent=capture==='system'?'Recording EEG and typing across apps.':'Recording EEG and writing below. Text saves automatically.';
 }catch(e){
  if(started){if(capture==='system')await api('system_typing/stop',{}).catch(()=>{});state.typing=await api('typing/stop',{reason:'Capture could not start'});}
  if(feedback)feedback.textContent=e.message;toast(e.message);
  if(/headset|EEG/i.test(e.message)){$('headsetSetup').open=true;$('headsetSetup').scrollIntoView({behavior:'smooth'});}
 }finally{typingStarting=false;renderTyping();}
}
$('typingStart').hidden=true;
$('typingStart').onclick=()=>startWriting();
$('typingStop').onclick=()=>stopTyping().catch(e=>toast(e.message));
$('writingEditor').addEventListener('beforeinput',e=>{
 if(!state?.typing?.running||state.typing.session?.capture==='system')return;const el=e.target,onset=now(),atEnd=el.selectionStart===el.value.length&&el.selectionEnd===el.value.length;
 const direct=e.inputType==='insertText'&&!e.isComposing&&e.data&&e.data.length===1;
 if(!typingWord&&direct&&!/\s/u.test(e.data)&&atEnd&&(!el.value.length||/\s/u.test(el.value.at(-1)))){
  typingWord={id:globalThis.crypto?.randomUUID?crypto.randomUUID():'word-'+Date.now().toString(36)+'-'+(++typingMarkerSequence),start:el.value.length,text:'',edited:false,unsupported:false};typingEvent({kind:'onset',id:typingWord.id,onset});
 }
 if(typingWord){if(e.inputType.startsWith('delete'))typingWord.edited=true;if(!atEnd||(!direct&&!['deleteContentBackward','insertLineBreak','insertParagraph'].includes(e.inputType)))typingWord.unsupported=true}
 typingEvent({kind:'edit',onset,input_type:e.inputType,data:e.data,selection:[el.selectionStart,el.selectionEnd],composing:e.isComposing});
});
$('writingEditor').addEventListener('input',e=>{
 if(!state?.typing?.running||state.typing.session?.capture==='system')return;
 if(typingWord){const suffix=e.target.value.slice(typingWord.start);typingWord.text=suffix.split(/\s/u)[0];if(!suffix.length)closeTypingWord(true);else if(/\s/u.test(suffix))closeTypingWord();}
 clearTimeout(typingDocTimer);typingDocTimer=setTimeout(()=>typingEvent({kind:'document',onset:now(),text:$('writingEditor').value}),500);
});
window.addEventListener('beforeunload',e=>{if(state?.typing?.running){e.preventDefault();e.returnValue=''}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&state?.typing?.running&&state.typing.session?.capture!=='system')stopTyping('Editor hidden').catch(e=>toast(e.message))});
selectTypingView(true);

$('typingExport').onclick=async()=>{try{const r=await api('typing/export',{});toast(r.message)}catch(e){toast(e.message)}};



// New editor sessions start blank; historical documents stay in their recording folders.

checkTypingAccess();

$('typingRestart').onclick=async()=>{try{if(state?.typing?.running)await stopTyping('New recording requested');$('writingParadigm').open=true;$('writingParadigm').scrollIntoView({behavior:'smooth'});await $('typingStart').onclick()}catch(e){toast(e.message)}};

for(const [id,value] of [['inferenceBest','best'],['inferenceAll','all']])$(id).onclick=()=>{inferenceFeed.setMode(value);$('inferenceBest').setAttribute('aria-selected',String(value==='best'));$('inferenceAll').setAttribute('aria-selected',String(value==='all'));renderTyping()};

function renderLearningCurve(curve){
 const canvas=$('learningCurve');if(!canvas)return;
 const points=curve?.points||[],w=Math.max(300,canvas.clientWidth||500),h=250,dpr=window.devicePixelRatio||1;
 canvas.width=w*dpr;canvas.height=h*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);
 const left=48,right=w-18,top=18,bottom=205,max=Math.max(1,...points.map(p=>p.training_phrases));
 const x=n=>left+n/max*(right-left),y=v=>bottom-v*(bottom-top);
 c.font='12px sans-serif';c.textAlign='right';
 for(const value of [0,.25,.5,.75,1]){c.strokeStyle='#e1e6df';c.beginPath();c.moveTo(left,y(value));c.lineTo(right,y(value));c.stroke();c.fillStyle='#708074';c.fillText(Math.round(value*100)+'%',left-8,y(value)+4)}
 if(curve?.chance_range){c.fillStyle='rgba(177,122,40,.14)';c.fillRect(left,y(curve.chance_range.high),right-left,y(curve.chance_range.low)-y(curve.chance_range.high))}
 c.strokeStyle='#b17a28';c.setLineDash([5,4]);c.beginPath();c.moveTo(left,y(.25));c.lineTo(right,y(.25));c.stroke();c.setLineDash([]);
 c.strokeStyle='#87918d';c.beginPath();points.forEach((p,i)=>{if(i)c.lineTo(x(p.training_phrases),y(p.accuracy));else c.moveTo(x(p.training_phrases),y(p.accuracy))});c.stroke();
 c.textAlign='center';for(const p of points){c.fillStyle=curve.chance_range&&p.correct>=curve.chance_range.minimum_above?'#278252':'#92999b';c.beginPath();c.arc(x(p.training_phrases),y(p.accuracy),5,0,Math.PI*2);c.fill();c.fillStyle='#526458';c.fillText(String(p.training_phrases),Math.min(right-8,x(p.training_phrases)),bottom+18);c.fillText(Math.round(p.accuracy*100)+'%',Math.min(right-10,x(p.training_phrases)),y(p.accuracy)-10)}
 c.fillText('Training phrases',w/2,h-8);
 $('learningCurveNote').textContent=points.length?'Same '+points[0].n+' held-out phrases at every point. Gold: random guessing and its 95% range. Chronological training subsets from the archive; same held-out test at every point, not historical scores.':'Waiting for the next model evaluation. The curve will use increasing training subsets and one fixed test set.';
}

$('typingUpdateTest').onclick=async()=>{try{$('typingUpdateTest').disabled=true;state.typing=await api('typing/update_test',{});renderTyping()}catch(e){toast(e.message)}finally{if(!state?.typing?.fitting)$('typingUpdateTest').disabled=false}};
