import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {openNativeBrowser} from './native_browser.mjs';

const url=process.argv[2];
if(!url)throw Error('Pass the hosted game URL');
const out=resolve('hosting/.reports');
await mkdir(out,{recursive:true});
const b=await openNativeBrowser(url,{webgl:true,width:1280,height:720,timeout:180000});
const checks=[];
async function click(selector){
 const point=await b.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||e.disabled)throw Error('Missing native control');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();if(r.width<5||r.height<5)throw Error('Hidden native control');return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);
 await b.call('Page.bringToFront');
 for(const type of ['mousePressed','mouseReleased'])await b.call('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1});
}
async function key(code,value,virtual,type='keyDown',modifiers=0){await b.call('Input.dispatchKeyEvent',{type,code,key:value,windowsVirtualKeyCode:virtual,modifiers});}
async function tap(code,value,virtual){await key(code,value,virtual);await key(code,value,virtual,'keyUp');}
async function state(){return b.evaluate(`({title:document.title,version:window.__SOMA_V78__?.version,ready:window.__SOMA_V78__?.ready,zone:typeof zone==='object'?zone?.id:null,geographicDistrict:typeof zone==='object'?!!zone?.v52District:false,paused:typeof paused==='boolean'?paused:null,position:typeof camera==='object'?{x:camera.x,y:camera.y,z:camera.z}:null,selectedPlace:document.querySelector('#v62-details h3')?.textContent||null,panels:[...document.querySelectorAll('.modal.open,.modal.active')].filter(e=>e.getBoundingClientRect().width).map(e=>e.id)})`);}
try{
 await b.waitFor("window.__SOMA_V78__?.ready && !!document.getElementById('v54-explore')",180000);
 const identity=await state();assert.equal(identity.version,'0.78.0');checks.push('Native v0.78 starts');
 await click('#v54-explore');
 await b.waitFor("typeof zone==='object' && zone?.v52District && !paused",120000);
 const before=(await state()).position;let after=before;
 for(const [code,value,vk] of [['KeyW','w',87],['KeyD','d',68],['KeyS','s',83]]){
  await key(code,value,vk);await b.sleep(900);await key(code,value,vk,'keyUp');await b.sleep(250);after=(await state()).position;
  if(Math.hypot(after.x-before.x,after.z-before.z)>=0.05)break;
 }
 assert.ok(Math.hypot(after.x-before.x,after.z-before.z)>=0.05);checks.push('Native keyboard movement changes position in provided centre');
 await writeFile(resolve(out,'street.png'),await b.capture());
 await key('ShiftLeft','Shift',16,'keyDown',8);await key('F1','F1',112,'keyDown',8);await key('F1','F1',112,'keyUp',8);await key('ShiftLeft','Shift',16,'keyUp');
 await b.waitFor("document.getElementById('v70-tactics')?.classList.contains('open')");checks.push('Cortex opens with native shortcut');
 await click('[data-v70-close]');await b.waitFor("!document.getElementById('v70-tactics')?.classList.contains('open')");
 await tap('KeyM','m',77);await b.waitFor("document.getElementById('exploration62')?.classList.contains('open')");checks.push('Native cartography opens');
 await click('#v62-list button.v62-place');await b.waitFor("!!document.querySelector('#v62-details h3')");checks.push('Discovered-place detail opens');
 const final=await state();await writeFile(resolve(out,'cartography.png'),await b.capture());
 const data=await b.evaluate(`(async()=>{
  const root=new URL('./',location.href);const r=await fetch(new URL('release.json',root),{cache:'no-cache'});if(!r.ok)throw Error('Missing web release');const release=await r.json();
  const mr=await fetch(new URL('data/v69/world/manifest.json',root),{cache:'no-cache'});if(!mr.ok)throw Error('Missing world manifest');const manifest=await mr.json();const samples=[];
  for(const tile of [manifest.tiles[0],manifest.tiles[manifest.tiles.length-1]])for(const role of ['vector','terrain','navigation','surfaces']){
   const asset=tile[role];if(!asset?.path)continue;const response=await fetch(new URL('data/v69/world/'+asset.path,root));if(!response.ok)throw Error('Missing tile '+asset.path);const bytes=new Uint8Array(await response.arrayBuffer());
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');if(digest!==asset.sha256)throw Error('Tile bytes altered '+asset.path);
   if(bytes[0]!==31||bytes[1]!==139)throw Error('Gzip payload transformed by host');const json=JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
   samples.push({path:asset.path,role,status:response.status,sha256:digest,jsonKeys:Object.keys(json).length});
  }
  return {version:release.version,sourceCommit:release.sourceCommit,htmlSha256:release.htmlSha256,providedCells:manifest.tiles.length,completeMetropole:manifest.completeMetropole,samples};
 })()`);
 assert.equal(data.version,'0.78.0');assert.equal(data.providedCells,168);assert.equal(data.completeMetropole,false);assert.equal(data.samples.length,8);checks.push('Manifest and eight original gzip cell assets load and decode with matching SHA');
 const report={verifiedAt:new Date().toISOString(),url,checks,passed:true,browser:{title:identity.title,playable:true,version:identity.version},movement:{before,after},final,data,limitations:['Provided 168-cell centre only; optional full metropolitan cache is absent.','Short native movement and menu smoke, not a complete campaign or performance certification.']};
 await writeFile(resolve(out,'browser-smoke.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
}finally{await b.close();}
