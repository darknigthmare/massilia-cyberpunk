'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {validateBuildEvidence,producerFiles}=require('./browser_provenance.cjs');
const html='game/SOMA_MASSILIA_URBAIN_v0_78.html',moduleName='src/v78/example.js',sha='a'.repeat(64),parent='b'.repeat(64);
function fixture(){const input={sources78:{[moduleName]:{bytes:9,sha256:sha}},modules78:['example'],nested:{sources77:{'build_v77.py':{bytes:8,sha256:parent}}}};return{input,sources:{[html]:sha,['game/'+moduleName]:sha,'game/build_v77.py':parent},sizes:{[html]:15,['game/'+moduleName]:9,'game/build_v77.py':8},report:{version:'0.78.0',output:'SOMA_MASSILIA_URBAIN_v0_78.html',sha256:sha,bytes:15,inputs:input}};}
test('current evidence includes nested inherited producer',()=>{const f=fixture();validateBuildEvidence(f.report,f.sources,html,f.input,f.sizes);assert.equal(producerFiles(f.input)['game/build_v77.py'].sha256,parent);});
test('tampered HTML bytes reject a matching hash field',()=>{const f=fixture();f.sizes[html]++;assert.throws(()=>validateBuildEvidence(f.report,f.sources,html,f.input,f.sizes),/mismatch/);});
test('stale nested producer rejects report even with unchanged current module',()=>{const f=fixture();f.sources['game/build_v77.py']='c'.repeat(64);assert.throws(()=>validateBuildEvidence(f.report,f.sources,html,f.input,f.sizes),/Stale producer/);});
test('missing newly introduced current input is rejected',()=>{const f=fixture();const current=structuredClone(f.input);current.newFlag=true;assert.throws(()=>validateBuildEvidence(f.report,f.sources,html,current,f.sizes),/inventory differs/);});
test('duplicate module inventory is rejected',()=>{const f=fixture();f.input.modules78.push('example');assert.throws(()=>validateBuildEvidence(f.report,f.sources,html,f.input,f.sizes),/module inventory/);});
test('producer path escaping checkout is rejected',()=>{assert.throws(()=>producerFiles({'../outside.py':{bytes:1,sha256:sha}}),/Invalid producer path/);});
