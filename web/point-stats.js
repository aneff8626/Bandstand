/* On-demand pointwise analysis. No trial arrays leave the local service. */
let pointStatsContext=null,pointStatsData=null,pointStatsRequest=0,pointStatsBusy=false,pointStatsTimer=null,pointStatsRevision='';
const graphStatsChoices=new Map(),graphStatsData={},graphStatsErrors={};
function statsIcon(kind){const e=document.createElementNS('http://www.w3.org/2000/svg','svg');e.setAttribute('viewBox','0 0 24 24');e.setAttribute('aria-hidden','true');e.classList.add('result-action-icon');e.innerHTML={stats:'<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/>',trash:'<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',book:'<path d="M12 5C9 2 4 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-2-1-7-2-10 1v16"/>'}[kind];return e}
function graphStatsKey(id){return pointStatsSession()?.id+':'+id}
function graphStatsEnabled(id){return graphStatsChoices.get(graphStatsKey(id))===true}
function syncGraphStatsControls(){
 document.querySelectorAll('canvas[id^="erp-"],canvas[id^="stageERP-"],canvas[id*="-spectrum-"],canvas[id*="-tf-"]').forEach(c=>{
  if(!c.closest('#channelERPs,#stageChannelERPs'))return;
  let row=c.nextElementSibling;if(!row?.classList.contains('graph-significance')){row=personalElement('div',undefined,'graph-significance');const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';label.append(check,document.createTextNode(c.id.includes('spectrum')?'Highlight significant frequencies':'Highlight significant time-windows'));const method=document.createElement('select');method.setAttribute('aria-label','Significance correction for '+c.id);for(const [v,t]of [['bh','Corrected (FDR)'],['by','FDR (BY)'],['holm','Corrected (Holm)'],['none','Uncorrected']])method.add(new Option(t,v));const status=personalElement('small',undefined,'graph-significance-status');status.setAttribute('role','status');row.append(label,method,status);c.after(row);check.onchange=async()=>{graphStatsChoices.set(graphStatsKey(c.id),check.checked);if(check.checked){const domain=c.id.includes('-tf-')?'map':'points';$('pointDomain').value=domain;await fetchPointStats(true,domain)}redrawPointStats()};method.onchange=()=>{$('pointCorrection').value=method.value;$('pointCorrection').dispatchEvent(new Event('change'));};}
  row.querySelector('input').checked=graphStatsEnabled(c.id);row.querySelector('select').value=$('pointCorrection').value;
  const status=row.querySelector('.graph-significance-status'),domain=c.id.includes('-tf-')?'map':'points',data=graphStatsData[domain],channel=c._pointTFChannel||c.id.split('-').at(-1),points=data?.session===pointStatsSession()?.id?data.channels[channel]?.points:undefined;
  status.hidden=!graphStatsEnabled(c.id);status.textContent=graphStatsErrors[domain]||(!points?'Calculating…':!points.some(p=>p.ready)?'Not enough usable data':points.some(p=>p.significant)?(domain==='points'?'Top bars':'Outlines')+' · '+(data.correction==='none'?'uncorrected':'corrected')+' p < .05':'No significant '+(domain==='map'?'cells':data.mode==='tf'?'frequencies':'timepoints'));

 });
}
function mountStatsActions(panel,step){
 let bar=step==='summary'?$('experimentResults')?.querySelector('.session-actions .button-row'):null;
 if(!bar){bar=$('runStatsActions');if(!bar){bar=personalElement('div',undefined,'button-row run-stats-actions');bar.id='runStatsActions';$('stageChannelERPs')?.before(bar)}}
 if(bar&&panel.parentElement!==bar)bar.append(panel);
 const quality=$('trialProgress')?.closest('section');if(quality&&!$('supplementalResults')){const extra=document.createElement('details');extra.id='supplementalResults';const title=document.createElement('summary');title.append(statsIcon('book'),document.createTextNode('Supplemental Results'));const body=personalElement('div',undefined,'supplemental-body');body.append(quality);body.prepend(personalButton('Close',()=>{extra.open=false}));extra.append(title,body);extra.addEventListener('toggle',()=>{if(extra.open)panel.open=false});bar?.append(extra)}
 const extra=$('supplementalResults');if(extra&&bar&&extra.parentElement!==bar)bar.append(extra);
}
function sessionRange(current){if(current?.session?.mode==='tf')return current.analysis?.band||current.session.band;return current?.session?.window?.map(v=>v*1000)}
function pointStatsSession(){return (!active&&selectedResult?selectedResult:state)?.session}
function redrawPointStats(){document.querySelectorAll('canvas[id^="erp-"],canvas[id^="stageERP-"],canvas[id*="-spectrum-"],canvas[id*="-tf-"]').forEach(c=>c._redraw?.())}
function clearPointStats(){pointStatsData=null;redrawPointStats()}
function significantRuns(points){
 const gaps=points.slice(1).map((p,i)=>p.x-points[i].x).filter(v=>v>0).sort((a,b)=>a-b),step=gaps[Math.floor(gaps.length/2)]||1,runs=[];let run=null;
 for(const p of points){if(!p.ready||!p.significant){run=null;continue}if(!run||p.x-run[1]>step*1.5){run=[p.x,p.x];runs.push(run)}else run[1]=p.x;}
 return runs.map(([lo,hi])=>[lo-step/2,hi+step/2]);
}
function pointStatsOverlay(id,view){
 const data=graphStatsData.points;if(!data||!graphStatsEnabled(id)||data.session!==pointStatsSession()?.id)return;
 const channel=id.split('-').at(-1),points=data.channels[channel]?.points||[],spectral=data.mode==='tf';
 const {ctx,x,box}=view;ctx.save();ctx.fillStyle='#7046ad';
 for(const [lo,hi]of significantRuns(points)){const left=Math.max(box.l,x(spectral?lo:lo/1000)),right=Math.min(box.r,x(spectral?hi:hi/1000));if(right>=left)ctx.fillRect(left,box.t+2,Math.max(2,right-left),4)}
 ctx.restore();
}
function pointStatsMapOverlay(id,tf,{ctx,left,top,cw,ch}){
 const el=$(id),data=graphStatsData.map;if(!data||!graphStatsEnabled(id)||data.session!==pointStatsSession()?.id)return;
 if(![Number($('pointFirst').value),Number($('pointSecond').value)].includes(el._pointTFCondition))return;
 const cells=new Set();
 for(const p of data.channels[el._pointTFChannel]?.points||[]){if(!p.significant)continue;const j=tf.times.findIndex(t=>Math.abs(t-p.time)<1e-5),k=tf.frequencies.findIndex(f=>Math.abs(f-p.x)<1e-5);if(j>=0&&k>=0)cells.add(`${j},${k}`)}
 ctx.save();ctx.strokeStyle='#7035ad';ctx.lineWidth=2;ctx.beginPath();
 for(const cell of cells){const [j,k]=cell.split(',').map(Number),x=left+j*cw,y=top+(tf.frequencies.length-1-k)*ch;
  if(!cells.has(`${j-1},${k}`)){ctx.moveTo(x,y);ctx.lineTo(x,y+ch)}
  if(!cells.has(`${j+1},${k}`)){ctx.moveTo(x+cw,y);ctx.lineTo(x+cw,y+ch)}
  if(!cells.has(`${j},${k+1}`)){ctx.moveTo(x,y);ctx.lineTo(x+cw,y)}
  if(!cells.has(`${j},${k-1}`)){ctx.moveTo(x,y+ch);ctx.lineTo(x+cw,y+ch)}
 }ctx.stroke();ctx.restore();if(cells.size)text(ctx,'Outline: '+(data.correction==='none'?'uncorrected':'corrected')+' p < .05',left+4,top-5,'#7035ad',9);
}
function syncStatsSpectralControls(session,current){
 const host=$('statsSpectralControls');if(!host)return;host.hidden=session.mode!=='tf';
 if(session.mode!=='tf')return;
 if(host.dataset.session!==session.id){host.replaceChildren();host.dataset.session=session.id;tfBandControl(host,session,current.analysis||{band:session.band});const label=personalElement('label','Plot'),selector=document.createElement('select');selector.id='statsPlotMode';selector.setAttribute('aria-label','Plot by condition or block');selector.add(new Option('By condition','condition'));selector.add(new Option('Each block','block'));label.append(selector);host.append(label);selector.onchange=()=>{for(const id of ['channelERPs','stageChannelERPs']){const parent=$(id);if(parent?._tfSession?.id!==session.id)continue;parent.dataset.tfKey='';drawTFChannels(id,parent._tfAnalysis,session,id==='stageChannelERPs')}};}
 const band=current.analysis?.band||session.band;host.querySelectorAll('.tf-band-control input').forEach((el,i)=>{if(document.activeElement!==el&&band)el.value=band[i]});
}
function initPointStats(){
 if($('pointStatsPanel'))return;
 const panel=document.createElement('details');panel.id='pointStatsPanel';panel.hidden=true;
 const button=document.createElement('summary');button.append(statsIcon('stats'),document.createTextNode('Stats · Provisional'));panel.append(button);
 const body=personalElement('div',undefined,'point-stats-body'),header=personalElement('div',undefined,'point-stats-heading');
 header.append(personalElement('h3','Stats · Provisional'),personalButton('×',()=>{panel.open=false}));header.lastChild.setAttribute('aria-label','Close statistics');body.append(header);const spectralControls=personalElement('div');spectralControls.id='statsSpectralControls';body.append(spectralControls);
 const controls=personalElement('div',undefined,'point-stats-controls');
 const field=(name,el)=>{const label=personalElement('label',name);el.setAttribute('aria-label',name);label.append(el);controls.append(label);return el};
 const select=(id,options)=>{const el=document.createElement('select');el.id=id;options.forEach(([value,label])=>{const o=new Option(label,value);el.add(o)});return el};
 field('Analysis',select('pointDomain',[['points','ERP / power spectrum'],['map','Time–frequency map']]));
 field('Compare',select('pointFirst',[]));field('With',select('pointSecond',[]));
 field('Test',select('pointMode',[['range','Each point in range'],['single','Single point']]));
 for(const [id,label]of [['pointLow','From'],['pointHigh','To']]){const el=document.createElement('input');el.type='number';el.id=id;field(label,el)}
 field('Correction',select('pointCorrection',[['bh','Corrected (FDR · BH)'],['by','Corrected (FDR · BY)'],['holm','Holm · family-wise'],['none','None · uncorrected']]));

 const live=document.createElement('input');live.type='checkbox';live.id='pointAuto';field('Update as completed trials arrive',live);
 body.append(controls,personalButton('Recalculate',()=>fetchPointStats()),personalButton('Use plot selection',()=>{const current=(!active&&selectedResult?selectedResult:state);const range=sessionRange(current);if(!range)return;$('pointMode').value='range';$('pointLow').value=range[0];$('pointHigh').value=range[1];queue()}),headsetHelp('Pointwise inference',[personalElement('p','ERP: a separate two-sided Welch test at each recorded time sample, using all accepted trials separately for each electrode (minimum 3 per condition). Spectra: tests at each native 0.5 Hz bin use the existing moving-block bootstrap of non-overlapping 2-second log-power segments, preserving gaps and trial boundaries. Only completed trials/blocks are used here.'),personalElement('p','The correction family is the full recorded ERP epoch or full 2–40 Hz spectrum × every recorded electrode, even when inspecting a narrower range. Time–frequency maps test each aligned cell across separate blocks (minimum 3 per condition), correcting all recorded cells × all four electrodes. Overlapping windows are separate tested coordinates, never independent observations. This controls the family for the chosen condition pair, including unavailable tests as p=1. Holm controls family-wise error without requiring independence between tests. BY controls FDR under general dependence; BH assumes independent or positively dependent tests. Corrections require valid underlying p-values.'),personalElement('p','These are exploratory within-session comparisons. They do not correct for choosing ranges after viewing data, testing other pairs, repeated live updates, trial dependence, or condition/order confounding. The spectral bootstrap is provisional and its minimum p-value is 0.001, which can limit discoveries with large correction families. Speller data are calibration-only and remain exploratory, not validation. Purple marks indicate p < .05 using the selected corrected or uncorrected method; each graph has its own highlight checkbox. Graph correction menus and Stats stay synchronized. Uncorrected marks do not control multiple comparisons. Marks and remain when the drawer closes; a significant sample does not establish component onset or duration. These settings do not alter recording or standard exports.') ]));
 const status=personalElement('p','Choose a range to calculate.','muted');status.id='pointStatsStatus';status.setAttribute('role','status');body.append(status);const output=personalElement('div');output.id='pointStatsOutput';body.append(output);panel.append(body);document.body.append(panel);
 const queue=()=>{clearTimeout(pointStatsTimer);++pointStatsRequest;delete graphStatsData.points;delete graphStatsData.map;delete graphStatsErrors.points;delete graphStatsErrors.map;syncGraphStatsControls();clearPointStats();$('pointStatsOutput').replaceChildren();$('pointStatsStatus').textContent='Updating…';$('pointHigh').closest('label').hidden=$('pointMode').value==='single';pointStatsTimer=setTimeout(async()=>{await fetchPointStats(true);const other=$('pointDomain').value==='map'?'points':'map';if([...document.querySelectorAll('.graph-significance input:checked')].some(el=>{const id=el.closest('.graph-significance').previousElementSibling.id;return (id.includes('-tf-')?'map':'points')===other}))await fetchPointStats(true,other)},350)};
 controls.querySelectorAll('input,select').forEach(el=>el.addEventListener(el.type==='number'?'input':'change',queue));
 panel.addEventListener('toggle',()=>{if(panel.open){if($('supplementalResults'))$('supplementalResults').open=false;fetchPointStats()}else{clearTimeout(pointStatsTimer)}});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&panel.open)panel.open=false});
 setInterval(()=>{
  const current=(!active&&selectedResult?selectedResult:state),session=current?.session,step=document.body.dataset.journeyStep;
  const visible=['run','summary'].includes(step)&&['erp','tf'].includes(session?.mode)&&[...document.querySelectorAll('#channelERPs canvas,#stageChannelERPs canvas')].some(c=>c.getClientRects().length);
  panel.hidden=!visible;if($('supplementalResults'))$('supplementalResults').hidden=!visible;if(!visible){if(panel.open)panel.open=false;return}
  mountStatsActions(panel,step);syncStatsSpectralControls(session,current);syncGraphStatsControls();
  if(pointStatsContext!==session.id){pointStatsContext=session.id;delete graphStatsData.points;delete graphStatsData.map;delete graphStatsErrors.points;delete graphStatsErrors.map;++pointStatsRequest;clearPointStats();pointStatsRevision='';$('pointStatsOutput').replaceChildren();const spectral=session.mode==='tf';$('pointDomain').value='points';$('pointDomain').closest('label').hidden=!spectral;for(const id of ['pointFirst','pointSecond']){const el=$(id);el.replaceChildren();session.conditions.forEach((c,i)=>el.add(new Option(c,String(i))))}$('pointSecond').value='1';for(const [id,val]of [['pointLow',spectral?2:0],['pointHigh',spectral?40:800]]){const el=$(id);el.min=spectral?2:-200;el.max=spectral?40:800;el.step=spectral?.5:1;el.value=val;el.closest('label').firstChild.textContent=(id==='pointLow'?'From':'To')+(spectral?' (Hz)':' (ms)');el.setAttribute('aria-label',el.closest('label').firstChild.textContent)}if(panel.open)fetchPointStats()}
  const map=$('pointDomain').value==='map';for(const id of ['pointMode','pointLow','pointHigh'])$(id).closest('label').hidden=map||(id==='pointHigh'&&$('pointMode').value==='single');
  const revision=String((!active&&selectedResult?selectedResult:state)?.analysis?.trial_count||0);
  if(panel.open&&$('pointAuto').checked&&!pointStatsBusy&&revision!==pointStatsRevision){pointStatsRevision=revision;fetchPointStats()}
 },1000);
}
async function fetchPointStats(force=false,domainOverride=null){
 const panel=$('pointStatsPanel'),session=pointStatsSession();if((!panel?.open&&!force)||panel.hidden||!session)return;const domain=domainOverride||$('pointDomain').value;
 const request=++pointStatsRequest,low=Number($('pointLow').value),single=$('pointMode').value==='single',high=single?low:Number($('pointHigh').value);
 if(domain===$('pointDomain').value){clearPointStats();$('pointStatsOutput').replaceChildren()}
 if($('pointDomain').value!=='map'&&($('pointLow').value===''||(!single&&$('pointHigh').value==='')||!Number.isFinite(low)||!Number.isFinite(high)||high<low)){$('pointStatsStatus').textContent='Enter a valid range.';return}
 const params=new URLSearchParams({low:domain==='points'?(session.mode==='tf'?2:-200):low,high:domain==='points'?(session.mode==='tf'?40:800):high,single:domain==='points'?false:single,first:$('pointFirst').value,second:$('pointSecond').value,correction:$('pointCorrection').value,full:true,domain});
 delete graphStatsErrors[domain];pointStatsBusy=request;if(domain===$('pointDomain').value)$('pointStatsStatus').textContent='Calculating…';
 try{const data=await api(`point-statistics/${session.id}?${params}`);if(request!==pointStatsRequest||session.id!==pointStatsSession()?.id)return;graphStatsData[domain]={...data,session:session.id};if(domain===$('pointDomain').value){pointStatsData=graphStatsData[domain];const inspected=domain==='points'?{...data,channels:Object.fromEntries(Object.entries(data.channels).map(([ch,c])=>[ch,{...c,points:single?c.points.filter(p=>p.x===c.points.reduce((best,v)=>Math.abs(v.x-low)<Math.abs(best.x-low)?v:best,c.points[0])?.x):c.points.filter(p=>p.x>=low&&p.x<=high)}]))}:data;renderPointStats(inspected)}redrawPointStats()}
 catch(e){if(request===pointStatsRequest){graphStatsErrors[domain]=e.message;$('pointStatsStatus').textContent=e.message}}
 finally{if(pointStatsBusy===request)pointStatsBusy=false;syncGraphStatsControls()}
}
function renderPointStats(data){
 const map=data.mode==='tf-map';
 const count=Object.values(data.channels).reduce((n,c)=>n+c.points.filter(p=>p.significant).length,0);
 $('pointStatsStatus').textContent=`${data.conditions.join(' − ')} · ${data.ready_count}/${data.family_size} tests available (through ${data.trial_count} completed trials/blocks) · ${count} displayed points below ${data.correction==='none'?'uncorrected':'adjusted'} p = .05`;
 const output=$('pointStatsOutput');output.replaceChildren(personalElement('small',data.method+' · completed trials/blocks only'));
 if(data.calibration)output.append(personalElement('p','Calibration data · exploratory, not held-out accuracy.','muted'));
 for(const [ch,c]of electrodeEntries(data.channels)){
  const section=personalElement('section'),heading=personalElement('h4',electrodeLabel(ch));section.append(heading);
  const plot=document.createElement('canvas');plot.hidden=map;plot.id='point-probability-'+ch;plot.height=120;section.append(plot);
  const detail=document.createElement('details');detail.append(personalElement('summary','Point values'));const table=document.createElement('table'),head=document.createElement('tr');for(const s of [...(map?['Time (s)']:[]),data.unit,'Δ','n A/B','p','Adjusted p'])head.append(personalElement('th',s));table.append(head);
  const fmt=v=>v==null?'—':Number(v).toPrecision(3);
  (map?c.points.filter(p=>p.significant).slice(0,200):c.points).forEach(p=>{const row=document.createElement('tr');row.classList.toggle('point-significant',p.significant);for(const value of [...(map?[p.time]:[]),Number(p.x.toFixed(2)),fmt(p.difference),p.n.join('/'),fmt(p.p),fmt(p.adjusted_p)])row.append(personalElement('td',String(value)));if(p.reason)row.title=p.reason;table.append(row)});detail.append(table);section.append(detail);if(map)section.append(personalElement('small',`${c.points.filter(p=>p.significant).length} ${data.correction==='none'?'uncorrected':'corrected'} cells; point table shows up to 200 discoveries. Open Time–frequency power below the electrode plot to view outlines.`));
  const unavailable=c.points.filter(p=>!p.ready);if(unavailable.length)section.append(personalElement('small',[...new Set(unavailable.map(p=>p.reason))].join(' · ')));
  output.append(section);
  const draw=()=>{const {ctx,w,h}=canvas(plot.id),pts=c.points,lo=pts[0]?.x??0,hi=pts.at(-1)?.x??lo+1,x=v=>30+(v-lo)/(hi-lo||1)*(w-42),y=p=>h-25-Math.min(5,-Math.log10(Math.max(p,1e-5)))*(h-40)/5;line(ctx,[[30,y(.05)],[w-12,y(.05)]],'#9b8cae',1);text(ctx,'.05',0,y(.05)+3,'#786b88',9);text(ctx,'Adjusted p (log scale)',30,11,'#786b88',9);for(const p of pts){if(!p.ready)continue;ctx.beginPath();ctx.fillStyle=p.significant?'#7046ad':'#9ca5b0';ctx.arc(hi===lo?w/2:x(p.x),y(p.adjusted_p),2.3,0,Math.PI*2);ctx.fill()}text(ctx,String(Number(lo.toFixed(1))),30,h-7);if(hi!==lo)text(ctx,String(Number(hi.toFixed(1)))+' '+data.unit,w-57,h-7)};plot._redraw=draw;if(!map)draw();
 }
}
