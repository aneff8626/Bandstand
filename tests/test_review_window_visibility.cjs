const fs=require('fs'),vm=require('vm'),assert=require('assert');
const workspace=fs.readFileSync(__dirname+'/../web/workspace.js','utf8');
const els={reviewWindow:{hidden:false},reviewStart:{},reviewEnd:{},reviewStatus:{}};
const c={$:id=>els[id],state:{session:{mode:'erp',protocol:'oddball',window:[.3,.5]}},document:{activeElement:null},clearTimeout:()=>{},reviewTimer:null,reviewRequest:0,previewReviewWindow:null,reviewChannel:null};
vm.createContext(c);vm.runInContext(workspace.slice(workspace.indexOf('function syncReviewWindow'),workspace.indexOf('async function updateReviewWindow')),c);
c.syncReviewWindow();assert.equal(els.reviewWindow.hidden,false);
for(const mode of ['tf','bio',undefined]){c.state.session={mode};c.syncReviewWindow();assert.equal(els.reviewWindow.hidden,true);}
c.state.session={mode:'erp',protocol:'speller'};c.syncReviewWindow();assert.equal(els.reviewWindow.hidden,true);
const app=fs.readFileSync(__dirname+'/../web/app.js','utf8');const fn=app.slice(app.indexOf('function drawChannelERPs(){'),app.indexOf('function drawChannelERPs(){')+1000);
assert(fn.indexOf('syncReviewWindow()')<fn.indexOf("mode==='tf'"),'Visibility must update before spectral early return');
console.log('ERP review controls are hidden for spectral, biofeedback and speller views.');
