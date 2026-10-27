const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/../web/point-stats.js','utf8'),drawn=[];
const points=[{x:0,ready:true,significant:true},{x:4,ready:true,significant:true},{x:8,ready:true,significant:false},{x:12,ready:true,significant:true}];
const c={graphStatsData:{points:{session:'s',mode:'erp',channels:{AF7:{points}}}},graphStatsEnabled:()=>true,pointStatsSession:()=>({id:'s'})};vm.createContext(c);vm.runInContext(src.slice(src.indexOf('function significantRuns'),src.indexOf('function pointStatsMapOverlay')),c);
c.pointStatsOverlay('erp-AF7',{ctx:{save(){},restore(){},fillRect(...v){drawn.push(v)}},x:v=>50+v*1000,box:{l:45,r:900,t:22,b:300}});
assert.deepStrictEqual(drawn,[[48,24,8,4],[60,24,4,4]]);assert.equal(c.significantRuns([{x:0,ready:false,significant:true}]).length,0);
assert(src.includes("low:domain==='points'?(session.mode==='tf'?2:-200):low"));
console.log('Significance bars merge adjacent samples, preserve nonsignificant gaps, and use the top of the plot.');
