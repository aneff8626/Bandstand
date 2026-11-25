const fs=require('fs'),vm=require('vm'),assert=require('assert');
// Flash order and target placement, from web/cursor.js.
const cursor=fs.readFileSync(__dirname+'/../web/cursor.js','utf8');
const c={};vm.createContext(c);vm.runInContext(cursor.slice(0,cursor.indexOf('function cursorScore'))+';this.order=cursorFlashOrder;this.target=cursorTarget;',c);
let seed=7;const random=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
for(let trial=0;trial<200;trial++){
 const order=c.order(10,random);assert.equal(order.length,40);
 for(let r=0;r<10;r++)assert.deepEqual([...order.slice(4*r,4*r+4)].sort(),[0,1,2,3]);
 for(let i=1;i<order.length;i++)assert.notEqual(order[i],order[i-1],'an arrow flashed twice in a row');
 const from=[Math.floor(random()*7),Math.floor(random()*7)],to=c.target(from,random),d=Math.abs(to[0]-from[0])+Math.abs(to[1]-from[1]);
 assert.ok(d>=3&&d<=5,`target ${to} is ${d} moves from ${from}`);assert.ok(to.every(v=>v>=0&&v<7));
}
// Results → Run and Setup keep the selected cursor task; a running task cannot be abandoned.
const journey=fs.readFileSync(__dirname+'/../web/journey.js','utf8');
const calls=[];const j={chosenActivityTitle:'P300 direction cursor',spellerRunning:false,cursorRunning:false,prepareSpeller:()=>calls.push('speller setup'),startSpeller:async()=>calls.push('speller'),prepareCursor:()=>calls.push('setup'),startCursor:async()=>calls.push('cursor'),beginRun:async()=>{throw Error('Wrong oddball route')},toast:t=>calls.push(t)};
vm.createContext(j);vm.runInContext(journey.slice(journey.indexOf('async function journeyGo'),journey.indexOf('// Step buttons')),j);
(async()=>{await j.journeyGo('run');assert.deepEqual(calls,['setup','cursor']);calls.length=0;await j.journeyGo('setup');assert.deepEqual(calls,['setup']);j.cursorRunning=true;calls.length=0;await j.journeyGo('summary');assert.equal(calls.length,1);assert.match(calls[0],/End & save/);console.log('Cursor flash order is balanced with no repeats, targets are 3–5 moves away, and Run/Setup keep the cursor task.');})().catch(e=>{console.error(e);process.exit(1)});
