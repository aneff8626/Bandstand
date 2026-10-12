const fs=require('fs'),vm=require('vm'),assert=require('assert');const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('web/inference-feed.js','utf8'),ctx);
const c=text=>({text,similarity:.4});
assert.equal(ctx.suggestedGist([c('technical problem with login'),c('another technical problem today')]),'technical problem');
assert.equal(ctx.suggestedGist([c('technical problem'),c('technical problem')]),'Meaning unclear');
assert.equal(ctx.suggestedGist([c('enjoying the garden'),c('fix the computer')]),'Meaning unclear');
assert.equal(ctx.suggestedGist([]),'Meaning unclear');
assert.equal(ctx.suggestedGist([c('I do not like this'),c('I do like this')]),'Meaning unclear');
console.log('Gist consensus, duplicate rejection, disagreement and empty-input checks passed');
