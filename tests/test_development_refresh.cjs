const fs=require('fs'),vm=require('vm'),assert=require('assert');
async function run({step='activity',running=false,dialog=false,focus='',css=false,enabled=true}={}){
 let tick,reloads=0,applies=0;const messages=[];
 const context={setInterval:f=>tick=f,setTimeout:f=>f(),URL,Date,console,window:{museNative:true},state:{typing:{running}},document:{body:{classList:{contains:()=>false},dataset:{journeyStep:step}},querySelector:()=>dialog,activeElement:{tagName:focus},querySelectorAll:()=>[]},location:{reload:()=>reloads++},toast:t=>messages.push(t),rawApi:async p=>p.endsWith('status')?{enabled,changed:true,settled:true,revision:1,busy:false}: (applies++,{ready:true,restart:!css})};
 vm.runInNewContext(fs.readFileSync('web/development.js','utf8'),context);await tick();return {applies,reloads};
}
(async()=>{
 for(const opts of [{step:'run'},{step:'setup'},{running:true},{dialog:true},{focus:'INPUT'},{enabled:false}])assert.deepEqual(await run(opts),{applies:0,reloads:0});
 assert.deepEqual(await run(),{applies:1,reloads:1});assert.deepEqual(await run({css:true}),{applies:1,reloads:0});console.log('Development refresh UI guards passed');
})().catch(e=>{console.error(e);process.exit(1)});
