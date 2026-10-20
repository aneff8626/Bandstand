const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/journey.js','utf8');
class Element {
 constructor(tag='div',id=''){this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.parent=null;this.dataset={};this.classList={add(){},contains(){return true}};}
 append(...nodes){for(const n of nodes){if(n.parent)n.parent.children.splice(n.parent.children.indexOf(n),1);n.parent=this;this.children.push(n)}}
 find(predicate){if(predicate(this))return this;for(const n of this.children){const found=n.find(predicate);if(found)return found}return null}
 querySelector(s){return this.find(n=>s[0]==='#'?n.id===s.slice(1):s==='summary'?n.tagName==='SUMMARY':s==='.brief-actions'?n.id==='actions':false)}
 replaceChildren(...nodes){for(const n of this.children)n.parent=null;this.children=[];this.append(...nodes)}
 setAttribute(){} addEventListener(){} get previousElementSibling(){return this.parent?.children[this.parent.children.indexOf(this)-1]}
}
const body=new Element(),setup=new Element(),brief=new Element('div','journeyBrief'),actions=new Element('div','actions'),task=new Element('p','briefTask'),row=new Element(),panel=new Element('details','advancedSettings');
body.append(setup,new Element('div','startupMessage'),new Element('div','startupScreen'));setup.append(brief,row,panel);brief.append(new Element('button'),task,actions);actions.append(new Element('button','briefAdvanced'),new Element('button','briefProtocol'));row.append(new Element('button','start'));panel.append(new Element('summary'));
const $=id=>body.find(n=>n.id===id),document={body,createElement:tag=>new Element(tag),querySelector:s=>s==='.setup .start-row'?row:null,querySelectorAll:()=>[]};
const ctx=vm.createContext({$,document,personalButton:()=>new Element('button'),location:{reload(){}},setTimeout:fn=>ctx.timer=fn});
const start=source.indexOf('function initLabSetupSequence()'),end=source.indexOf('\nasync function',start);vm.runInContext(source.slice(start,end),ctx);vm.runInContext('initLabSetupSequence()',ctx);
assert.equal($('briefProtocol').parent,panel);assert.equal($('advancedSettings'),panel);assert.equal(panel.open,false);
const problem=source.indexOf('function startupProblem('),problemEnd=source.indexOf('\nfunction spectrumGroups',problem);vm.runInContext(source.slice(problem,problemEnd),ctx);vm.runInContext('startupProblem("test failure")',ctx);ctx.timer();assert.equal($('startupMessage').textContent,'Startup could not finish: test failure');
console.log('Detached panel initialization and startup-error timer regression checks passed.');
