const fs=require('fs'),vm=require('vm'),assert=require('assert');
const personal=fs.readFileSync('web/personal.js','utf8'),journey=fs.readFileSync('web/journey.js','utf8');
const context={};vm.createContext(context);
vm.runInContext(fs.readFileSync('web/mind-demo.js','utf8')+'\n'+personal.slice(personal.indexOf('function personalitySpectrumPrototypes('),personal.indexOf('function createRecordedSpectrum(')),context);
for(const kind of ['big5','enneagram']){const rows=context.personalitySpectrumPrototypes(kind);assert.equal(rows.length,kind==='big5'?5:9);for(const p of rows)for(const ref of p.references){assert.equal(ref.psd.length,4);assert.equal(ref.psd[0].length,79);assert(ref.psd.flat().every(Number.isFinite))}}
vm.runInContext(journey.slice(journey.indexOf('function sessionCompatibilityKey('),journey.indexOf('function renderSessionOverlay(')),context);
const base={recordType:'personal',kind:'big5',source:'live',questionnaire_version:'v1',plan:[['Questionnaire',1800]],summary:{spectra:{Questionnaire:{channels:[]}}}};
(async()=>{
 await assert.rejects(context.prepareCombinedSessions([base],'group'),/two sessions/);
 await assert.rejects(context.prepareCombinedSessions([base,{...base,kind:'enneagram'}],'group'),/same activity/);
 await assert.rejects(context.prepareCombinedSessions([base,{...base,source:'simulation'}],'group'),/same activity/);
 await assert.rejects(context.prepareCombinedSessions([base,{...base,questionnaire_version:'v2'}],'group'),/different protocols/);
 await assert.rejects(context.prepareCombinedSessions([base,base],'within'),/participant ID/);
 assert.equal((await context.prepareCombinedSessions([base,{...base,id:'second'}],'group')).length,2);
 const lab={recordType:'lab',kind:'p300',source:'live'},a={session:{protocol:'p300',mode:'erp',window:[.3,.5],conditions:['A','B'],channels:['TP9']},analysis:{}};
 assert.notEqual(context.sessionCompatibilityKey(lab,a),context.sessionCompatibilityKey(lab,{...a,session:{...a.session,window:[.4,.6]}}));
 console.log('Prototype shapes, matching sessions, source/version/window conflicts and participant checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
