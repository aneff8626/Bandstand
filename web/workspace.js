/* One headset component shared by every workspace. Display choices do not change analysis. */
const hiddenTraceChannels=new Set();
let displayFilterKey='',displayFilterTime=-Infinity,displayFilterState=[],displayFilterCache=new Map();
function displayTrace(trace){
 if(!trace?.times?.length||!$('displayBandpass')?.checked)return trace;
 const low=Number($('displayLow').value),high=Number($('displayHigh').value),key=`${low}/${high}`;
 if(!(low>=.1&&high>low&&high<=30))return trace;
 if(key!==displayFilterKey||trace.times.at(-1)<displayFilterTime){displayFilterKey=key;displayFilterTime=-Infinity;displayFilterState=[];displayFilterCache.clear()}
 // First-order causal high/low pass, applied to the existing 0.1–30 Hz notched trace.
 const values=trace.times.map((t,i)=>{if(t>displayFilterTime){const dt=Number.isFinite(displayFilterTime)?Math.min(.1,t-displayFilterTime):1/128;const hp=1/(1+2*Math.PI*low*dt),lp=1-Math.exp(-2*Math.PI*high*dt);const out=trace.values[i].map((x,ch)=>{if(!Number.isFinite(x)){displayFilterState[ch]=null;return null}const q=displayFilterState[ch]||{x,h:0,l:0};q.h=hp*(q.h+x-q.x);q.x=x;q.l+=lp*(q.h-q.l);displayFilterState[ch]=q;return q.l});displayFilterCache.set(t,out);displayFilterTime=t}return displayFilterCache.get(t)||trace.values[i]});
 for(const t of displayFilterCache.keys())if(t<trace.times[0])displayFilterCache.delete(t);
 return {...trace,values};
}
function workspaceSection(id,title,before){const d=document.createElement('details');d.id=id;d.className='panel workspace-section';d.open=true;const summary=document.createElement('summary');summary.textContent=title;d.append(summary);before.before(d);return d}
function initWorkspace(){
 document.querySelector('.steps').remove();$('pageSubtitle').hidden=true;
 const connection=document.querySelector('.connection');const headset=workspaceSection('headsetSetup','1 · Headset setup',connection);headset.append(connection,$('signalPanel'));
 const writing=$('writingSetup');const paradigm=workspaceSection('writingParadigm','2 · Paradigm setup',writing);
 paradigm.append($('typingRequirements'),$('writingEditor'),$('typingCapture'),writing.querySelector('.writing-controls'),$('typingAccess'),$('typingCheckAccess'),$('typingRestart'));
 for(const id of ['typingRestart','typingExport','typingCheckAccess','typingAccess','typingRequirements'])$(id).hidden=true;
 const results=workspaceSection('writingResults','3 · Results',$('writingAnalysis'));results.append($('typingStatus'),$('typingCounts'),$('writingAnalysis'));
 $('writingAnalysis').querySelector('.panel-heading').remove();writing.remove();
 // Keep model assumptions as its existing, independent disclosure.
 const context=$('writingAnalysis').querySelector(':scope > details');results.after(context);
 const design=workspaceSection('experimentParadigm','2 · Paradigm setup',$('designSection'));design.append($('designSection'));
 const erpResults=workspaceSection('experimentResults','3 · Results',$('recordSection'));erpResults.append($('recordSection'));$('recordSection').classList.remove('hidden');
 erpResults.append(document.querySelector('.export-actions'));
 $('designSection').querySelector('.section-heading').hidden=true;
 const resultLabelNode=document.createElement('label');resultLabelNode.textContent='Experiment';const resultMenu=document.createElement('select');resultMenu.id='resultExperiment';resultLabelNode.append(resultMenu);erpResults.querySelector('summary').after(resultLabelNode);
 resultMenu.onchange=async()=>{++reviewRequest;clearTimeout(reviewTimer);try{selectedResult=resultMenu.value?await api('results/'+resultMenu.value):null;renderRevision='';updateResultExports();render()}catch(e){toast(e.message)}};
 erpResults.addEventListener('toggle',()=>{if(erpResults.open)refreshResultSessions().then(()=>{renderRevision='';if(state)render()}).catch(e=>toast(e.message))});
 refreshResultSessions().catch(e=>toast(e.message));

 const guide=document.createElement('details');guide.innerHTML='<summary>Recommended first ERP: visual oddball P300</summary><p>Silently count rare blue circles among frequent green circles. Select Visual oddball: pool TP9 and TP10, referenced to Fpz; compare target and standard mean amplitude at 300–500 ms. Start with 120 trials (about 3 minutes), or choose 240 for more usable targets. Blink during the breaks every 40 trials.</p><p>Muse validation supports this montage. Single-person detection remains uncertain; this is a Muse 2 adaptation with uncalibrated physical onset timing. Reward positivity is a supported second option. N400, ERN and phonetic decoding are less suitable as the first validation task for this setup.</p><a href="https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2017.00109/full" target="_blank" rel="noreferrer">Krigolson et al. · Muse ERP validation</a>';design.append(guide);

 $('recordSection').querySelector('h2').textContent='Recorded response';$('sessionSummary').textContent='No experiment recorded yet.';
 $('start').textContent='Review & start recording';
 const heading=$('signalPanel').querySelector('.panel-heading');heading.querySelector('p').textContent='Click an electrode name below to hide or restore its trace.';
 const controls=document.createElement('div');controls.className='display-filter-controls';controls.innerHTML='<span class="pill">60 Hz notch · 0.1–30 Hz</span><label><input id="displayBandpass" type="checkbox"> Additional display bandpass</label><label>Low (Hz)<input id="displayLow" type="number" min="0.1" max="29.9" step="0.1" value="1"></label><label>High (Hz)<input id="displayHigh" type="number" min="0.2" max="30" step="0.1" value="30"></label><span id="displayFilterNote" class="muted">Display only; recorded data and analysis filters are unchanged.</span>';
 heading.querySelector('.pill').remove();
 const filters=document.createElement('details');filters.className='signal-disclosure filter-disclosure';const filterSummary=document.createElement('summary');filterSummary.textContent='Filters';filters.append(filterSummary,controls);heading.querySelector('.inline').append(filters);
 const helpRow=document.createElement('div');helpRow.className='signal-help-row';heading.after(helpRow);
 function help(title,nodes){const d=document.createElement('details');d.className='signal-disclosure';const summary=document.createElement('summary');summary.textContent=title;const body=document.createElement('div');body.className='signal-help-body';body.append(...nodes);d.append(summary,body);helpRow.append(d);return d}
 help('Electrode contact',[$('signalPanel').querySelector('.contact-summary'),heading.querySelector('p')]);
 const supplementary=[...$('signalPanel').querySelectorAll(':scope > p:not(.artifact-key)')];const signalHelp=help('Signal details',[...supplementary,$('signalPanel').querySelector('.chart-footer')]);
 helpRow.append(filters);heading.hidden=true;$('traceMode').value='all';
 const scale=document.createElement('label');scale.textContent='Amplitude per half row';const select=document.createElement('select');select.id='displayScale';for(const n of [25,50,75,100,200,500]){const o=document.createElement('option');o.value=n;o.textContent=n+' µV';o.selected=n===75;select.append(o)}scale.append(select);signalHelp.lastChild.prepend(scale);
 const scaleLabel=document.createElement('p');scaleLabel.id='traceScaleLabel';scaleLabel.className='muted';scaleLabel.textContent='±75 µV per channel';$('trace').after(scaleLabel);scaleLabel.after(helpRow);select.onchange=()=>scaleLabel.textContent='±'+select.value+' µV per channel';
 const privacy=document.createElement('details');privacy.innerHTML='<summary>Display privacy</summary><p>Names are masked in displayed predictions and history using conservative local rules. Names can be missed, and other capitalized words may be masked. Original recordings are retained. Add names below for case-insensitive masking (one per line).</p><textarea id="redactNames" rows="3" aria-label="Additional names to redact" placeholder="One name per line"></textarea>';
 context.append(privacy);try{$('redactNames').value=JSON.parse(localStorage.getItem('decoderRedactNames')||'[]').join('\n')}catch{};$('redactNames').oninput=()=>{try{localStorage.setItem('decoderRedactNames',JSON.stringify($('redactNames').value.split('\n')))}catch{};if(state)renderTyping()};


 for(const id of ['displayLow','displayHigh','displayBandpass'])$(id).onchange=()=>{const valid=+$('displayLow').value>=.1&&+$('displayHigh').value<=30&&+$('displayLow').value<+$('displayHigh').value;$('displayFilterNote').textContent=valid?'Display only; recorded data and analysis filters are unchanged.':'Enter 0.1 ≤ low < high ≤ 30 Hz.';if(!valid)$('displayBandpass').checked=false;displayFilterKey='';displayFilterTime=-Infinity;displayFilterCache.clear();displayFilterState=[]};
 $('contactReadout').setAttribute('aria-label','Electrode contact and trace visibility');
 $('typingRestart').onclick=async()=>{try{if(state?.typing?.running)await stopTyping('New recording requested');paradigm.open=true;paradigm.scrollIntoView({behavior:'smooth'});await $('typingStart').onclick()}catch(e){toast(e.message)}};
 erpResults.addEventListener('toggle',()=>{renderRevision='';if(state)render()});
}
let selectedResult=null;
function updateResultExports(){for(const a of document.querySelectorAll('#experimentResults .export-actions a')){const kind=a.dataset.exportKind||(a.dataset.exportKind=a.getAttribute('href').split('/')[3]);a.href='/api/export/'+kind+(selectedResult?'/'+selectedResult.session.id:'')}}
async function refreshResultSessions(){
 const select=$('resultExperiment');if(!select)return;
 const sessions=await api('sessions');const prior=select.value;select.replaceChildren();const current=document.createElement('option');current.value='';current.textContent=state?.session?resultLabel(state.session):'Select an experiment';select.append(current);
 for(const s of sessions){if(s.id===state?.session?.id)continue;const o=document.createElement('option');o.value=s.id;o.textContent=resultLabel(s);select.append(o)}select.value=prior; if(select.selectedIndex<0)select.value='';
 if(!state?.session&&!selectedResult&&sessions.length){select.value=sessions[0].id;selectedResult=await api('results/'+sessions[0].id);renderRevision='';updateResultExports();}
}
function resultLabel(s){return (s.title||s.protocol||'Experiment')+' · '+new Date(s.started*1000).toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'})}
const axisLimits=new Map();
function setupAxisDrag(id,low,high,box){
 const el=$(id),key=(selectedResult?.session?.id||state?.session?.id||'')+'/'+id,limits=axisLimits.get(key)||[low,high];
 el.title='Drag either end of the left axis to scale; double-click to reset. Drag across the ERP to select a comparison window.';
 const position=e=>{const r=el.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]},axisHit=(x,y)=>x<=48&&Math.min(Math.abs(y-box.t),Math.abs(y-box.b))<=28;
 el.onpointermove=e=>{const [x,y]=position(e);el.style.cursor=axisHit(x,y)?'grab':el._timeDomain&&x>=box.l&&x<=box.r&&y>=box.t&&y<=box.b?'crosshair':'default'};
 el.onpointerdown=e=>{const [x,y]=position(e),axis=axisHit(x,y),domain=el._timeDomain;
 if(!axis&&(!domain||x<box.l||x>box.r||y<box.t||y>box.b||active))return;
 e.preventDefault();const rect=el.getBoundingClientRect(),upper=Math.abs(y-box.t)<Math.abs(y-box.b),initial=[...limits],startY=e.clientY;
 const ms=px=>Math.max(0,Math.min(800,Math.round((domain[0]+(px-box.l)/(box.r-box.l)*(domain[1]-domain[0]))*1000)));
 const anchor=axis?0:ms(x);let lastUpdate=0;
 document.body.style.cursor=axis?'grabbing':'crosshair';
 const move=event=>{if(axis){const delta=(startY-event.clientY)*(initial[1]-initial[0])/(box.b-box.t);axisLimits.set(key,upper?[initial[0],Math.max(initial[0]+.1,initial[1]+delta)]:[Math.min(initial[1]-.1,initial[0]+delta),initial[1]]);el._redraw?.()}else{const end=ms(event.clientX-rect.left),lo=Math.min(anchor,end),hi=Math.max(anchor,end);if(hi-lo<8)return;$('reviewStart').value=lo;$('reviewEnd').value=hi;previewReviewWindow=[lo/1000,hi/1000];document.querySelectorAll('#channelERPs canvas').forEach(c=>c._redraw?.());if(performance.now()-lastUpdate>120){lastUpdate=performance.now();updateReviewWindow()}}};
 const finish=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',finish);document.body.style.cursor='';if(!axis){updateReviewWindow();previewReviewWindow=null}};
 window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);
 };
 el.ondblclick=()=>{axisLimits.delete(key);el._redraw?.()};return limits;
}
let previewReviewWindow=null;
let reviewRequest=0,reviewTimer;
function syncReviewWindow(){
 let controls=$('reviewWindow');if(!controls){controls=document.createElement('div');controls.id='reviewWindow';controls.className='review-window';controls.innerHTML='<label>Comparison window (ms)<span class="input-pair"><input id="reviewStart" type="number" min="0" max="799" step="10" aria-label="Comparison window start"><input id="reviewEnd" type="number" min="1" max="800" step="10" aria-label="Comparison window end"></span></label><button id="reviewReset">Reset to recorded window</button><p id="reviewStatus" class="muted"></p><p class="muted">Enter a range or drag across an ERP plot to update comparisons automatically. Drag the top or bottom of the left axis to scale; double-click to reset. Window exploration is post hoc; p-values are uncorrected. Exports retain the recorded analysis window.</p>';$('resultExperiment').closest('label').after(controls);
 for(const id of ['reviewStart','reviewEnd'])$(id).oninput=()=>{clearTimeout(reviewTimer);reviewTimer=setTimeout(updateReviewWindow,180)};
 $('reviewReset').onclick=()=>{const s=selectedResult?.session||state.session,w=s.original_window||s.window;$('reviewStart').value=Math.round(w[0]*1000);$('reviewEnd').value=Math.round(w[1]*1000);updateReviewWindow()};}
 controls.hidden=state.session?.mode!=='erp';if(controls.hidden)return;
 for(const [i,id]of ['reviewStart','reviewEnd'].entries())if(!previewReviewWindow&&document.activeElement!==$(id))$(id).value=Math.round(state.session.window[i]*1000);
 $('reviewStatus').textContent=state.session.review_window?'Exploratory window · statistics recalculated for each electrode.':'Recorded default window · '+state.session.window.map(v=>Math.round(v*1000)).join('–')+' ms';
}
async function updateReviewWindow(){
 const request=++reviewRequest,s=selectedResult?.session||state.session,start=Number($('reviewStart').value),end=Number($('reviewEnd').value);
 if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end>800||start>=end){$('reviewStatus').textContent='Enter 0 ≤ start < end ≤ 800 ms.';return}
 try{const r=await api('results/'+s.id+'/'+start/1000+'/'+end/1000);if(request!==reviewRequest)return;selectedResult=r;renderRevision='';render()}catch(e){if(request===reviewRequest)$('reviewStatus').textContent=e.message}
}
