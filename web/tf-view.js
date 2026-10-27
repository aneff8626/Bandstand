/* Separate electrodes and block-level statistics for spectral experiments. */
let tfBandRequest=0, tfPreviewBand=null, tfPreviewFrame=0;
async function setTFBand(session,band){
 const request=++tfBandRequest;
 try{const result=await api(`tf-band/${session.id}/${band[0]}/${band[1]}`);if(request!==tfBandRequest)return;if(!active)selectedResult=result;else state.analysis=result.analysis;renderRevision='';render()}catch(e){toast(e.message)}
}
function tfBandControl(parent,session,analysis){
 const bar=document.createElement('div');bar.className='tf-band-control';
 const band=analysis.band||session.band;bar.append(personalElement('span','Analyze frequencies (Hz)'));
 const low=document.createElement('input'),high=document.createElement('input');for(const [input,value,name]of [[low,band[0],'Low frequency (Hz)'],[high,band[1],'High frequency (Hz)']]){input.type='number';input.min=2;input.max=40;input.step=.05;input.value=value;input.setAttribute('aria-label',name);bar.append(input)}
 let timer;const change=()=>{clearTimeout(timer);timer=setTimeout(async()=>{const lo=Number(low.value),hi=Number(high.value);if(!(lo>=2&&lo<hi&&hi<=40))return;setTFBand(session,[lo,hi])},300)};
 low.oninput=high.oninput=change;bar.append(headsetHelp('Frequency comparison',[personalElement('p','Enter any range from 2–40 Hz, or drag across a spectrum. All electrode comparisons update automatically. Means and SD use clean non-overlapping 2-second segments, including the current block. Approximate 95% intervals and p-values use moving-block bootstrap chunks within continuous recorded periods, never across gaps or blocks. At least 24 clean seconds per condition are needed; correlation, short runs or drift can require more. This is a comparison of the recorded periods, not a causal or population claim. Repeated live looks and selected bands are exploratory; intervals are not sequentially adjusted. PSD shading separately describes uncertainty across eligible trial blocks (10 or more).')]));parent.append(bar);
}
function drawTFChannels(parentId,a,session,compact=false){
 const parent=$(parentId);if(!parent)return;parent.hidden=false;parent._tfSession=session;parent._tfPlotMode=$('statsPlotMode')?.value||'condition';
 parent._tfAnalysis=a;const key=session.id+'/'+a.trial_count+'/'+a.pending+'/'+(a.statistics_revision||0)+'/'+(parent._tfPlotMode||'condition') ;if(parent.dataset.tfKey===key&&parent.querySelector('canvas')){drawTFSpectra(parentId,a);for(const [ch,v] of electrodeEntries(a.channels)){drawTFStats(parentId+'-power-'+ch,v,parentId+'-note-'+ch,session);$(parentId+'-title-'+ch).textContent=`${a.band.join('–')} Hz power · ${session.window.join('–')} s after cue`;}const inputs=parent.querySelectorAll('.tf-band-control input');inputs.forEach((el,i)=>{if(document.activeElement!==el)el.value=a.band[i]});return;}parent.dataset.tfKey=key;parent.replaceChildren();
 for(const [ch,v]of electrodeEntries(a.channels)){
  const card=document.createElement('section');card.className='panel electrode-result';electrodeGridPosition(card,ch);const title=document.createElement('h3');title.textContent=electrodeLabel(ch);card.append(title);
  const spectrum=document.createElement('canvas');spectrum.id=parentId+'-spectrum-'+ch;spectrum.height=compact?160:220;card.append(spectrum);
  const counts=document.createElement('p');counts.className='muted';counts.textContent=v.groups.map(g=>`${g.label}: ${g.segment_features?.length||0} segments · ${g.accepted} ${a.clip_inference?'usable clips':'eligible blocks'} · ${g.clean_seconds.toFixed(1)} clean seconds · ${g.rejected} rejected${g.blocks?.some(b=>b.partial)?' · current block in progress':''}`).join(' | ');card.append(counts);
  const h=document.createElement('h4');h.id=parentId+'-title-'+ch;h.textContent=`${a.band.join('–')} Hz power · ${session.window.join('–')} s after cue`;card.append(h);
  const comparison=document.createElement('canvas');comparison.id=parentId+'-power-'+ch;comparison.height=compact?160:220;const note=document.createElement('p');note.id=parentId+'-note-'+ch;note.className='muted';card.append(comparison,note);parent.append(card);
  drawTFStats(comparison.id,v,note.id,session);
  const detail=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Time–frequency power';detail.append(summary);card.append(detail);
  const maps=[];v.groups.forEach((g,i)=>{const label=document.createElement('p');label.textContent=g.label;const map=document.createElement('canvas');map.id=parentId+'-tf-'+ch+'-'+i;map.height=180;detail.append(label,map);maps.push([map.id,g.tf])});for(const [id,tf]of maps){$(id)._pointTFChannel=ch;$(id)._pointTFCondition=maps.findIndex(v=>v[0]===id);$(id)._redraw=()=>heatmap(id,tf)}detail.ontoggle=()=>{if(detail.open)for(const [id,tf]of maps)heatmap(id,tf)};

 }
 drawTFSpectra(parentId,a);
}

function drawTFSpectra(parentId,a){
 for(const [ch,v]of electrodeEntries(a.channels)){
  const id=parentId+'-spectrum-'+ch;if(!$(id))continue;$(id)._redraw=()=>drawTFSpectra(parentId,a);
  const live=a.live_preview?.[ch]?.map(p=>10*Math.log10(Math.max(p,1e-12)));
  const values=[...v.groups.flatMap(g=>g.psd?g.psd.mean.flatMap((m,k)=>[m-(g.psd.ci95?.[k]||0),m+(g.psd.ci95?.[k]||0)]):[]),...(live||[])],lo=Math.min(-10,...values)-3,hi=Math.max(10,...values)+3;
  const {ctx,x,y,box}=axes(id,2,40,lo,hi,'Frequency (Hz)','dB / Hz');for(const [l,h,label,tint]of [[2,4,'δ','#758da0'],[4,8,'θ','#8d82a2'],[8,13,'α','#739c8d'],[13,20,'Low β','#b6a17a'],[20,30,'High β','#ac8c83'],[30,40,'γ','#8292a1']]){ctx.globalAlpha=.045;ctx.fillStyle=tint;ctx.fillRect(x(l),box.t,x(h)-x(l),box.b-box.t);ctx.globalAlpha=.45;text(ctx,label,x((l+h)/2)-12,box.t+12,'#718078',9);ctx.globalAlpha=1;}
  const band=tfPreviewBand||a.band;ctx.fillStyle='#426c9838';ctx.fillRect(x(band[0]),box.t,Math.max(2,x(band[1])-x(band[0])),box.b-box.t);for(const f of band)line(ctx,[[x(f),box.t],[x(f),box.b]],'#426c98',1.5);
  setupFrequencyDrag($(id),box,$(parentId)._tfSession);
  for(const f of [2,10,20,30,40])text(ctx,String(f),x(f)-5,box.b+16);
  const plotGroups=$(parentId)._tfPlotMode==='block'?v.groups.flatMap((g,i)=>(g.blocks||[]).filter(b=>b.psd).map(b=>({label:`Block ${b.index+1} · ${g.label}`,plotColor:colors[i],psd:{mean:b.psd}}))):v.groups;
  v.groups.forEach((g,i)=>text(ctx,g.label,55+i*(box.r-55)/v.groups.length,12,colors[i],10));
  plotGroups.forEach((g,i)=>{const color=g.plotColor||colors[i];if(g.psd){const m=g.psd.mean,ci=g.psd.ci95;ctx.save();ctx.beginPath();ctx.rect(box.l,box.t,box.r-box.l,box.b-box.t);ctx.clip();if(ci){ctx.beginPath();m.forEach((v,k)=>{k?ctx.lineTo(x(a.frequencies[k]),y(v+ci[k])):ctx.moveTo(x(a.frequencies[k]),y(v+ci[k]))});for(let k=m.length-1;k>=0;k--)ctx.lineTo(x(a.frequencies[k]),y(m[k]-ci[k]));ctx.closePath();ctx.fillStyle=colors[i];ctx.globalAlpha=.15;ctx.fill();ctx.globalAlpha=1;}line(ctx,m.map((p,k)=>[x(a.frequencies[k]),y(p)]),color,2);ctx.restore();}});
  if(typeof pointStatsOverlay==='function')pointStatsOverlay(id,{ctx,x,box});
  if(live){ctx.setLineDash([4,3]);line(ctx,live.map((p,k)=>[x(a.frequencies[k]),y(p)]),colors[a.live_condition],1,.6);ctx.setLineDash([])}
 }
}

function setupFrequencyDrag(el,box,session){
 const axisDown=el.onpointerdown,axisMove=el.onpointermove;
 el.title='Click for one 0.5 Hz bin; drag to select a frequency range. Drag the left axis ends to scale.';
 const inside=e=>{const r=el.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;return px>=box.l&&px<=box.r&&py>=box.t&&py<=box.b};
 el.onpointermove=e=>{if(document.documentElement.classList.contains('tf-selecting')||inside(e)){el.style.cursor='crosshair';return}axisMove?.(e)};
 el.onpointerdown=e=>{if(!inside(e)){axisDown?.(e);return}e.preventDefault();document.documentElement.classList.add('tf-selecting');el.style.cursor='crosshair';const rect=el.getBoundingClientRect();
 const hz=e=>Math.max(2,Math.min(40,Math.round((2+(e.clientX-rect.left-box.l)/(box.r-box.l)*38)*20)/20));
 const anchor=hz(e);let last=0,band=null;
 const move=e=>{const end=hz(e);if(end===anchor)return;band=[Math.min(anchor,end),Math.max(anchor,end)];tfPreviewBand=band;if(!tfPreviewFrame)tfPreviewFrame=requestAnimationFrame(()=>{tfPreviewFrame=0;document.querySelectorAll('[id*="-spectrum-"]').forEach(c=>c._redraw?.())});if(performance.now()-last>80){last=performance.now();setTFBand(session,band)}};
 const finish=()=>{document.documentElement.classList.remove('tf-selecting');window.removeEventListener('blur',finish);window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',finish);tfPreviewBand=null;setTFBand(session,band||[Math.round(anchor*2)/2,Math.round(anchor*2)/2])};
 window.addEventListener('blur',finish);window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);
 };
}

function drawTFStats(id,data,noteId,session){
 const parent=$(id).closest('[id="channelERPs"], [id="stageChannelERPs"]');
 const separate=parent?._tfPlotMode==='block';
 const items=separate?data.groups.flatMap((g,c)=>(g.blocks||[]).map(b=>({...b,label:`${b.index+1}${b.partial?'*':''}`,color:colors[c],mean:b.mean,sd:b.sd}))).sort((a,b)=>a.index-b.index):data.groups.map((g,c)=>({label:g.label,features:g.segment_features||[],mean:g.descriptive_mean,sd:g.sd,color:colors[c]}));
 $(id)._redraw=()=>drawTFStats(id,data,noteId,session);
 const values=items.flatMap(g=>[...g.features,...(g.mean==null?[]:[g.mean-(g.sd||0),g.mean+(g.sd||0)])]);
 const low=values.length?Math.min(...values):-1,high=values.length?Math.max(...values):1,pad=Math.max(1,high-low)*.15;
 const {ctx,x,y,box}=axes(id,0,items.length+1,low-pad,high+pad,separate?'Block · mean ± SD (* = in progress)':'Condition','dB');
 items.forEach((g,j)=>{const px=x(j+1);g.features.forEach((v,i)=>{ctx.beginPath();ctx.fillStyle=g.color;ctx.globalAlpha=.4;ctx.arc(px+Math.sin(i*7.1)*Math.min(18,(box.r-box.l)/(items.length+1)*.2),y(v),2.5,0,Math.PI*2);ctx.fill()});ctx.globalAlpha=1;if(g.mean!=null){line(ctx,[[px-8,y(g.mean)],[px+8,y(g.mean)]],g.color,3);if(g.sd!=null){line(ctx,[[px,y(g.mean-g.sd)],[px,y(g.mean+g.sd)]],g.color,1.5)}}text(ctx,g.label.length>18?g.label.slice(0,17)+'…':g.label,px-12,box.b+16,g.color,10)});
 const descriptions=data.groups.map(g=>`${g.label}: ${g.descriptive_mean==null?'waiting':g.descriptive_mean.toFixed(2)+' dB'}${g.sd==null?'':', SD '+g.sd.toFixed(2)} (n=${g.segment_features?.length||0} segments)`).join(' · ');
 const format=(s,labels)=>!s.ready?s.reason:`${labels.join(' − ')}: Δ ${s.difference.toFixed(2)} dB, approximate 95% CI [${s.ci95.map(v=>v.toFixed(2)).join(', ')}], p = ${(s.adjusted_p??s.p).toPrecision(3)}`;
 const inference=data.pairwise?.length?data.pairwise.map(s=>format(s,s.labels)).join(' · ')+' (Holm corrected within electrode)':format(data.stats,data.groups.map(g=>g.label));
 $(noteId).textContent=descriptions+' — Exploratory within-recording comparison: '+inference;
}
