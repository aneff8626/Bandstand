function matrixPercentile(score){
 if(!Number.isFinite(score))return null;if(score===100)return 50;
 const z=(score-100)/15,sign=z<0?-1:1,x=Math.abs(z)/Math.SQRT2,t=1/(1+.3275911*x);
 const erf=sign*(1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-x*x));
 return Math.max(0,Math.min(100,50*(1+erf)));
}
function matrixPercentileText(p){
 if(p==null)return 'Waiting for answers';if(p<1)return 'Below 1st percentile';if(p>99)return 'Above 99th percentile';
 const n=Math.round(p),suffix=n%100>=11&&n%100<=13?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th');return `${n}${suffix} percentile`;
}
function matrixScorePanel(host,estimate,demo,source){
 host._latest={estimate,demo,source};
 if(!host._matrixInitialized){
  host._matrixInitialized=true;
  const help=headsetHelp('Percentile and uncertainty',[
   personalElement('p','Percentile is the modeled percentage of the reference distribution below your estimated reasoning ability—not percent correct. The reference is the published MaRs-IB US adult online research calibration, using a standard-normal ability model. The bell curve is this model, not an observed histogram of Bandstand users, and not representative or age-adjusted population IQ norms.'),
   personalElement('p','Only the 12 published reference items contribute to the estimate. Three original experimental puzzles are interspersed at random and recorded separately for future calibration. They never raise or lower today’s score. Interspersing pilots and showing live feedback change the original protocol; score comparability still needs validation. Early estimates depend strongly on the prior.'),
   personalElement('p','The blue range is a 95% Bayesian credible interval, transformed into percentiles from the MaRs-IB 3PL posterior. It assumes fixed published item parameters and excludes uncertainty about transferring norms to this app. Saved older sessions are converted to the same percentile scale.'),
   personalElement('p','EEG demo: an arbitrary band-power transformation, with no demonstrated IQ accuracy. Its gold marker is illustrative, not a validated percentile. Responses, item order, timing, versions and EEG are saved locally. Nothing is uploaded by this activity; accumulating records does not automatically train or validate a new model.'),
   personalElement('a','Published validation study')]);
  const link=help._helpDialog.querySelector('a');link.href='https://doi.org/10.3758/s13428-023-02067-8';link.target='_blank';link.rel='noopener';
  const heading=personalElement('h3','Reasoning percentile');heading.append(help);host.append(heading,personalElement('small','Research-reference estimate','matrix-limit'));
  const choices=host._matrixChoices||{test:true,eeg:true};host._matrixChoices=choices;
  const tools=personalElement('div',undefined,'matrix-score-toggles');
  for(const [key,label] of [['test','Test estimate'],['eeg','EEG demo']]){const l=personalElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=choices[key];c.onchange=()=>{choices[key]=c.checked;const v=host._latest;matrixScorePanel(host,v.estimate,v.demo,v.source)};l.append(c,document.createTextNode(label));tools.append(l)}
  host.append(tools);host._warning=personalElement('small','EEG DEMO · synthetic mapping; no demonstrated IQ accuracy','matrix-demo-warning');host.append(host._warning);
  host._chart=personalElement('div',undefined,'matrix-score-chart');host.append(host._chart);
 }
 const choices=host._matrixChoices;host._warning.hidden=!choices.eeg;const chart=host._chart;chart.replaceChildren();
 const p=estimate?.reference_percentile??matrixPercentile(estimate?.score),range=estimate?.percentile_interval??estimate?.interval?.map(matrixPercentile);
 const readouts=personalElement('div',undefined,'matrix-percentile-readouts');chart.append(readouts);
 for(const [key,label,value]of [['test','Test estimate',p],['eeg','EEG demo · illustrative',matrixPercentile(demo?.score)]]){
  if(!choices[key])continue;const block=personalElement('div',undefined,'matrix-percentile-'+key);block.append(personalElement('small',label),personalElement('strong',value==null?(key==='test'?'Answer a puzzle':'Waiting for EEG'):matrixPercentileText(value)));readouts.append(block);
 }
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 440 260');svg.setAttribute('role','img');svg.setAttribute('aria-label',`Modeled research-reference distribution. ${p==null?'No test estimate yet':matrixPercentileText(p)}${range?', 95% credible range '+range.map(v=>v.toFixed(1)).join(' to ')+' percentile':''}. Gold EEG marker is synthetic.`);chart.append(svg);
 const node=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);return n};
 const xx=z=>32+(Math.max(-3,Math.min(3,z))+3)/6*376,yy=z=>170-130*Math.exp(-z*z/2);
 const points=Array.from({length:181},(_,i)=>{const z=-3+i/30;return [z,xx(z),yy(z)]});
 const area=arr=>`M${arr[0][1]},170 `+arr.map(v=>`L${v[1]},${v[2]}`).join(' ')+` L${arr[arr.length-1][1]},170 Z`;
 node('path',{d:area(points),fill:'#e7edf4'});
 if(choices.test&&estimate?.score!=null){const z=(estimate.score-100)/15,selected=points.filter(v=>v[0]<=z);if(selected.length)node('path',{d:area([...selected,[z,xx(z),yy(z)]]),fill:'#8aabc9',opacity:.75})}
 node('path',{d:points.map((v,i)=>`${i?'L':'M'}${v[1]},${v[2]}`).join(' '),fill:'none',stroke:'#9bacbd','stroke-width':1.5});
 for(const z of [-2,-1,0,1,2]){const at=xx(z);node('line',{x1:at,x2:at,y1:170,y2:176,stroke:'#96a8b8'});node('text',{x:at,y:191,'text-anchor':'middle',fill:'#6a7c8c','font-size':11},String(Math.round(matrixPercentile(100+15*z))))}
 node('text',{x:220,y:211,'text-anchor':'middle',fill:'#6a7c8c','font-size':11},'Reference percentile · modeled distribution');
 if(choices.test&&estimate?.interval){const a=xx((estimate.interval[0]-100)/15),b=xx((estimate.interval[1]-100)/15);node('rect',{x:a,y:228,width:Math.max(1,b-a),height:9,rx:4,fill:'#527ca7',opacity:.3});node('text',{x:220,y:254,'text-anchor':'middle',fill:'#6a7c8c','font-size':10},'95% credible range')}
 for(const [key,value,color,dashed]of [['test',estimate?.score,'#416c96',false],['eeg',demo?.score,'#b18b42',true]]){
  if(!choices[key]||value==null)continue;const z=(value-100)/15,x=xx(z);node('line',{x1:x,x2:x,y1:30,y2:170,stroke:color,'stroke-width':2,'stroke-dasharray':dashed?'4 4':'none'});node('circle',{cx:x,cy:yy(z),r:4,fill:color});if(key==='test'&&estimate?.interval)node('circle',{cx:x,cy:232.5,r:5,fill:color});
 }
 if(estimate?.answered)chart.append(personalElement('p',`${estimate.answered} / 12 reference items${estimate.partial?' · provisional':''}${range?' · 95% range: '+range.map(v=>v.toFixed(1)).join('–')+' percentile':''}`,'matrix-score-caption'));
 if(source==='simulation')chart.append(personalElement('small','Simulated EEG','matrix-demo-warning'));
}

async function startMatrixReasoning(resume=null){
 if(!resume&&!personalLeave())return;
 // Decode assets before the server starts the timed items.
 await Promise.all(Object.values(matrixAssets).map(src=>new Promise((resolve,reject)=>{const im=new Image();im.onload=resolve;im.onerror=()=>reject(Error('Could not load the matrix stimuli'));im.src=src})));
 const recording=resume||await api('personal/start',{kind:'matrix'});
 chosenActivityTitle='Matrix reasoning';personalKind='matrix';personalBusy=true;journeyRun=true;activitySetupStep('personalSetup',true);journeySetStep('run');document.body.classList.add('questionnaire-recording');
 const host=$('personalSetupBody');host.replaceChildren();const layout=personalElement('div',undefined,'questionnaire-run-layout'),task=personalElement('section',undefined,'questionnaire-task matrix-task'),viewer=personalElement('section',undefined,'questionnaire-viewer');layout.append(task,viewer);host.append(layout);
 const toggle=personalButton('Hide live estimates',()=>{viewer.hidden=!viewer.hidden;layout.classList.toggle('viewer-hidden',viewer.hidden);toggle.textContent=viewer.hidden?'Show live estimates':'Hide live estimates'});host.prepend(toggle);
 const scores=personalElement('section'),eegDetails=personalElement('details',undefined,'matrix-eeg');eegDetails.append(personalElement('summary','EEG'));const spectralHost=personalElement('section');eegDetails.append(spectralHost);const spectral=createRecordedSpectrum(spectralHost,'matrix');viewer.append(scores,eegDetails);
 const status=personalElement('p',undefined,'questionnaire-status');viewer.prepend(status);const progress=personalElement('progress'),label=personalElement('h3'),timer=personalElement('span',undefined,'matrix-countdown'),image=document.createElement('img'),choices=personalElement('div',undefined,'matrix-choices'),feedback=personalElement('p',undefined,'matrix-feedback'),controls=personalElement('div',undefined,'button-row');image.className='matrix-stem';image.alt='Complete the missing lower-right pattern in this matrix';task.append(label,progress,timer,image,choices,feedback,controls);
 let item=null,deadline=0,ended=false,busy=false,ticker=null,poller=null,last=recording,polling=false;
 const cleanup=()=>{ended=true;clearInterval(ticker);clearInterval(poller);personalBusy=false;journeyRun=false;document.body.classList.remove('questionnaire-recording');$('headsetSetup').open=false;document.removeEventListener('visibilitychange',hidden);document.removeEventListener('keydown',escape)};
 const showResult=r=>{cleanup();renderPersonalResult(r);journeyFreshResult=true;journeySetStep('summary')};
 const stop=async()=>{if(ended||busy)return;busy=true;try{const result=await api('personal/stop',{});const r=result.history?.find(r=>r.id===recording.id);if(r)showResult(r);else{cleanup();personalHome('insights')}}catch(e){busy=false;toast(e.message)}};
 const escape=e=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]'))void stop()};document.addEventListener('keydown',escape);const hidden=()=>{if(document.hidden)void stop()};document.addEventListener('visibilitychange',hidden);controls.append(personalButton('Stop & save partial',stop));
 const update=r=>{last=r;matrixScorePanel(scores,r.matrix_result,r.matrix_eeg_demo,r.source);spectral.update(r.summary?.spectra);status.textContent=`● ${r.source==='simulation'?'Simulated EEG':'EEG'} recording · ${r.summary?.clean_clips||0} usable clips`};update(recording);
 const draw=async()=>{item=await api('personal/matrix-open',{});if(ended)return;deadline=performance.now()+item.remaining*1000;progress.max=item.stage==='practice'?3:item.total;progress.value=item.index;label.textContent=item.stage==='practice'?`Practice ${item.index+1} / 3`:`Puzzle ${item.index+1} / ${item.total}`;image.src=item.stem.startsWith('data:image/')?item.stem:matrixAssets[item.stem];choices.replaceChildren();feedback.textContent='';item.choices.forEach((choice,i)=>{const button=personalButton('',()=>respond(choice.value,button));const img=document.createElement('img');img.src=choice.image.startsWith('data:image/')?choice.image:matrixAssets[choice.image];img.alt='Option '+(i+1);button.append(img,personalElement('span',String(i+1)));button.setAttribute('aria-label','Choose option '+(i+1));choices.append(button)});busy=false;tick()};
 const respond=async(value,button=null)=>{
  if(busy||ended||!item)return;busy=true;choices.querySelectorAll('button').forEach(b=>{b.disabled=true;b.setAttribute('aria-pressed',String(b===button))});
  try{const result=await api('personal/matrix-answer',{token:item.token,choice:value});await new Promise(r=>setTimeout(r,180));if(ended)return;
   if(result.complete){showResult(result.record);return}
   update({...last,matrix_result:result.estimate});
   if(result.practice){feedback.textContent=result.correct?'Correct.':'Not quite. Look for the pattern across rows and columns.';choices.replaceChildren(personalButton(result.correct?'Continue':'Try again',()=>draw()));item=null;timer.textContent='';busy=false}
   else await draw();
  }catch(e){feedback.textContent=e.message;busy=false;choices.querySelectorAll('button').forEach(b=>b.disabled=false)}
 };
 const tick=()=>{if(!item||ended)return;const seconds=Math.max(0,(deadline-performance.now())/1000);timer.textContent=`${Math.ceil(seconds)} s`;if(!seconds&&!busy)void respond(null)};
 ticker=setInterval(tick,100);poller=setInterval(async()=>{if(ended||polling||busy)return;polling=true;try{const r=await api('personal/status',{});if(ended||busy)return;if(r.running){if((r.matrix_result?.answered||0)<(last.matrix_result?.answered||0))r.matrix_result=last.matrix_result;update(r)}else{const saved=r.history?.find(v=>v.id===recording.id);if(saved)showResult(saved);else cleanup()}}catch(e){status.textContent=e.message}finally{polling=false}},1000);
 try{await draw()}catch(e){await stop();throw e}
}

function renderMatrixResult(r){
 chosenActivityTitle='Matrix reasoning';const host=$('personalResultsBody');host.replaceChildren();mountSessionActions(host,{...r,recordType:'personal',title:chosenActivityTitle,date:r.created},()=>showResultsBrowser('library'));
 host.append(personalElement('h2','Matrix reasoning'));const chart=personalElement('section');host.append(chart);matrixScorePanel(chart,r.matrix_result,r.matrix_eeg_demo,r.source);
 const details=personalElement('details');details.append(personalElement('summary','Recorded EEG'));const spectrum=personalElement('section');details.append(spectrum);host.append(details);const viewer=createRecordedSpectrum(spectrum,'matrix');loadPersonalSpectra(r,viewer);
 if(r.reason!=='Completed')host.append(personalElement('p','Partial session · '+r.reason,'muted'));
 $('personalResults').open=true;
}
