/* Separate electrodes and block-level statistics for spectral experiments. */
let tfBandRequest=0, tfPreviewBand=null, tfPreviewFrame=0;
async function setTFBand(session,band){
 const request=++tfBandRequest;
 try{const result=await api(`tf-band/${session.id}/${band[0]}/${band[1]}`);if(request!==tfBandRequest)return;if(!active)selectedResult=result;else state.analysis=result.analysis;renderRevision='';render()}catch(e){toast(e.message)}
}
function tfBandControl(parent,session,analysis){
 const bar=document.createElement('div');bar.className='tf-band-control';
 const label=document.createElement('label');label.textContent='Frequency band ';const menu=document.createElement('select');
 for(const [name,value]of [['Theta · 4–7 Hz','4,7'],['Alpha · 8–13 Hz','8,13'],['Low beta · 13–20 Hz','13,20'],['High beta · 20–30 Hz','20,30'],['Custom','custom']]){const o=document.createElement('option');o.textContent=name;o.value=value;menu.append(o)}
 const band=analysis.band||session.band;menu.value=['4,7','8,13','13,20','20,30'].includes(band.join(','))?band.join(','):'custom';label.append(menu);bar.append(label);
 const low=document.createElement('input'),high=document.createElement('input');for(const [input,value,name]of [[low,band[0],'Low frequency (Hz)'],[high,band[1],'High frequency (Hz)']]){input.type='number';input.min=2;input.max=40;input.step=.05;input.value=value;input.setAttribute('aria-label',name);input.hidden=menu.value!=='custom';bar.append(input)}
 let timer;const change=()=>{clearTimeout(timer);timer=setTimeout(async()=>{const lo=Number(low.value),hi=Number(high.value);if(!(lo>=2&&lo<hi&&hi<=40))return;setTFBand(session,[lo,hi])},300)};
 menu.onchange=()=>{low.hidden=high.hidden=menu.value!=='custom';if(menu.value!=='custom'){[low.value,high.value]=menu.value.split(',');change()}};low.oninput=high.oninput=change;parent.append(bar);
}
function drawTFChannels(parentId,a,session,compact=false){
 const parent=$(parentId);if(!parent)return;parent.hidden=false;parent._tfSession=session;
 const key=session.id+'/'+a.trial_count+'/'+a.pending ;if(parent.dataset.tfKey===key){drawTFSpectra(parentId,a);for(const [ch,v] of electrodeEntries(a.channels)){drawStats(parentId+'-power-'+ch,v,parentId+'-note-'+ch);$(parentId+'-title-'+ch).textContent=`${a.band.join('–')} Hz power · ${session.window.join('–')} s after cue`;}const menu=parent.querySelector('.tf-band-control select'),preset=a.band.join(',');menu.value=['4,7','8,13','13,20','20,30'].includes(preset)?preset:'custom';const inputs=parent.querySelectorAll('.tf-band-control input');inputs.forEach((el,i)=>{el.hidden=menu.value!=='custom';if(document.activeElement!==el)el.value=a.band[i]});return;}parent.dataset.tfKey=key;parent.replaceChildren();
 tfBandControl(parent,session,a);
 const explanation=document.createElement('p');explanation.className='muted';explanation.textContent='2 s windows · 0.5 s steps · at least 4 clean seconds per electrode per block. Dashed spectrum: latest clean 2 s. Small dots: clean, non-overlapping 2 s segments, including partially usable blocks. Means and tests use eligible blocks. Shading: pointwise 95% CI across eligible blocks (≥10). Band review is exploratory.';if(a.clip_inference)explanation.textContent='Exploratory clip-level comparison · Non-overlapping 2 s clips. Clips from the same block are correlated; these p-values may overstate the evidence. Spectral confidence intervals still use eligible blocks (≥10).';parent.append(explanation);
 for(const [ch,v]of electrodeEntries(a.channels)){
  const card=document.createElement('section');card.className='panel electrode-result';electrodeGridPosition(card,ch);const title=document.createElement('h3');title.textContent=electrodeLabel(ch);card.append(title);
  const spectrum=document.createElement('canvas');spectrum.id=parentId+'-spectrum-'+ch;spectrum.height=compact?160:220;card.append(spectrum);
  const counts=document.createElement('p');counts.className='muted';counts.textContent=v.groups.map(g=>`${g.label}: ${g.segment_features?.length||0} segments · ${g.accepted} ${a.clip_inference?'usable clips':'eligible blocks'} · ${g.clean_seconds.toFixed(1)} clean seconds · ${g.rejected} rejected`).join(' | ');card.append(counts);
  const h=document.createElement('h4');h.id=parentId+'-title-'+ch;h.textContent=`${a.band.join('–')} Hz power · ${session.window.join('–')} s after cue`;card.append(h);
  const comparison=document.createElement('canvas');comparison.id=parentId+'-power-'+ch;comparison.height=compact?160:220;const note=document.createElement('p');note.id=parentId+'-note-'+ch;note.className='muted';card.append(comparison,note);parent.append(card);
  drawStats(comparison.id,v,note.id);
  const detail=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Time–frequency power';detail.append(summary);card.append(detail);
  const maps=[];v.groups.forEach((g,i)=>{const label=document.createElement('p');label.textContent=g.label;const map=document.createElement('canvas');map.id=parentId+'-tf-'+ch+'-'+i;map.height=180;detail.append(label,map);maps.push([map.id,g.tf])});detail.ontoggle=()=>{if(detail.open)for(const [id,tf]of maps)heatmap(id,tf)};

 }
 drawTFSpectra(parentId,a);
}

function drawTFSpectra(parentId,a){
 for(const [ch,v]of electrodeEntries(a.channels)){
  const id=parentId+'-spectrum-'+ch;if(!$(id))continue;$(id)._redraw=()=>drawTFSpectra(parentId,a);
  const live=a.live_preview?.[ch]?.map(p=>10*Math.log10(Math.max(p,1e-12)));
  const values=[...v.groups.flatMap(g=>g.psd?g.psd.mean.flatMap((m,k)=>[m-(g.psd.ci95?.[k]||0),m+(g.psd.ci95?.[k]||0)]):[]),...(live||[])],lo=Math.min(-10,...values)-3,hi=Math.max(10,...values)+3;
  const {ctx,x,y,box}=axes(id,2,40,lo,hi,'Frequency (Hz)','dB / Hz');for(const [l,h,label,tint]of [[2,4,'δ','#758da0'],[4,8,'θ','#8d82a2'],[8,13,'α','#739c8d'],[13,20,'Low β','#b6a17a'],[20,30,'High β','#ac8c83'],[30,40,'γ','#8292a1']]){ctx.globalAlpha=.045;ctx.fillStyle=tint;ctx.fillRect(x(l),box.t,x(h)-x(l),box.b-box.t);ctx.globalAlpha=.45;text(ctx,label,x((l+h)/2)-12,box.t+12,'#718078',9);ctx.globalAlpha=1;}
  const band=tfPreviewBand||a.band;ctx.fillStyle='#426c9838';ctx.fillRect(x(band[0]),box.t,x(band[1])-x(band[0]),box.b-box.t);for(const f of band)line(ctx,[[x(f),box.t],[x(f),box.b]],'#426c98',1.5);
  setupFrequencyDrag($(id),box,$(parentId)._tfSession);
  for(const f of [2,10,20,30,40])text(ctx,String(f),x(f)-5,box.b+16);
  v.groups.forEach((g,i)=>{text(ctx,g.label,55+i*130,12,colors[i]);if(g.psd){const m=g.psd.mean,ci=g.psd.ci95;ctx.save();ctx.beginPath();ctx.rect(box.l,box.t,box.r-box.l,box.b-box.t);ctx.clip();if(ci){ctx.beginPath();m.forEach((v,k)=>{k?ctx.lineTo(x(a.frequencies[k]),y(v+ci[k])):ctx.moveTo(x(a.frequencies[k]),y(v+ci[k]))});for(let k=m.length-1;k>=0;k--)ctx.lineTo(x(a.frequencies[k]),y(m[k]-ci[k]));ctx.closePath();ctx.fillStyle=colors[i];ctx.globalAlpha=.15;ctx.fill();ctx.globalAlpha=1;}line(ctx,m.map((p,k)=>[x(a.frequencies[k]),y(p)]),colors[i],2);ctx.restore();}});
  if(live){ctx.setLineDash([4,3]);line(ctx,live.map((p,k)=>[x(a.frequencies[k]),y(p)]),colors[a.live_condition],1,.6);ctx.setLineDash([])}
 }
}

function setupFrequencyDrag(el,box,session){
 const axisDown=el.onpointerdown,axisMove=el.onpointermove;
 el.title='Drag across the spectrum to select frequencies. Drag the left axis ends to scale.';
 const inside=e=>{const r=el.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;return px>=box.l&&px<=box.r&&py>=box.t&&py<=box.b};
 el.onpointermove=e=>{if(document.documentElement.classList.contains('tf-selecting')||inside(e)){el.style.cursor='crosshair';return}axisMove?.(e)};
 el.onpointerdown=e=>{if(!inside(e)){axisDown?.(e);return}e.preventDefault();document.documentElement.classList.add('tf-selecting');el.style.cursor='crosshair';const rect=el.getBoundingClientRect();
 const hz=e=>Math.max(2,Math.min(40,Math.round((2+(e.clientX-rect.left-box.l)/(box.r-box.l)*38)*20)/20));
 const anchor=hz(e);let last=0,band=null;
 const move=e=>{const end=hz(e);if(end===anchor)return;band=[Math.min(anchor,end),Math.max(anchor,end)];tfPreviewBand=band;if(!tfPreviewFrame)tfPreviewFrame=requestAnimationFrame(()=>{tfPreviewFrame=0;document.querySelectorAll('[id*="-spectrum-"]').forEach(c=>c._redraw?.())});if(performance.now()-last>80){last=performance.now();setTFBand(session,band)}};
 const finish=()=>{document.documentElement.classList.remove('tf-selecting');window.removeEventListener('blur',finish);window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',finish);tfPreviewBand=null;if(band)setTFBand(session,band)};
 window.addEventListener('blur',finish);window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);
 };
}
