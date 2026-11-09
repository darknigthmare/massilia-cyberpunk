'use strict';
// Bind each current browser result to both real pages and all actual producers.
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../../..');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const canonical=value=>JSON.stringify(value,(key,item)=>item&&!Array.isArray(item)&&typeof item==='object'?Object.fromEntries(Object.keys(item).sort().map(name=>[name,item[name]])):item);
const currentPages=Object.freeze(['game/SOMA_MASSILIA_URBAIN_v0_77.html','game/metropole-viewer-v77.html']);
const parentPages=Object.freeze({
 'game/SOMA_MASSILIA_URBAIN_v0_76.html':'f3fd9d42c17db7835e95a33034ca25a442c7e3909121877795004142acf6d97a',
 'game/metropole-viewer-v76.html':'68b4eb3ae26a895a94d69b12da2577ee2074b18fc134f31914b638a79530557b',
});
function producerFiles(inputs){const files={};function visit(value){if(!value||typeof value!=='object'||Array.isArray(value))return;for(const[key,item]of Object.entries(value)){
 if(key==='reusedWorldManifest')files['game/data/v69/world/manifest.json']=item;
 else if(item&&!Array.isArray(item)&&typeof item==='object'&&typeof item.sha256==='string'&&Number.isInteger(item.bytes)){
  if(key.startsWith('/')||key.split('/').includes('..')||!key.includes('.'))throw Error('Invalid producer path: '+key);
  const name='game/'+key;if(files[name]&&canonical(files[name])!==canonical(item))throw Error('Conflicting producer evidence: '+name);files[name]=item;
 }else visit(item);
}}visit(inputs);return files;}
function validateBuildEvidence(report,sources,html,actualInputs,sizes){
 if(report.version!=='0.77.0'||report.output!==path.basename(html)||report.sha256!==sources[html]||report.bytes!==sizes[html])throw Error('Built page/report mismatch: '+html);
 const inputs=report.inputs;if(!inputs?.sources77||!Array.isArray(inputs.modules77)||!inputs.modules77.length||new Set(inputs.modules77).size!==inputs.modules77.length||inputs.modules77.some(name=>!inputs.sources77['src/v77/'+name+'.js']))throw Error('Missing actual77 module inventory');
 for(const[name,item]of Object.entries(producerFiles(inputs)))if(sources[name]!==item.sha256||sizes[name]!==item.bytes)throw Error('Stale producer: '+name);
 if(canonical(inputs)!==canonical(actualInputs))throw Error('Current builder input inventory differs from report');
}
async function sourceEvidence(script){
 const actual=JSON.parse(execFileSync('python3',['-B','-S','-c','import json,sys;sys.path.insert(0,"game");import build_v77;print(json.dumps(build_v77.inputs(),sort_keys=True))'],{cwd:root,encoding:'utf8',maxBuffer:8*1024*1024,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}}));
 const files=new Set([...currentPages,...Object.keys(parentPages),...Object.keys(producerFiles(actual)),'lancer.py','game/data/v77/BUILD_REPORT.json','game/data/v77/VIEWER_BUILD_REPORT.json',path.relative(root,script),'game/tests/v77/browser_provenance.cjs']);
 const sources={},sizes={};for(const name of[...files].sort()){const bytes=await fs.readFile(path.join(root,name));sources[name]=hash(bytes);sizes[name]=bytes.length;}
 for(const[name,expected]of Object.entries(parentPages))if(sources[name]!==expected)throw Error('Frozen parent page changed: '+name);
 const artifacts=[];for(const[reportName,html]of[['BUILD_REPORT.json',currentPages[0]],['VIEWER_BUILD_REPORT.json',currentPages[1]]]){
  const filename='game/data/v77/'+reportName,report=JSON.parse(await fs.readFile(path.join(root,filename),'utf8'));validateBuildEvidence(report,sources,html,actual,sizes);artifacts.push({html,bytes:report.bytes,sha256:report.sha256,report:filename,actualProducerInputsSHA256:hash(canonical(actual))});
 }
 return{recordedAt:new Date().toISOString(),gitHEAD:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),script:path.relative(root,script),sources,sizes,aggregateSHA256:hash(canonical({sources,sizes})),artifacts,modules77:actual.modules77,scope:'Both actual77 HTML/reports, complete real builder input inventory including nested producers, immutable76 pages, current launcher, executing script and helper.'};
}
async function finishEvidence(report,script){try{report.provenanceFinished=await sourceEvidence(script);report.sourceSetUnchanged=report.provenance?.aggregateSHA256===report.provenanceFinished.aggregateSHA256;if(!report.sourceSetUnchanged)throw Error('Sources changed during browser execution');}catch(error){report.passed=false;report.sourceSetUnchanged=false;report.provenanceFailure=String(error.stack||error);process.exitCode=1;}}
module.exports={sourceEvidence,finishEvidence,producerFiles,validateBuildEvidence,currentPages,parentPages,canonical,hash};
