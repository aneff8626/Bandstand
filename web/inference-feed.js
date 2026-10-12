/* Presentation only: cosine similarity is not a calibrated probability. */
function createInferenceFeed(){
 let mode='best',current=null,shownAt=0,lastKey='',seen=[],history=[],pending=new Map();
 const readingMs=text=>Math.min(20000,Math.max(4000,2000+text.trim().split(/\s+/).length/3*1000));
 return {setMode(value){mode=value==='all'?'all':'best';},update(prediction,now){
  const top=prediction?.candidates?.[0],key=prediction?.generated_at+':'+prediction?.trial;
  if(top&&Number.isFinite(top.similarity)&&key!==lastKey){
   lastKey=key;const item={gist:suggestedGist(prediction.candidates),matches:prediction.candidates.slice(0,5).map(c=>({text:c.text,similarity:c.similarity})),text:top.text,score:top.similarity,time:prediction.generated_at,validated:!!prediction.validated,arrived:now};
   seen.unshift(item);seen=seen.slice(0,100);
   const old=pending.get(item.text);pending.set(item.text,{...item,hits:(old?.hits||0)+1});
   if(!current){current=item;shownAt=now;pending.delete(item.text)}
  }
  for(const [text,item] of pending)if(now-item.arrived>10000||text===current?.text)pending.delete(text);
  if(current&&now-shownAt>=readingMs(current.text)){
   const choices=[...pending.values()];const extra=now-shownAt-readingMs(current.text);
   const eligible=mode==='all'?choices:choices.filter(x=>x.hits>=2||x.score>=current.score+.05);
   const pool=eligible.length?eligible:extra>=5000?choices:[];
   pool.sort(mode==='all'?(a,b)=>b.arrived-a.arrived:(a,b)=>b.score-a.score);
   if(pool.length){history.unshift(current);history=history.slice(0,30);current=pool[0];shownAt=now;pending.clear()}
  }
  const previous=mode==='all'?seen.filter(x=>current&&x.time<current.time):history;
  return {current,previous:previous.slice(0,20),mode,readingMs:current?readingMs(current.text):0};
 }};
}

/* Extract shared wording only; no model calls, paraphrasing or confidence claims. */
function suggestedGist(candidates){
 const stop=new Set('a an the and or but if then of to in on at for from with by as is are was were be been being it its this that these those i me my we our you your he she they them their have has had do does did very really just some any about'.split(' '));
 const rows=[...new Map((candidates||[]).slice(0,5).filter(c=>typeof c.text==='string'&&Number.isFinite(c.similarity)).map(c=>[c.text.toLowerCase().trim(),c])).values()];
 if(rows.length<2)return 'Meaning unclear';
 const support=new Map();
 rows.forEach((row,rank)=>{const words=row.text.match(/[\p{L}\p{N}]+(?:['’][\p{L}]+)?/gu)||[];const seen=new Set();
  for(let n=2;n<=5;n++)for(let i=0;i+n<=words.length;i++){const span=words.slice(i,i+n),key=span.join(' ').toLowerCase();if(stop.has(span[0].toLowerCase())||stop.has(span.at(-1).toLowerCase())||span.filter(w=>!stop.has(w.toLowerCase())).length<2||seen.has(key))continue;seen.add(key);const old=support.get(key)||{text:span.join(' '),hits:0,score:0};old.hits++;old.score+=1/(rank+1);support.set(key,old);}
 });
 const shared=[...support.values()].filter(x=>x.hits>=2).sort((a,b)=>b.hits-a.hits||b.score-a.score||b.text.length-a.text.length);
 return shared[0]?.text||'Meaning unclear';
}
