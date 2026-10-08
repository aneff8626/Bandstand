/* Conservative local display masking, not a guarantee of anonymization. */
function redactPhrase(value){
 const safe=new Set('i a the this that these those it its we you he she they my our your his her their and but or so if when where why how what which who there here yes no not now then also all some any one two three first second last more less for from to in on at of with without as is are was were be been being have has had do does did can could should would will may might must just very really please okay ok thanks thank hello hi'.split(' '));
 const known=new Set('john jane james mary michael david sarah sara emily robert william jennifer linda elizabeth susan jessica daniel thomas joseph charles patricia barbara richard paul mark andrew andy andrea josh joshua matt matthew chris christopher alex alexander emma olivia sophia ava noah liam ethan lucas ben benjamin amy anna anne ann rachel rebecca laura lauren lisa kevin brian eric steven stephen tim timothy jason justin nicole amanda ashley megan melissa michelle kim kimberly karen nancy sandra donna carol sharon ryan jacob nicholas sam samantha samuel natalie grace chloe zoe hannah victoria'.split(' '));
 let text=String(value||'');
 let custom=[];try{custom=JSON.parse(localStorage.getItem('decoderRedactNames')||'[]')}catch{}
 for(const name of custom.filter(n=>typeof n==='string'&&n.trim()).sort((a,b)=>b.length-a.length)){const escaped=name.trim().replace(/[.*+?^${}()|[\]\\]/g,'\\$&');text=text.replace(new RegExp('(?<![\\p{L}\\p{N}])'+escaped+'(?![\\p{L}\\p{N}])','giu'),'[name]')}
 text=text.replace(/\b(?:Dr|Mr|Mrs|Ms|Prof)\.?\s+[\p{L}][\p{L}'’-]*(?:\s+[A-Z][\p{L}'’-]*)?/gu,'[name]');
 return text.replace(/[\p{L}][\p{L}'’-]*/gu,word=>{const base=word.replace(/['’]s$/i,'');return known.has(base.toLowerCase())||(/^\p{Lu}/u.test(base)&&!safe.has(base.toLowerCase())&&base!=='EEG')?'[name]':word});
}
