/* MaRs-IB SF1 run/results views. Synthetic EEG demo is never presented as validated IQ. */
function matrixScorePanel(host,estimate,demo,source){
 host._latest={estimate,demo,source};
 if(!host._matrixInitialized){host._matrixInitialized=true;const heading=personalElement('h3','Reasoning score');heading.append(headsetHelp('Reasoning score and uncertainty',[personalElement('p','Test: MaRs-IB short form 1, scored with the published 3PL model and a standard-normal ability prior. Score = 100 + 15 × posterior mean ability. Whiskers show a 95% Bayesian credible interval conditional on fixed published item parameters; they do not include norm-transfer or item-parameter uncertainty. This online US adult research reference is not a representative, age-adjusted IQ norm and does not measure full-scale IQ. Live feedback is an adaptation of the published procedure. Early estimates are strongly influenced by the prior.'),personalElement('p','EEG demo: an arbitrary fixed transformation of recorded band-power differences. It is not trained on IQ data, does not use your test answers, and has no demonstrated IQ accuracy. No confidence interval is assigned to it. Responses, item timing and EEG are saved locally for future validation.'),personalElement('a','Published validation study')]));const link=heading.querySelector('button')._helpDialog.querySelector('a');if(link){link.href='https://doi.org/10.3758/s13428-023-02067-8';link.target='_blank';link.rel='noopener'}host.append(heading,personalElement('small','Reference-sample estimate · not population IQ','matrix-limit'));
 const choices=host._matrixChoices||{test:true,eeg:true};host._matrixChoices=choices;const tools=personalElement('div',undefined,'button-row');for(const [key,label] of [['test','Test estimate'],['eeg','EEG demo']]){const l=personalElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=choices[key];c.onchange=()=>{choices[key]=c.checked;const v=host._latest;matrixScorePanel(host,v.estimate,v.demo,v.source)};l.append(c,document.createTextNode(label));tools.append(l)}host.append(tools);host._warning=personalElement('small','EEG DEMO · synthetic mapping; no demonstrated IQ accuracy','matrix-demo-warning');host.append(host._warning);host._chart=document.createElement('div');host._chart.className='matrix-score-chart';host.append(host._chart)}
 const choices=host._matrixChoices;host._warning.hidden=!choices.eeg;const chart=host._chart;chart.replaceChildren();
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 400 310');svg.setAttribute('role','img');svg.setAttribute('aria-label','Test estimate with 95% credible interval beside explicitly synthetic EEG demo');chart.append(svg);
 const node=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);return n},y=v=>250-(v-25)/150*220;
 for(const value of [40,70,100,130,160]){node('line',{x1:45,x2:385,y1:y(value),y2:y(value),stroke:'#dce4eb','stroke-width':value===100?1.5:1});node('text',{x:8,y:y(value)+4,fill:'#6c7e90','font-size':12},value)}
 for(const [key,label,value,x,color,range]of [['test','Test estimate',estimate?.score,100,'#527ca7',estimate?.interval],['eeg','EEG demo',demo?.score,255,'#be974d',null]]){
  if(!choices[key])continue;node('rect',{x:x-35,y:30,width:100,height:220,fill:color,opacity:.045});node('text',{x:x+15,y:276,'text-anchor':'middle',fill:'#40576b','font-size':13},label);
  if(value==null){node('text',{x:x+15,y:150,'text-anchor':'middle',fill:'#7c8996','font-size':12},key==='test'?'Answer a puzzle':'Waiting for EEG');continue}
  node('rect',{x:x-15,y:y(value),width:60,height:250-y(value),rx:4,fill:color,opacity:key==='test'?.85:.45});
  if(range){const lo=y(range[0]),hi=y(range[1]);node('line',{x1:x+15,x2:x+15,y1:hi,y2:lo,stroke:color,'stroke-width':2});for(const yy of [hi,lo])node('line',{x1:x+5,x2:x+25,y1:yy,y2:yy,stroke:color,'stroke-width':2})}
  node('text',{x:x+15,y:y(value)-9,'text-anchor':'middle',fill:'#28465f','font-size':17,'font-weight':600},Math.round(value));
 }
 if(estimate?.answered)chart.append(personalElement('p',`${estimate.correct} / ${estimate.answered} correct${estimate.partial?' · provisional':''}${estimate.interval?' · 95% interval '+estimate.interval.map(Math.round).join('–'):''}`,'matrix-score-caption'));

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
 const draw=async()=>{item=await api('personal/matrix-open',{});if(ended)return;deadline=performance.now()+item.remaining*1000;progress.max=item.stage==='practice'?3:12;progress.value=item.index;label.textContent=item.stage==='practice'?`Practice ${item.index+1} / 3`:`Puzzle ${item.index+1} / 12`;image.src=matrixAssets[item.stem];choices.replaceChildren();feedback.textContent='';item.choices.forEach((choice,i)=>{const button=personalButton('',()=>respond(choice.value,button));const img=document.createElement('img');img.src=matrixAssets[choice.image];img.alt='Option '+(i+1);button.append(img,personalElement('span',String(i+1)));button.setAttribute('aria-label','Choose option '+(i+1));choices.append(button)});busy=false;tick()};
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
