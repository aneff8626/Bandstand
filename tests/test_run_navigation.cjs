const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/journey.js','utf8');
function fn(name){const start=source.indexOf('async function '+name+'(');const end=source.indexOf('\nfunction ',start+1);return source.slice(start,end)}
(async()=>{
 const events=[],state={typing:{running:true}};let release;
 const c=vm.createContext({state,journeyLeavingTyping:false,journeyRun:true,stopTyping:()=>new Promise(resolve=>{release=()=>{events.push('saved');state.typing.running=false;resolve()}}),journeySetStep:step=>events.push(step),journeyGo:step=>events.push('go:'+step),toast:text=>events.push(text),Error});
 vm.runInContext(fn('leaveTypingRun'),c);
 const pending=vm.runInContext("leaveTypingRun('headset',true)",c);assert.deepEqual(events,[]);assert.equal(c.journeyLeavingTyping,true);release();await pending;assert.deepEqual(events,['saved','go:headset']);assert.equal(c.journeyRun,false);assert.equal(c.journeyLeavingTyping,false);
 events.length=0;state.typing.running=true;c.stopTyping=async()=>{throw Error('network failure')};await vm.runInContext("leaveTypingRun('choose',true)",c);assert.equal(events.at(-1),'run');assert.equal(state.typing.running,true);
 assert(!source.includes("preflightSection.prepend(personalButton('Click for instructions'"));
 assert(source.includes("if(step!=='run'&&state?.typing?.running)"));
 console.log('Writing stops and saves before navigation; failures retain Run; obsolete preflight gate removed.');
})();
