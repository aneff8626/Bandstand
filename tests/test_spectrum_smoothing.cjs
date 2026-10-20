const fs=require('fs'),vm=require('vm'),assert=require('assert');const source=fs.readFileSync('web/journey.js','utf8');const c={performance:{now:()=>0},$:()=>({getAttribute:()=> 'false'}),boot:{channels:['TP9']},hiddenTraceChannels:new Set()};vm.createContext(c);vm.runInContext(source.slice(source.indexOf('const fixedSpectrumAxes='),source.indexOf('// Browser history')),c);
const data=v=>({channels:[{psd:[v],bands:[v]},null]});
assert.equal(c.smoothSpectrum(data(0),'8',0).channels[0].psd[0],0);
const target=data(10),out=c.smoothSpectrum(target,'8',500);assert(Math.abs(out.channels[0].psd[0]-6.3212)<.001);assert.equal(target.channels[0].psd[0],10);assert.equal(out.channels[1],null);
assert.equal(c.smoothSpectrum(data(20),'4',510).channels[0].psd[0],20);assert.equal(c.smoothSpectrum(null,'4',520),null);assert.equal(c.smoothSpectrum(data(3),'4',530).channels[0].psd[0],3);
console.log('Smoothing response, unmodified inputs, window reset and stale clearing passed');
let clock=0;c.performance.now=()=>clock;const initial=c.psdMaximum({frequencies:[10],channels:[{psd:[10]}]});clock=500;const rising=c.psdMaximum({frequencies:[10],channels:[{psd:[100]}]});assert.equal(rising,initial);clock=1000;const falling=c.psdMaximum({frequencies:[10],channels:[{psd:[2]}]});assert.equal(falling,initial);console.log('Shared PSD scale stays fixed as power rises and falls');

c.smoothSpectrum(null,"8",2000);assert.equal(c.psdMaximum({frequencies:[10],channels:[{psd:[200]}]}),initial);console.log("Scale survives signal interruption");
