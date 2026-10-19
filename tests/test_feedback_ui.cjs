const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync('web/personal.js','utf8'),journey=fs.readFileSync('web/journey.js','utf8');
function extract(source,name){const start=source.indexOf('function '+name+'(');let end=source.indexOf('\nfunction ',start+1);if(end<0)end=source.indexOf('\nwindow.addEventListener',start);return source.slice(start,end<0?undefined:end)}
const ctx=vm.createContext({console,Math,Number,Boolean,Date});vm.runInContext(extract(code,'sampleSpread')+extract(code,'trainingFeedback'),ctx);
assert.equal(vm.runInContext('sampleSpread([3])',ctx),null);assert.equal(vm.runInContext('sampleSpread([1,3,5])',ctx),2);
const make=(power,config={band:1,channels:['TP9','TP10'],direction:1})=>({feedback:config,phase:'Training',phase_elapsed:10,recent_clips:[{time:10,phase:'Training',power}],summary:{phases:{Baseline:{TP9:{n:10,db:[0,10,0,0],sd:[1,1,1,1]},TP10:{n:10,db:[0,10,0,0],sd:[1,1,1,1]}}}}});
ctx.r=make({TP9:[0,13,0,0]});let result=vm.runInContext('trainingFeedback(r)',ctx);assert.equal(result.delta,3);assert.equal(result.level,.75);assert.equal(result.values.length,1);assert.equal(result.contactLost,false);
ctx.r=make({});assert.equal(vm.runInContext('trainingFeedback(r).contactLost',ctx),true);
ctx.r=make({TP9:[0,2,0,0]});assert.equal(vm.runInContext('trainingFeedback(r).deviant',ctx),true);
ctx.r=make({TP9:[0,2,0,0]},{band:1,channels:['TP9'],direction:-1});assert.equal(vm.runInContext('trainingFeedback(r).deviant',ctx),false);
ctx.r=make({TP9:[0,13,0,0]});ctx.r.summary.phases.Baseline.TP9.n=1;assert.equal(vm.runInContext('trainingFeedback(r).contactLost',ctx),false);
// Repeated sessions of one participant must have one summary, not extra participant weight.
vm.runInContext('async '+extract(journey,'combinedSessionMetrics'),ctx);
ctx.records=[{id:'a',recordType:'personal',subject:'P1',title:'Big Five',source:'simulation',scores:{Trait:1}},{id:'b',recordType:'personal',subject:'P1',title:'Big Five',source:'simulation',scores:{Trait:5}},{id:'c',recordType:'personal',subject:'P2',title:'Big Five',source:'simulation',scores:{Trait:4}}];
(async()=>{const metrics=await vm.runInContext('combinedSessionMetrics(records)',ctx);assert.deepEqual(Array.from(Object.values(metrics)[0]),[3,4]);console.log('Personality variability, linear feedback, channel fallback, artifact and participant grouping checks passed.');})();
// Sustained cues count new clean/noisy clips, never repeated one-second polls.
const nodes={personalOrb:{classList:{remove(){}},style:{}},personalFeedback:{}};
ctx.$=id=>nodes[id];ctx.ensureFeedbackAudio=()=>{};ctx.feedbackSound=null;ctx.feedbackState={};ctx.cues=[];ctx.feedbackCue=type=>ctx.cues.push(type);
vm.runInContext(extract(code,'updateTrainingFeedback'),ctx);
ctx.r=make({TP9:[0,2,0,0]});vm.runInContext('updateTrainingFeedback(r);updateTrainingFeedback(r)',ctx);assert.equal(ctx.cues.length,0);
ctx.r.recent_clips[0].time=12;vm.runInContext('updateTrainingFeedback(r)',ctx);assert.deepEqual(ctx.cues,['gong']);
ctx.feedbackState={};ctx.cues=[];ctx.r=make({});for(const time of [20,22,24,26]){ctx.r.recent_clips[0].time=time;vm.runInContext('updateTrainingFeedback(r)',ctx)}assert.deepEqual(ctx.cues,['contact']);
ctx.feedbackState={};ctx.cues=[];ctx.r=make({TP9:[0,13,0,0]});for(const time of [30,32,34,36,38]){ctx.r.recent_clips[0].time=time;vm.runInContext('updateTrainingFeedback(r)',ctx)}assert.equal(ctx.cues.length,0);
ctx.r.server_time=50;assert.equal(vm.runInContext('trainingFeedback(r).delta',ctx),null);
console.log('Cue duration, repeat-poll suppression, valid-channel fallback and stale-signal checks passed.');
