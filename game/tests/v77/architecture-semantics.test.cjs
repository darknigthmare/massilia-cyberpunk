'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const game=path.resolve(__dirname,'../..'),K=require('../../src/v77/architecture-semantics-core.js');
const raw=fs.readFileSync(path.join(game,'data/v76/architecture-conflicts.json')),parent=JSON.parse(raw);
const data=JSON.parse(fs.readFileSync(path.join(game,'data/v77/architecture-semantics.json'))),model=K.create(data),clone=x=>JSON.parse(JSON.stringify(x));
test('all77 new raw field rows bind exactly to the preserved parent reference and geometry',()=>{
 assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),data.provenance.parentCatalogueSHA256);
 assert.equal(data.provenance.ignSourceSHA256,parent.provenance.ignSourceSHA256);
 assert.equal(data.provenance.ignReceiptSHA256,parent.provenance.ignReceiptSHA256);
 for(const row of parent.rows)assert.equal(model.compatible(row),true,row.id);
 assert.equal(model.compatible({...parent.rows[0],groundAltitude:999}),false);
 assert.equal(model.compatible({...parent.rows[0],geometrySHA256:'a'.repeat(64)}),false);
 assert.equal(model.compatible(null),false);assert.ok(Object.isFrozen(model.data.rows[0].fields));
});
test('a raw roof statistic stays distinct from the calculated reference with no geometry substitution',()=>{
 const d=model.describe('osm/way/69129984');
 assert.equal(d.calculatedReferenceNGF,46.1);assert.equal(d.row.fields.altitude_minimale_toit,46.2);
 assert.ok(Math.abs(d.minimumRoofMinusReferenceM-.1)<1e-9);assert.equal(d.geometryChanged,false);assert.equal(d.referenceChanged,false);
 assert.equal(parent.rows.find(r=>r.id===d.row.id).absoluteEaveNGF,46.1);
 assert.equal(model.describe('invented'),null);
 assert.equal(data.rows.filter(r=>r.fields.altitude_minimale_toit!==null).length,77);
 assert.equal(data.rows.filter(r=>r.fields.altitude_maximale_toit!==null).length,41);
 assert.equal(data.rows.filter(r=>r.fields.altitude_maximale_sol!==null).length,41);
 assert.equal(data.rows.filter(r=>Math.abs(model.describe(r.id).minimumRoofMinusReferenceM)>1e-9).length,39);
});
test('zero is unknown only for height; absent altitude and true zero NGF remain different',()=>{
 assert.equal(K.meaning('hauteur',0),'unknown-or-insignificant');
 for(const field of K.FIELDS.slice(1)){assert.equal(K.meaning(field,0),'present');assert.equal(K.meaning(field,null),'absent');}
 for(const value of [undefined,NaN,Infinity,'0',false,-1001,9001])assert.throws(()=>K.meaning('altitude_minimale_toit',value));
 assert.throws(()=>K.meaning('roof_ridge',23));
});
test('tampered schema, fields, identities and document provenance are rejected',()=>{
 for(const change of [d=>d.geometryChanged=true,d=>d.referenceChanged=true,d=>d.cohortChanged=true,d=>d.rows.pop(),d=>d.rows[1].id=d.rows[0].id,
  d=>d.rows[0].fields.hauteur=0,d=>d.rows[0].fields.altitude_minimale_sol=null,d=>delete d.rows[0].fields.altitude_minimale_toit,
  d=>d.rows[0].fields.extra=1,d=>d.provenance.document.sha256='a'.repeat(64),d=>d.provenance.document.url='https://example.com/fake.pdf']){
  const d=clone(data);change(d);assert.throws(()=>K.create(d));
 }
});
function runtime(source=data){
 const c={JSON,Number,Math,Object,Array,Set,Map};c.window=c;c.__SOMA_ARCHITECTURE77_CORE__=K;c.__SOMA_ARCHITECTURE77_DATA__=clone(source);
 Object.defineProperty(c,'localStorage',{get(){throw Error('Read-only inspector accessed persistence');}});
 vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(game,'src/v77/architecture-semantics-runtime.js'),'utf8'),c);
 return {c,api:c.__SOMA_ARCHITECTURE77__};
}
test('native inspector explains sources, deciles and distinct values without a storage owner',()=>{
 const {c,api}=runtime(),html=api.paragraphs(parent.rows[0]),s=api.snapshot();
 assert.equal(s.ready,true);assert.equal(s.rows,77);assert.equal(s.maximumRoofAvailable,41);assert.equal(s.differentMinimumRoof,39);
 assert.equal(c.__SOMA_ARCHITECTURE77_DATA__,undefined);
 assert.match(html,/Référence du modèle calculée/);assert.match(html,/46\.100 m/);assert.match(html,/46\.200 m/);
 assert.match(html,/2,5e à 4e décile/);assert.match(html,/9e décile/);assert.match(html,/pages imprimées 68 et 76–78/);
 assert.match(html,/cause/);assert.match(html,/non renseignée/);assert.doesNotMatch(html,/undefined|NaN/);
 assert.match(api.paragraphs({...parent.rows[0],ignId:'different'}),/indisponible/);
});
test('present statistical ridge is shown and raw labels cannot inject HTML',()=>{
 const changed=clone(data),row=changed.rows.find(r=>r.fields.altitude_maximale_toit!==null);row.method='<img onerror="bad">';
 const {api}=runtime(changed),html=api.paragraphs(parent.rows.find(r=>r.id===row.id));
 assert.match(html,new RegExp(row.fields.altitude_maximale_toit.toFixed(3).replace('.','\\.')+' m NGF'));
 assert.match(html,/&lt;img onerror=&quot;bad&quot;&gt;/);assert.doesNotMatch(html,/<img/);
});
test('versioned payload matches proof JSON and invalid data fails closed',()=>{
 const c={window:{}};vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(game,'src/v77/architecture-semantics-data.js'),'utf8'),c);
 assert.deepEqual(JSON.parse(JSON.stringify(c.window.__SOMA_ARCHITECTURE77_DATA__)),data);
 const changed=clone(data);changed.rows.pop();const {api}=runtime(changed);assert.equal(api.snapshot().ready,false);assert.match(api.snapshot().problem,/incompatible/);
 assert.match(api.paragraphs(parent.rows[0]),/indisponible/);
});
