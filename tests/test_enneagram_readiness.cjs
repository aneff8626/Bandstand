const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/personal.js','utf8'),start=source.indexOf('function enneagramReadiness('),end=source.indexOf('function drawEnneagramCircle',start),ctx=vm.createContext({});vm.runInContext(source.slice(start,end),ctx);
ctx.items=Array.from({length:108},(_,i)=>({domain:String(i%9),reverse:false}));ctx.answers=Array(108).fill(null);
assert.equal(vm.runInContext('enneagramReadiness(items,answers)',ctx),false);
ctx.answers=Array(54).fill(3).concat(Array(54).fill(null));assert.equal(vm.runInContext('enneagramReadiness(items,answers)',ctx),true);
ctx.answers=Array(36).fill(1).concat(Array(18).fill(5),Array(54).fill(null));assert.equal(vm.runInContext('enneagramReadiness(items,answers)',ctx),false);
console.log('Readiness requires coverage and stable dimension means; missing or unstable answers do not qualify.');
