const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements={displayBandpass:{checked:true},displayLow:{value:1},displayHigh:{value:30}};
const ctx={$:id=>elements[id],Map,Set};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/workspace.js','utf8'),ctx);
const trace={times:Array.from({length:1024},(_,i)=>i/128),values:Array.from({length:1024},(_,i)=>[100+Math.sin(i/128*2*Math.PI*10),0,null,0])};
const filtered=ctx.displayTrace(trace);assert(Math.abs(filtered.values.at(-1)[0])<2);assert.equal(filtered.values.at(-1)[2],null);assert.deepEqual(ctx.displayTrace(trace),filtered);elements.displayBandpass.checked=false;assert.strictEqual(ctx.displayTrace(trace),trace);console.log('Display filter: DC rejection, missing data, overlapping packets and bypass passed');
