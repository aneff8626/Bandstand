const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(require('path').join(__dirname,'../web/app.js'),'utf8');
const nodes={},timers=[],messages=[];
const c={console:{error(){}},$:id=>nodes[id]??={textContent:'',disabled:false,classList:{remove(){}},setAttribute(){}},state:null,active:true,runID:0,lastPanelRender:0,performance:{now:()=>200},setTimeout:fn=>timers.push(fn),show(){},toast:m=>messages.push(m),api:async()=>({status:{state:'streaming'}}),render(){c.$('connectMuse').textContent='Device connected, streaming';throw new Error('test rendering failure')}};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf("let lastDisplayError="),source.indexOf('\nfunction config()')),c);
(async()=>{
 await c.poll();assert.equal(c.$('connectMuse').textContent,'Device connected, streaming');assert.equal(c.active,true);assert.equal(timers.length,1);assert.match(messages[0],/Display update failed/);
 c.api=async()=>{throw new Error('offline')};await c.poll();assert.match(c.$('connectMuse').textContent,/retrying/);assert.equal(c.active,false);assert.equal(timers.length,2);
 c.api=async()=>({status:{state:'disconnected'}});c.render=()=>{c.$('connectMuse').textContent='Click to connect Bluetooth';c.$('connectMuse').disabled=false};await c.poll();assert.equal(c.$('connectMuse').disabled,false);assert.equal(timers.length,3);
 console.log('Display failures stay separate from service failures; polling and connection controls recover.');
})().catch(e=>{console.error(e);process.exitCode=1});
