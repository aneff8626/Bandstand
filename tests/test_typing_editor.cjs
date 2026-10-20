const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els={},sent=[];
function el(id){return els[id]??=( {value:'',selectionStart:0,selectionEnd:0,dataset:{},replaceChildren(){},classList:{toggle(){},remove(){}},setAttribute(k,v){this[k]=v},handlers:{},addEventListener(k,v){this.handlers[k]=v},closest(){return this},focus(){},setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b}})}
const context={console,$:el,api:async(path,body)=>{sent.push({path,body});return {}},toast:()=>{},now:()=>100,crypto:{randomUUID:()=>String(sent.length)+'-word'},state:{typing:{running:true}},active:false,show:()=>{},setMode:()=>{},mode:'erp',document:{body:{classList:{toggle(){}}},querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},setTimeout:()=>1,clearTimeout:()=>{},Promise};
vm.createContext(context);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../web/inference-feed.js'),'utf8'),context);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../web/typing.js'),'utf8'),context);
const editor=el('writingEditor');function input(type,data,next){editor.selectionStart=editor.selectionEnd=editor.value.length;editor.handlers.beforeinput({target:editor,inputType:type,data,isComposing:false});editor.value=next;editor.handlers.input({target:editor})}
(async()=>{
 for(const c of 'hellp')input('insertText',c,editor.value+c);
 input('deleteContentBackward',null,'hell');input('insertText','o','hello');input('insertText',' ','hello ');
 await vm.runInContext('typingChain',context);
 const onset=sent.filter(r=>r.body?.kind==='onset'),commit=sent.filter(r=>r.body?.kind==='commit');assert.equal(onset.length,1);assert.equal(commit.length,1);assert.equal(commit[0].body.text,'hello');assert.equal(commit[0].body.edited,true);assert.equal(commit[0].body.unsupported,false);
 sent.length=0;input('insertFromPaste','pasted text ','hello pasted text ');await vm.runInContext('typingChain',context);assert.equal(sent.filter(r=>r.body?.kind==='onset').length,0);
 context.state.typing.running=false;vm.runInContext("chooseTypingMode('editor')",context);assert.equal(el('writingEditor').hidden,false);assert.equal(el('typingCheckAccess').hidden,true);assert.equal(el('typingModeEditor')['aria-pressed'],'true');
 context.state.typing={running:true,session:{capture:'editor'}};vm.runInContext("chooseTypingMode('system');updateTypingMode()",context);assert.equal(el('typingCapture').value,'editor');assert.equal(el('typingModeSystem').disabled,true);
 context.state.typing.session.capture='system';vm.runInContext('updateTypingMode()',context);assert.equal(el('writingEditor').hidden,true);sent.length=0;input('insertText','x',editor.value+'x');await vm.runInContext('typingChain',context);assert.equal(sent.length,0);
 // Direct mode buttons start once, clear only the new editor, and roll back failed native capture.
 context.personalBusy=false;context.syncClock=async()=>{};
 // Exercise the real renderer: a display exception previously disabled Bluetooth on every poll.
 context.performance={now:()=>1000};context.redactPhrase=x=>x;
 vm.runInContext('renderLearningCurve=()=>{}',context);
 context.state={source:'live',stale:false,typing:{running:false,total:0}};
 vm.runInContext('renderTyping()',context);
 context.state.typing={running:true,session:{capture:'system',started:Date.now()/1000},total:2,capture_preview:{text:'test phrase',app:'Test editor',at:Date.now()/1000}};
 vm.runInContext('renderTyping()',context);
 assert.match(el('typingStartFeedback').textContent,/Recording/);assert.match(el('typingCapturePreview').textContent,/test phrase.*Test editor/);
 context.state.typing={running:false,total:2};vm.runInContext('renderTyping()',context);
 assert.match(el('typingStartFeedback').textContent,/Recording saved/);assert.equal(el('typingModeSystem').disabled,false);

 vm.runInContext('renderTyping=()=>updateTypingMode()',context);
 context.state.typing={running:false};editor.value='previous session text';
 context.api=async(path,body)=>{sent.push({path,body});if(path==='typing/start')return {running:true,session:{capture:body.capture}};if(path==='typing/stop')return {running:false};return {}};
 sent.length=0;await Promise.all([el('typingModeEditor').onclick(),el('typingModeEditor').onclick()]);
 assert.equal(sent.filter(x=>x.path==='typing/start').length,1);assert.equal(editor.value,'');assert.equal(context.state.typing.running,true);assert.equal(el('typingModeEditor').textContent,'● Recording in Bandstand');assert(!sent.some(x=>x.path==='system_typing/start'));
 context.state.typing={running:false};context.window.museNative=true;
 context.api=async(path,body)=>{sent.push({path,body});if(path==='system_typing/status')return {available:true};if(path==='typing/start')return {running:true,session:{capture:body.capture}};if(path==='system_typing/start')return {active:false,reason:'Capture unavailable'};if(path==='typing/stop')return {running:false};return {}};
 await el('typingModeSystem').onclick();assert.equal(context.state.typing.running,false);assert.equal(el('typingStartFeedback').textContent,'Capture unavailable');assert.equal(el('typingModeSystem').disabled,false);
 assert(!sent.some(x=>x.path==='typing/document'));
 console.log('Direct-start, blank editor, duplicate-click and native rollback checks passed');
 console.log('Editor onset, typo/backspace correction, word commit and paste exclusion checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
