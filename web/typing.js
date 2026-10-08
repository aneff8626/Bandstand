const inferenceFeed=createInferenceFeed();
let typingWasRunning=false;
/* Free-writing acquisition. Text is sent as labels; it is never a decoder input. */
let typingAccessState=null,typingMarkerSequence=0,typingStopping=false,typingView=false,typingWord=null,typingChain=Promise.resolve(),typingDocTimer=null,typingPlotRevision=-1;
function typingEvent(body){typingChain=typingChain.then(()=>api('typing/event',body)).catch(e=>{toast(e.message);$('typingStatus').textContent='Recording issue: '+e.message});return typingChain}
function selectTypingView(on){
 if(active)return toast('Finish the experiment before changing workspace.');
 if(state?.typing?.running&&!on)return toast('Stop the typing recording before changing workspace.');
 typingView=on;if(on)document.querySelectorAll('[data-mode]').forEach(b=>b.classList.remove('active'));document.body.classList.toggle('typing-view',on);show('typingWorkspace',on);$('typingNav').classList.toggle('active',on);
 if(on){$('modeCrumb').textContent='WRITING DECODER';$('pageTitle').textContent='Writing decoder';$('pageSubtitle').textContent='';show('developerPanel',false)}else setMode(mode);
}
function closeTypingWord(cancel=false){
 if(!typingWord)return Promise.resolve();const w=typingWord;typingWord=null;
 return typingEvent({kind:cancel?'cancel':'commit',id:w.id,text:w.text,onset:now(),edited:w.edited,unsupported:w.unsupported});
}
async function stopTyping(reason='Stopped by writer'){
 if(typingStopping)return;typingStopping=true;try{
 clearTimeout(typingDocTimer);await closeTypingWord();await typingEvent({kind:'document',onset:now(),text:$('writingEditor').value});await typingChain;
 if(state.typing?.session?.capture==='system')await api('system_typing/stop',{}).catch(()=>{});state.typing=await api('typing/stop',{reason});renderTyping();}finally{typingStopping=false}
}
function renderTyping(){
 const d=state?.typing;if(!d)return;const running=d.running;if(running&&state.stale){stopTyping('EEG signal lost').catch(e=>toast(e.message));return}
 $('typingExport').disabled=running||!d.session;
 $('typingRestart').textContent=running?'Save session & continue':'Continue recording';
 $('typingRequirements').textContent=typingAccessState?.available?'Typing access available.':'Enable typing access to record across apps.';
 $('typingStart').disabled=running||active||!!state.developer?.recording||state.stale||state.source!=='live';show('typingStop',true);$('typingStop').disabled=!running;$('typingWindow').disabled=running;
 $('typingStatus').textContent=running?'Recording locally · space or Enter completes a word':d.session?(d.session.stop_reason||'Recording saved locally'):'Ready when you are';
 $('writingEditor').readOnly=!running||d.session?.capture==='system';
 for(const id of ['typingHistory','typingDelay','typingCapture'])$(id).disabled=running;
 if(running&&d.session?.capture==='system')$('typingStatus').textContent=d.capture_status?.reason||'Recording EEG · type in another app';
 $('typingCounts').textContent=`${d.accepted} usable · ${d.rejected} excluded · ${d.pending} pending`;
 $('typingPrediction').textContent=(d.prediction?.word?redactPhrase(d.prediction.word):null)||(d.decoder?.ready?'No confident estimate':'Collecting evidence');
 $('typingPredictionNote').textContent=d.prediction?.reason||d.decoder?.reason||'No EEG prediction yet.';
 const r=d.decoder;$('typingEvidence').textContent=r?.accuracy!==undefined?`Later-block accuracy ${(r.accuracy*100).toFixed(1)}% · balanced ${(r.balanced_accuracy*100).toFixed(1)}% · chance ${(r.chance*100).toFixed(1)}% · majority ${(r.majority_accuracy*100).toFixed(1)}% · ${r.validation_trials} validation words. ${r.reason}`:r?.reason||'';
 if(r?.kind==='semantic')$('typingEvidence').textContent=r.cosine!==undefined?`${r.training_phrases} training phrases · ${r.validation_trials} later phrases · EEG cosine ${r.cosine.toFixed(3)} · text-history baseline ${r.text_history_baseline.toFixed(3)} · quality baseline ${r.mask_baseline.toFixed(3)} · gain over strongest baseline ${r.gain.toFixed(3)}. ${r.reason}`:r.reason;
 const feed=inferenceFeed.update(d.prediction,performance.now());
 if(feed.current){$('typingPrediction').textContent='“'+redactPhrase(feed.current.text)+'”';$('typingPredictionNote').textContent=(feed.current.validated?'Exploratory':'Ultra-tentative · unvalidated')+' · similarity '+feed.current.score.toFixed(3)+' · '+(running?'Receiving live EEG matches':'Recording stopped; last match shown')+'. Similarity is not probability.';}
 $('semanticCandidates').textContent=feed.mode==='best'?'Stronger or repeated matches, held for reading time plus up to 5 seconds.':'All received matches in history; the headline stays long enough to read.';
 const historyKey=feed.mode+JSON.stringify(feed.previous.map(x=>[redactPhrase(x.text),x.time]));
 if($('inferenceHistory').dataset.key!==historyKey){$('inferenceHistory').dataset.key=historyKey;$('inferenceHistory').replaceChildren(...feed.previous.map(item=>{const row=document.createElement('div');const phrase=document.createElement('p');phrase.textContent=redactPhrase(item.text);const meta=document.createElement('small');meta.textContent=new Date(item.time*1000).toLocaleTimeString()+' · similarity '+item.score.toFixed(3);row.append(phrase,meta);return row}));}
 const score=r?.four_choice;
 $('typingProgress').textContent=`${d.lifetime_words??d.total} words recorded · ${d.semantic_phrases||0} phrases in the recent training window · ${d.session_count??0} sessions · ${(d.recording_minutes||0).toFixed(1)} minutes recording${d.fitting?' · Updating model…':''}`;
 $('performanceHeadline').textContent=score?Math.round(score.eeg*100)+'% correct on the phrase test':'First test pending';
 $('performanceSummary').textContent=score?`${score.correct} of ${score.n} later phrases selected correctly. ${score.eeg>Math.max(score.typical,score.text_history,score.signal_quality)?'EEG led the simple comparisons on this test.':'EEG has not beaten the strongest simple comparison.'} Results are preliminary.`:'Keep writing freely. Tentative matches can appear before there is enough separate data to test them.';
 if(score?.chance_range)$('performanceSummary').textContent+=` Shading shows the 95% chance range: ${Math.round(score.chance_range.low*100)}–${Math.round(score.chance_range.high*100)}%. Highlighting is exploratory; overlapping EEG and repeated checks limit statistical conclusions.`;
 const comparisons=score?[['Random guessing',.25],['Your EEG',score.eeg],['Typical meaning (no EEG)',score.typical],['Previous writing (no EEG)',score.text_history],['Signal quality alone',score.signal_quality]]:[];
 $('performanceBars').replaceChildren(...comparisons.map(([label,value])=>{const row=document.createElement('div');row.className='performance-row'+(label==='Random guessing'?' random-baseline':'');const name=document.createElement('span');name.textContent=label;const bar=document.createElement('progress');bar.max=1;bar.value=value;bar.setAttribute('aria-label',label+': '+Math.round(value*100)+' percent correct');const n=document.createElement('strong');n.textContent=Math.round(value*100)+'%';const track=document.createElement('div');track.className='performance-track';track.append(bar);if(score.chance_range){const band=document.createElement('span');band.className='chance-band';band.style.left=(score.chance_range.low*100)+'%';band.style.width=((score.chance_range.high-score.chance_range.low)*100)+'%';band.title='95% range expected from independent random guesses';track.append(band);if(label==='Your EEG'&&score.correct>=score.chance_range.minimum_above){row.classList.add('above-chance');name.textContent+=' · above chance range'}}row.append(name,track,n);return row}));
 $('typingStorage').textContent=d.session?`Saved in data/typing/${d.session.id} · continuous EEG, text, edit events and word epochs`:'Ready for a new recording.';
 if(running){$('source').disabled=true;$('start').disabled=true;$('developerStart').disabled=true;$('developerFree').disabled=true}
 if(!running&&typingWasRunning)api('system_typing/stop',{}).catch(()=>{});typingWasRunning=running;

}
$('typingNav').onclick=()=>selectTypingView(true);
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{if(typingView)selectTypingView(false)}));
async function checkTypingAccess(){
 if(!window.museNative){typingAccessState={available:false,reason:'Across-app writing capture requires the Bandstand desktop app. Open Muse Lab.app from Applications, then start recording there. The browser preview cannot capture typing in other apps.'};}
 else try{typingAccessState=await api('system_typing/status',{});}catch(e){typingAccessState={available:false,reason:'Could not check typing access: '+e.message+'. Quit and reopen Bandstand, then try again.'};}
 if(window.museNative&&typingAccessState&&typeof typingAccessState.accessibility==='boolean'){const missing=[];if(!typingAccessState.accessibility)missing.push('Accessibility');if(!typingAccessState.inputMonitoring)missing.push('Input Monitoring');typingAccessState.reason=missing.length?'macOS has not authorized this running copy for '+missing.join(' and ')+'. If its switch is already on, remove the old entry and add the Muse Lab app from Applications, then quit and reopen the app.':'Typing access ready.';}
 $('typingAccess').textContent=typingAccessState.reason;
 $('typingAccess').hidden=Boolean(typingAccessState.available);$('typingCheckAccess').hidden=!window.museNative||Boolean(typingAccessState.available);$('typingCheckAccess').textContent='Enable typing access';
}
async function enableTypingAccess(){if(!window.museNative)return checkTypingAccess();try{await api('system_typing/request_access',{});await checkTypingAccess()}catch(e){toast(e.message)}}
$('typingCheckAccess').onclick=enableTypingAccess;
window.addEventListener('focus',()=>checkTypingAccess());
$('typingStart').onclick=async()=>{try{
 const capture=$('typingCapture').value;
 if(capture==='system'){await checkTypingAccess();if(!typingAccessState?.available){$('typingCheckAccess').focus();return toast(typingAccessState?.reason||'Use Enable typing access, then start recording.');}}
 await syncClock();state.typing=await api('typing/start',{window:'context',history:Number($('typingHistory').value),delay:Number($('typingDelay').value),capture});typingWord=null;typingPlotRevision=-1;
 if(capture==='system'){
  const result=await api('system_typing/start',{});if(!result.active){await api('typing/stop',{reason:'Input capture unavailable'});return toast(result.reason||'Typing capture could not start.');}
 }else{const el=$('writingEditor');el.readOnly=false;el.focus();el.setSelectionRange(el.value.length,el.value.length);typingEvent({kind:'document',onset:now(),text:el.value})}
 renderTyping();if(state.typing?.running)$('writingAnalysis').scrollIntoView({behavior:'smooth'});
 }catch(e){toast(e.message)}};
$('typingStop').onclick=()=>stopTyping().catch(e=>toast(e.message));
$('writingEditor').addEventListener('beforeinput',e=>{
 if(!state?.typing?.running)return;const el=e.target,onset=now(),atEnd=el.selectionStart===el.value.length&&el.selectionEnd===el.value.length;
 const direct=e.inputType==='insertText'&&!e.isComposing&&e.data&&e.data.length===1;
 if(!typingWord&&direct&&!/\s/u.test(e.data)&&atEnd&&(!el.value.length||/\s/u.test(el.value.at(-1)))){
  typingWord={id:globalThis.crypto?.randomUUID?crypto.randomUUID():'word-'+Date.now().toString(36)+'-'+(++typingMarkerSequence),start:el.value.length,text:'',edited:false,unsupported:false};typingEvent({kind:'onset',id:typingWord.id,onset});
 }
 if(typingWord){if(e.inputType.startsWith('delete'))typingWord.edited=true;if(!atEnd||(!direct&&!['deleteContentBackward','insertLineBreak','insertParagraph'].includes(e.inputType)))typingWord.unsupported=true}
 typingEvent({kind:'edit',onset,input_type:e.inputType,data:e.data,selection:[el.selectionStart,el.selectionEnd],composing:e.isComposing});
});
$('writingEditor').addEventListener('input',e=>{
 if(!state?.typing?.running)return;
 if(typingWord){const suffix=e.target.value.slice(typingWord.start);typingWord.text=suffix.split(/\s/u)[0];if(!suffix.length)closeTypingWord(true);else if(/\s/u.test(suffix))closeTypingWord();}
 clearTimeout(typingDocTimer);typingDocTimer=setTimeout(()=>typingEvent({kind:'document',onset:now(),text:$('writingEditor').value}),500);
});
window.addEventListener('beforeunload',e=>{if(state?.typing?.running){e.preventDefault();e.returnValue=''}});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&state?.typing?.running&&state.typing.session?.capture!=='system')stopTyping('Editor hidden').catch(e=>toast(e.message))});
selectTypingView(true);

$('typingExport').onclick=async()=>{try{const r=await api('typing/export',{});toast(r.message)}catch(e){toast(e.message)}};



api('typing/document',{}).then(r=>{if(!$('writingEditor').value&&!state?.typing?.running)$('writingEditor').value=r.text||''}).catch(()=>{});

checkTypingAccess();

$('typingRestart').onclick=async()=>{try{if(state?.typing?.running)await stopTyping('New recording requested');$('writingParadigm').open=true;$('writingParadigm').scrollIntoView({behavior:'smooth'});await $('typingStart').onclick()}catch(e){toast(e.message)}};

for(const [id,value] of [['inferenceBest','best'],['inferenceAll','all']])$(id).onclick=()=>{inferenceFeed.setMode(value);$('inferenceBest').setAttribute('aria-selected',String(value==='best'));$('inferenceAll').setAttribute('aria-selected',String(value==='all'));renderTyping()};
