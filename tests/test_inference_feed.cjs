const fs=require('fs'),vm=require('vm'),assert=require('assert');const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../web/inference-feed.js'),'utf8'),ctx);
const p=(text,score,time)=>({generated_at:time,candidates:[{text,similarity:score}],validated:false});
let f=ctx.createInferenceFeed();assert.equal(f.update(p('first phrase',.5,1),0).current.text,'first phrase');
assert.equal(f.update(p('stronger second phrase',.8,2),1000).current.text,'first phrase');
let state=f.update(null,4500);assert.equal(state.current.text,'stronger second phrase');assert.equal(state.previous[0].text,'first phrase');
f.update(p('third',.3,3),5000);assert.equal(f.update(null,8600).current.text,'stronger second phrase');assert.equal(f.update(null,14000).current.text,'third');
f.setMode('all');state=f.update(p('fourth',.6,4),15000);assert.equal(state.current.text,'third');state=f.update(null,19000);assert.equal(state.current.text,'fourth');assert.ok(state.previous.length>=3);
console.log('Read-time hold, stronger-match promotion, five-second grace, history and mode checks passed');
