const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els={},sent=[];
function el(id){return els[id]??=( {value:'',selectionStart:0,selectionEnd:0,classList:{toggle(){}},handlers:{},addEventListener(k,v){this.handlers[k]=v},closest(){return this},focus(){},setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b}})}
const context={console,$:el,api:async(path,body)=>{sent.push({path,body});return {}},toast:()=>{},now:()=>100,crypto:{randomUUID:()=>String(sent.length)+'-word'},state:{typing:{running:true}},active:false,show:()=>{},setMode:()=>{},mode:'erp',document:{body:{classList:{toggle(){}}},querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},setTimeout:()=>1,clearTimeout:()=>{},Promise};
vm.createContext(context);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../web/inference-feed.js'),'utf8'),context);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../web/typing.js'),'utf8'),context);
const editor=el('writingEditor');function input(type,data,next){editor.selectionStart=editor.selectionEnd=editor.value.length;editor.handlers.beforeinput({target:editor,inputType:type,data,isComposing:false});editor.value=next;editor.handlers.input({target:editor})}
(async()=>{
 for(const c of 'hellp')input('insertText',c,editor.value+c);
 input('deleteContentBackward',null,'hell');input('insertText','o','hello');input('insertText',' ','hello ');
 await vm.runInContext('typingChain',context);
 const onset=sent.filter(r=>r.body?.kind==='onset'),commit=sent.filter(r=>r.body?.kind==='commit');assert.equal(onset.length,1);assert.equal(commit.length,1);assert.equal(commit[0].body.text,'hello');assert.equal(commit[0].body.edited,true);assert.equal(commit[0].body.unsupported,false);
 sent.length=0;input('insertFromPaste','pasted text ','hello pasted text ');await vm.runInContext('typingChain',context);assert.equal(sent.filter(r=>r.body?.kind==='onset').length,0);
 console.log('Editor onset, typo/backspace correction, word commit and paste exclusion checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
