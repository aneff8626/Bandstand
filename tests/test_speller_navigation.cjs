const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/../web/journey.js','utf8');
const calls=[];const c={chosenActivityTitle:'P300 speller',spellerRunning:false,prepareSpeller:()=>calls.push('setup'),startSpeller:async()=>calls.push('speller'),beginRun:async()=>{throw Error('Wrong oddball route')},toast:t=>calls.push(t)};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf('async function journeyGo'),source.indexOf('// Step buttons')),c);
(async()=>{await c.journeyGo('run');assert.deepEqual(calls,['setup','speller']);calls.length=0;await c.journeyGo('setup');assert.deepEqual(calls,['setup']);c.spellerRunning=true;calls.length=0;await c.journeyGo('summary');assert.equal(calls.length,1);assert.match(calls[0],/End & save/);console.log('Speller Results → Run and Setup keep the selected task; recording cannot be abandoned.');})().catch(e=>{console.error(e);process.exitCode=1});
