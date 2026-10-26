"""Add bounded terrain mosaics to the frozen terrain runtime, with strict anchors.

The original grid remains the legacy fallback. A present transient tile owns its
NoData; missing samples never leak through to the legacy grid underneath it.
"""

import re

_MARKER = '/* SOMA v69 terrain mosaic: shared nodes, strict admission, no invented ground. */'

_HELPERS = r"""/* SOMA v69 terrain mosaic: shared nodes, strict admission, no invented ground. */
const v69Tiles=new Map(),V69_MAX_TILES=64,V69_MAX_NODES=2000000,V69_MAX_TILE_NODES=100000;
let v69AnchorRecords=null,v69AnchorsDirty=true,v69Revision=0;
const v69Finite=n=>typeof n==='number'&&Number.isFinite(n);
const v69EqualBounds=(a,b)=>Array.isArray(a)&&Array.isArray(b)&&a.length===4&&b.length===4&&a.every((v,i)=>v69Finite(v)&&Math.abs(v-b[i])<=1e-6);
function v69Bounds(b){
 if(!Array.isArray(b)||b.length!==4||!b.every(v69Finite)||Math.abs(b[2]-b[0]-250)>1e-6||Math.abs(b[3]-b[1]-250)>1e-6)throw Error('Relief v69 : emprise de cellule 250 m invalide.');
 return b.slice();
}
function v69RecordId(record){return String(record?.cellId||'');}
function v69GridForRecord(record){
 if(!record||!Array.isArray(record.boundsL93))return null;
 const tile=v69Tiles.get(v69RecordId(record));
 if(tile)return v69EqualBounds(tile.bounds,record.boundsL93)?tile.grid:null;
 const b=record.boundsL93,c=grid?.boundsL93;
 return c&&b[0]>=c[0]-1e-6&&b[1]>=c[1]-1e-6&&b[2]<=c[2]+1e-6&&b[3]<=c[3]+1e-6?grid:null;
}
function v69GridFor(z){return isReal(z)?v69GridForRecord(z.v50Record):null;}
function v69EnsureAnchors(){
 const records=window.__SOMA_V52__?.records?.()||new Map();
 if(v69AnchorsDirty||!v69AnchorRecords||records.size!==v69AnchorRecords.size||[...records].some(([id,value])=>v69AnchorRecords.get(id)!==value))anchorIndex();
}
function v69TileComplete(g){
 for(let row=1;row<g.rows-1;row++)for(let col=1;col<g.cols-1;col++)if(!g.mask[row*g.cols+col])return false;
 return true;
}
function v69Validate(pack,bounds){
 if(!pack||typeof pack.gridHeader!=='string'||pack.gridHeader.length>10000)throw Error('Relief v69 : grille absente.');
 const h=JSON.parse(pack.gridHeader);
 const headerKeys=new Set(['boundsL93','cols','rows','crs','x0','n0','step','units','verticalDatum','haloNodes','interpolation','nodeRegistration','rowOrder']);
 if(h&&Object.keys(h).some(key=>!headerKeys.has(key)))throw Error('Relief v69 : entête contient un champ inconnu.');
 if(!h||![1,5,25].includes(h.step)||h.haloNodes!==1||h.cols!==250/h.step+3||h.rows!==h.cols||h.cols*h.rows>V69_MAX_TILE_NODES||Math.abs(h.x0-(bounds[0]-h.step))>1e-6||Math.abs(h.n0-(bounds[3]+h.step))>1e-6)throw Error('Relief v69 : carroyage, halo ou budget incompatible.');
 if(!pack.source||typeof pack.source!=='object'||typeof pack.source.truth!=='string'||!pack.source.truth.trim())throw Error('Relief v69 : provenance absente.');
 if((pack.testOnly||/fixture|synthetic/i.test(pack.source.truth))&&!window.__SOMA_TERRAIN56_QA__)throw Error('Relief v69 : une fixture ne peut pas servir de relief réel.');
 const sha=s=>typeof s==='string'&&/^[a-f0-9]{64}$/i.test(s);
 let identified=sha(pack.source.sourceGridSHA256)||sha(pack.source.sha256);
 if(pack.source.files!==undefined){
  if(!Array.isArray(pack.source.files)||!pack.source.files.length||pack.source.files.some(f=>!f||!sha(f.sha256)))throw Error('Relief v69 : empreinte de source raster invalide.');
  identified=true;
 }
 if(!identified)throw Error('Relief v69 : empreinte de la source absente.');
 return K.load(pack,bounds);
}
function v69CheckPair(a,b){
 const x=a.boundsL93,y=b.boundsL93;
 const overlapX=Math.min(x[2],y[2])-Math.max(x[0],y[0]),overlapN=Math.min(x[3],y[3])-Math.max(x[1],y[1]);
 if(overlapX< -1e-6||overlapN< -1e-6)return;
 if(Math.abs(a.step-b.step)>1e-9)throw Error('Relief v69 : raccord entre LOD différents non pris en charge.');
 const s=a.step,left=Math.max(a.x0,b.x0),right=Math.min(a.x0+(a.cols-1)*s,b.x0+(b.cols-1)*s),
       north=Math.min(a.n0,b.n0),south=Math.max(a.n0-(a.rows-1)*s,b.n0-(b.rows-1)*s);
 if(right<left-1e-6||north<south-1e-6)return;
 for(const [value,origin]of[[left,a.x0],[left,b.x0],[north,a.n0],[north,b.n0]])if(Math.abs((value-origin)/s-Math.round((value-origin)/s))>1e-6)throw Error('Relief v69 : nœuds de raccord non alignés.');
 const cols=Math.round((right-left)/s),rows=Math.round((north-south)/s);
 for(let row=0;row<=rows;row++)for(let col=0;col<=cols;col++){
  const e=left+col*s,n=north-row*s,ha=a.sample(e,n),hb=b.sample(e,n);
  if(ha!==null&&hb!==null&&Math.abs(ha-hb)>.030000001)throw Error('Relief v69 : rupture de terrain supérieure à 3 cm, y compris dans le halo.');
 }
}
function v69ActiveTile(cellId,bounds){
 if(typeof zone==='undefined'||!isReal(zone))return false;
 return v69RecordId(zone.v50Record)===cellId||v69EqualBounds(zone.v50Record.boundsL93,bounds);
}
function v69Attach(cellId,pack,boundsL93){
 if(typeof cellId!=='string'||!/^[A-Za-z0-9_.:-]{1,160}$/.test(cellId))throw Error('Relief v69 : identifiant de cellule invalide.');
 const bounds=v69Bounds(boundsL93),old=v69Tiles.get(cellId);
 if(old&&old.grid.pack.sha256===pack?.sha256&&v69EqualBounds(old.bounds,bounds))return {cellId,sha256:old.grid.pack.sha256,complete:v69TileComplete(old.grid),reused:true};
 if(old)throw Error('Relief v69 : une version différente est déjà attachée ; la détacher hors de la cellule active.');
 if(v69ActiveTile(cellId,bounds))throw Error('Relief v69 : ne pas remplacer le terrain de la cellule active.');
 if(v69Tiles.size>=V69_MAX_TILES)throw Error('Relief v69 : budget de tuiles dépassé.');
 const next=v69Validate(pack,bounds);
 const nodes=[...v69Tiles.values()].reduce((sum,t)=>sum+t.grid.cols*t.grid.rows,0)+next.cols*next.rows;
 if(nodes>V69_MAX_NODES)throw Error('Relief v69 : budget de nœuds dépassé.');
 for(const tile of v69Tiles.values()){
  if(Math.min(bounds[2],tile.bounds[2])-Math.max(bounds[0],tile.bounds[0])>1e-6&&Math.min(bounds[3],tile.bounds[3])-Math.max(bounds[1],tile.bounds[1])>1e-6)throw Error('Relief v69 : deux cellules de terrain se chevauchent.');
  v69CheckPair(next,tile.grid);
 }
 if(grid)v69CheckPair(next,grid);
 v69Tiles.set(cellId,{bounds,grid:next});v69AnchorsDirty=true;v69Revision++;
 return {cellId,sha256:pack.sha256,complete:v69TileComplete(next),reused:false};
}
function v69Detach(ids){
 if(!Array.isArray(ids)||ids.some(id=>typeof id!=='string'))throw Error('Relief v69 : liste de cellules requise.');
 for(const id of ids){const tile=v69Tiles.get(id);if(tile&&v69ActiveTile(id,tile.bounds))throw Error('Relief v69 : impossible de détacher le terrain actif.');}
 let count=0;for(const id of ids)if(v69Tiles.delete(id))count++;
 if(count){v69AnchorsDirty=true;v69Revision++;}
 return count;
}
function v69Snapshot(){
 const tiles=[...v69Tiles].map(([cellId,t])=>({cellId,boundsL93:t.bounds.slice(),stepM:t.grid.step,sha256:t.grid.pack.sha256,
  nodes:t.grid.cols*t.grid.rows,validNodes:t.grid.stats.valid,noDataNodes:t.grid.stats.noData,complete:v69TileComplete(t.grid)}));
 return {version:'0.69.0',revision:v69Revision,tiles,attachedTiles:tiles.length,nodes:tiles.reduce((sum,t)=>sum+t.nodes,0),maxTiles:V69_MAX_TILES,maxNodes:V69_MAX_NODES,
  baselineSHA256:activePack?.sha256||null,completeMetropole:false,certified:false};
}
function v69TraceTerrain(origin,direction,range,sight=window.__SOMA_SIGHT61_CORE__){
 if(!sight||typeof sight.terrain!=='function'||!sight.finite3(origin)||!sight.finite3(direction)||!Number.isFinite(range)||range<0||range>2000||Math.hypot(...direction)<1e-8)return {distance:0,kind:'invalid'};
 // Preserve the exact historical ray path when there is no overlay.
 if(!v69Tiles.size)return grid?sight.terrain(grid,origin,direction,range):{distance:0,kind:'unknown-terrain'};
 const candidates=[...v69Tiles].map(([cellId,tile])=>({cellId,grid:tile.grid,bounds:tile.bounds}));
 const baseline=grid?{cellId:null,grid,bounds:grid.boundsL93}:null;
 const cuts=[0,range];
 for(const tile of [...candidates,...(baseline?[baseline]:[])]){
  const b=tile.bounds,span=sight.slab(origin,direction,[b[0],-Infinity,-b[3]],[b[2],Infinity,-b[1]],range,[0,2]);
  if(span)for(const t of span)if(t>1e-8&&t<range-1e-8)cuts.push(t);
 }
 cuts.sort((a,b)=>a-b);
 const ordered=cuts.filter((value,index)=>index===0||value-cuts[index-1]>1e-8);
 const inside=(tile,p)=>p[0]>=tile.bounds[0]-1e-8&&p[0]<=tile.bounds[2]+1e-8&&-p[2]>=tile.bounds[1]-1e-8&&-p[2]<=tile.bounds[3]+1e-8;
 const choose=point=>{
  const covering=candidates.filter(tile=>inside(tile,point));
  // A ray lying exactly on a shared boundary may belong to both tiles.
  // Trace those covering grids from this interval's entry, never from an
  // origin outside them, and retain the nearest measured/unknown result.
  if(covering.length)return covering.sort((a,b)=>a.cellId.localeCompare(b.cellId));
  return baseline&&inside(baseline,point)?[baseline]:[];
 };
 const nearest=(tiles,start,end)=>{
  const localOrigin=sight.point(origin,direction,start);let nearest=null;
  for(const tile of tiles){
   const hit=sight.terrain(tile.grid,localOrigin,direction,end-start);
   if(hit&&(!nearest||hit.distance<nearest.distance-1e-8||Math.abs(hit.distance-nearest.distance)<=1e-8&&hit.kind==='unknown-terrain'))nearest={...hit,cellId:tile.cellId,terrainSHA256:tile.grid.pack.sha256};
  }
  return nearest?{...nearest,distance:start+nearest.distance}:null;
 };
 if(range<=1e-8){const tiles=choose(origin);return tiles.length?nearest(tiles,0,range):{distance:0,kind:'unknown-terrain'};}
 for(let i=0;i<ordered.length-1;i++){
  const start=ordered[i],end=ordered[i+1];if(end-start<=1e-8)continue;
  const middle=sight.point(origin,direction,(start+end)/2),tiles=choose(middle);
  if(!tiles.length)return {distance:start,kind:'unknown-terrain'};
  const hit=nearest(tiles,start,end);if(hit)return hit;
 }
 return null;
}
const v69API={attach:v69Attach,detach:v69Detach,clear(){return v69Detach([...v69Tiles.keys()]);},gridFor:v69GridFor,snapshot:v69Snapshot,
 traceTerrain:v69TraceTerrain,get revision(){return v69Revision;},refreshAnchors(){anchorIndex();return anchors.size;}};
"""


def _once(script, old, new, label):
    if script.count(old) != 1:
        raise ValueError(f'Relief v69 : ancre non unique ou différente ({label}).')
    return script.replace(old, new, 1)


def patch_terrain_runtime(script: str) -> str:
    """Patch only the frozen soma-v56-terrain-runtime script; refuse source drift."""
    if not isinstance(script, str):
        raise TypeError('Le script terrain doit être une chaîne.')
    if _MARKER in script or 'function v69GridForRecord(' in script:
        raise ValueError('La mosaïque terrain v69 est déjà appliquée.')
    script = _once(script,
                   'const isReal=z=>!!z?.v52District&&!!z.v50Record?.v53Validated&&!z.v50Record?.v53Synthetic;\n',
                   'const isReal=z=>!!z?.v52District&&!!z.v50Record?.v53Validated&&!z.v50Record?.v53Synthetic;\n' + _HELPERS,
                   'fonctions de mosaïque')
    replacements = [
        ('const activeFor=z=>!!grid&&isReal(z);',
         'const activeFor=z=>!!v69GridFor(z);', 'activation par cellule'),
        ('function ground(z,x,zz){if(!activeFor(z))return null;const p=K.world(z.v50Record,x,zz);return grid.sample(...p);}',
         'function ground(z,x,zz){const cellGrid=v69GridFor(z);if(!cellGrid)return null;const p=K.world(z.v50Record,x,zz);return cellGrid.sample(...p);}', 'sol par cellule'),
        ('function slope(z,x,zz){if(!activeFor(z))return null;return grid.gradient(...K.world(z.v50Record,x,zz));}',
         'function slope(z,x,zz){const cellGrid=v69GridFor(z);if(!cellGrid)return null;return cellGrid.gradient(...K.world(z.v50Record,x,zz));}', 'pente par cellule'),
        ('function anchorIndex(){\n anchors.clear();',
         'function anchorIndex(){\n v69AnchorRecords=new Map(window.__SOMA_V52__?.records?.()||[]);v69AnchorsDirty=false;\n anchors.clear();', 'cache des ancrages'),
        ('    const h=grid.sample(q[0],q[1]);if(h===null){item.missing=true;continue;}',
         '    const recordGrid=v69GridForRecord(record),h=recordGrid?recordGrid.sample(q[0],q[1]):null;if(h===null){item.missing=true;continue;}', 'ancrages du bon MNT'),
        ('function activate(p,next){grid=next;',
         'function activate(p,next){for(const tile of v69Tiles.values())v69CheckPair(next,tile.grid);v69Revision++;grid=next;', 'protection du socle gelé'),
        (' const z=g.__v56.zone,box=z.v50Record.boundsL93,ce=(box[0]+box[2])/2,cn=(box[1]+box[3])/2;',
         ' const z=g.__v56.zone,box=z.v50Record.boundsL93,ce=(box[0]+box[2])/2,cn=(box[1]+box[3])/2;\n const grid=v69GridFor(z);if(!grid)return;', 'découpe des surfaces sur le bon MNT'),
        (' const m=g.__v56;\n const area=',
         ' const m=g.__v56,grid=v69GridFor(m.zone);if(!grid)return;\n const area=', 'triangles du bon MNT'),
        ('function buildTerrain(z,g,color){\n if(!activeFor(z))return false;',
         'function buildTerrain(z,g,color){\n const grid=v69GridFor(z);if(!grid)return false;', 'maillage du bon MNT'),
        (' z.v56Build={terrainSHA256:activePack.sha256,stepM:grid.step,',
         ' z.v56Build={terrainSHA256:grid.pack.sha256,stepM:grid.step,', 'empreinte du maillage'),
        (' if(!activeFor(z))return null;const a=anchors.get(String(id));',
         ' if(!activeFor(z))return null;v69EnsureAnchors();const a=anchors.get(String(id));', 'rafraîchissement du datum bâtiment'),
        ('function building(z,g,mesh,p,id,fn){\n if(!activeFor(z))return fn();\n const a=anchors.get(String(id));',
         'function building(z,g,mesh,p,id,fn){\n const grid=v69GridFor(z);if(!grid)return fn();\n v69EnsureAnchors();const a=anchors.get(String(id));', 'fondations du bon MNT'),
        ('function snapshot(){return {version:VERSION,ready,loaded:!!grid,status,',
         'function snapshot(){return {version:VERSION,ready,loaded:!!grid,status,mosaic:v69Snapshot(),', 'diagnostic mosaïque'),
        (' const target=WORLD.zones[args[0]];\n  if(activeFor(target)){',
         " const target=WORLD.zones[args[0]];\n  if(isReal(target)&&!v69GridFor(target)){status='Entrée refusée : relief de la cellule absent.';refresh();return false;}\n  if(activeFor(target)){", 'refus du sol plat implicite'),
        ('const T={version:VERSION,ready:false,core:K,',
         'const T={version:VERSION,ready:false,core:K,v69:v69API,', 'API mosaïque'),
    ]
    for old, new, label in replacements:
        script = _once(script, old, new, label)
    # The HUD must describe the active LOD, while the historical export/card
    # continue to refer to the unchanged baseline grid.
    script = _once(script,
                   "const h=ground(zone,camera.x,camera.z);tag.textContent=h===null?'IGN · altitude absente — passage bloqué':`${activePack?.source?.truth==='fixture'?'QA SYNTHÉTIQUE':delivered(activePack)?'IGN':'MNT déclaré'} · ${h.toFixed(2)} m · grille ${grid.step} m · non certifié`;",
                   "const h=ground(zone,camera.x,camera.z),currentGrid=v69GridFor(zone),currentPack=currentGrid?.pack;tag.textContent=h===null?'IGN · altitude absente — passage bloqué':`${currentPack?.source?.truth==='fixture'?'QA SYNTHÉTIQUE':delivered(currentPack)?'IGN':'MNT déclaré'} · ${h.toFixed(2)} m · grille ${currentGrid.step} m · non certifié`;",
                   'LOD du HUD')
    return script


# Explicit alias for callers following the source-script name.
patch_terrain = patch_terrain_runtime


def _rewrite_script(html, script_id, rewrite):
    pattern = re.compile(r'(<script\b[^>]*\bid="' + re.escape(script_id) + r'"[^>]*>)(.*?)(</script>)', re.S)
    if len(pattern.findall(html)) != 1:
        raise ValueError(f'Relief v69 : script consommateur absent ou dupliqué ({script_id}).')
    return pattern.sub(lambda match: match[1] + rewrite(match[2]) + match[3], html, count=1)


def patch_consumers(html: str) -> str:
    """Use the zone's grid for vehicles and revision-safe preparation jobs.

    SIGHT61 is deliberately not rewritten here: the parent builder owns its
    source-index, building-part and inter-tile-ray integration together.
    """
    if not isinstance(html, str):
        raise TypeError('Le HTML de reconstruction doit être une chaîne.')

    def contact(script):
        return _once(script,
                     'K.groundFootprint(terrain.grid,wz.v50Record,poly)',
                     'K.groundFootprint(terrain.v69?.gridFor(wz)??terrain.grid,wz.v50Record,poly)',
                     'contact véhicule sur le bon MNT')

    def preparation(script):
        script = _once(script, 'T()?.grid!==job.terrain',
                       '(T()?.v69?.revision??T()?.grid)!==job.terrain',
                       'révision du préchargement')
        return _once(script, 'terrain:T()?.grid',
                     'terrain:(T()?.v69?.revision??T()?.grid)',
                     'capture de révision du préchargement')

    html = _rewrite_script(html, 'soma-v57-runtime', contact)
    return _rewrite_script(html, 'soma-v65-performance-runtime', preparation)
