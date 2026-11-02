'use strict';
// CPU audit only: authored topology paths do not certify physical traversal.
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=require('./missions-fixture.cjs');
async function main(){
 const output=path.resolve(process.argv[2]||'/workspace/massilia-geodata-generated/validation-v76-2026-11-02/missions');await fs.mkdir(output,{recursive:true});
 const c={C:{hex:x=>x},localStorage:{getItem:()=>null},setTimeout:()=>{},document:{readyState:'complete'},Math,Object,Map,Set,Date,performance:{now:()=>0}};c.window=c;vm.createContext(c);
 vm.runInContext(source.worldData+'\n'+source.nightWorld+'\n'+source.authoredWorld+'\nvar WORLD=makeWorld();var D=Object.fromEntries(DISTRICTS.map(d=>[d.id,d]));var NARRATIVE={readables:{}};'+source.annexWorld,c);
 c.state={zone:'station-interiorA',health:100,reputation:{}},c.zone=c.WORLD.zones[c.state.zone];
 vm.runInContext(source.production.replace('v43Setup();','window.defs={stories:V43_STORY,gigs:V43_GIGS,hotspots:V43_HOTSPOTS};'),c);
 vm.runInContext(source.city.replace('v45Setup();','window.route=v45FindRoute;'),c);
 const native=c.__SOMA_MISSIONS76__.snapshot(),routes=[];
 for(const m of c.defs.stories){let from='station-interiorA';for(const [index,s]of m.steps.entries()){const p=c.route(from,s.zone);assert(p.length,m.id+' approach '+index);routes.push({kind:'story',id:m.id,index,kindOfStage:s.kind,from,zone:s.zone,path:p});from=s.zone;}const p=c.route(from,'station-interiorA');assert(p.length);routes.push({kind:'story-return',id:m.id,from,zone:'station-interiorA',path:p});}
 for(const g of c.defs.gigs){const board=Object.values(c.WORLD.zones).find(z=>z.district===g.district&&z.type==='social');for(const [kind,from,to]of [['gig',board.id,g.zone],['gig-return',g.zone,board.id]]){const p=c.route(from,to);assert(p.length,g.id+' '+kind);routes.push({kind,id:g.id,from,zone:to,path:p});}}
 const exact=native.encounters.flatMap(e=>e.enemies.map(q=>({...q,zone:e.zone,owner:e.owner,boss:e.boss,kind:e.kind,quest:e.id}))),hotspots=c.defs.hotspots.flatMap(h=>Array.from({length:h.count},(_,index)=>({id:`v43-hotspot-${h.id}-${index}`,zone:h.zone})));
 for(const q of exact){assert(c.__SOMA_MISSIONS76__.knownEnemy(q.id,q.zone));assert(!c.__SOMA_MISSIONS76__.knownEnemy(q.id,'invented'));}
 for(const q of hotspots){assert(c.__SOMA_MISSIONS75__.knownHotspotEnemy(q.id,q.zone));assert(!c.__SOMA_MISSIONS76__.knownEnemy(q.id,q.zone));}
 assert.equal(exact.length,55);assert.equal(hotspots.length,31);assert.equal(routes.filter(r=>['story','gig'].includes(r.kind)).length,34);
 const files=['game/tools/v76_missions.py','game/src/v76/missions-runtime.js','game/tests/v76/missions.test.cjs','game/tests/v76/missions-fixture.cjs','game/tests/v76/missions-source-audit.cjs','game/SOMA_MASSILIA_URBAIN_v0_75.html'];const sources={};
 for(const f of files)sources[f]=crypto.createHash('sha256').update(await fs.readFile(path.resolve(__dirname,'../../..',f))).digest('hex');
 const report={schema:'soma/production43-source-audit/76/1',passed:true,createdAt:new Date().toISOString(),sources,counts:{stories:6,storyStages:18,gigs:16,stagesAndGigs:34,locationReferencesRepaired:24,distinctLocationAliasesRepaired:23,encounters:19,newEnemies:55,storyEnemies:21,gigEnemies:34,bosses:1,unchangedHotspotEnemies:31,source43Enemies:86},locations:native.locationRepairs,exactNewEnemies:exact,unchangedHotspots:hotspots,routes,owner:'production43 + combat32 + persistence37/group64',newPersistenceDomain:false,limits:['CPU audit evaluates actual authored definitions and native45 topology paths without building scenes or certifying passage through them.','Representative native interaction, combat32 defeat and grouped/raw reload cases belong to the separate browser missions report.']};
 await fs.writeFile(path.join(output,'source43-cpu-audit.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify({passed:true,report:path.join(output,'source43-cpu-audit.json'),counts:report.counts})+'\n');
}
main().catch(error=>{process.stderr.write(String(error.stack||error)+'\n');process.exitCode=1;});
