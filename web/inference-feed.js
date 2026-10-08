/* Presentation only: cosine similarity is not a calibrated probability. */
function createInferenceFeed(){
 let mode='best',current=null,shownAt=0,lastKey='',seen=[],history=[],pending=new Map();
 const readingMs=text=>Math.min(20000,Math.max(4000,2000+text.trim().split(/\s+/).length/3*1000));
 return {setMode(value){mode=value==='all'?'all':'best';},update(prediction,now){
  const top=prediction?.candidates?.[0],key=prediction?.generated_at+':'+prediction?.trial;
  if(top&&Number.isFinite(top.similarity)&&key!==lastKey){
   lastKey=key;const item={text:top.text,score:top.similarity,time:prediction.generated_at,validated:!!prediction.validated,arrived:now};
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
