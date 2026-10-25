"""Expose a transient tile registry in reconstructed HTML, preserving frozen files."""
import re

_MARKER = '/* SOMA v69 transient geographic registry: never persisted through dbAll. */'
_ID_GUARD = "if(typeof id!=='string'||!/^V52-MC-(?:[1-5][1-5]|[EW][0-9]{2}-[NS][0-9]{2})$/.test(id))"
_ID_GUARD_WIDE = "if(typeof id!=='string'||!/^V52-MC-(?:[1-5][1-5]|[EW][0-9]{2,4}-[NS][0-9]{2,4})$/.test(id))"

_REGISTRY = r"""/* SOMA v69 transient geographic registry: never persisted through dbAll. */
const TRANSIENT69=new Map();
function grid69(id){
 let m=String(id).match(/^V52-MC-([1-5])([1-5])$/);
 if(m)return{gridX:Number(m[2])-3,gridY:Number(m[1])-3};
 m=String(id).match(/^V52-MC-([EW])(\d{2,4})-([NS])(\d{2,4})$/);
 return m?{gridX:(m[1]==='W'?-1:1)*Number(m[2]),gridY:(m[3]==='N'?-1:1)*Number(m[4])}:null;
}
function protected69(id){
 const direct=zone?.v52CellId,parent=zone?.v51ParentCellId;
 if(id===direct||id===parent)return true;
 const active=DISTRICT.cells.find(c=>c.id===(direct||parent)),candidate=DISTRICT.cells.find(c=>c.id===id);
 return !!active&&!!candidate&&Math.abs(active.gridX-candidate.gridX)<=1&&Math.abs(active.gridY-candidate.gridY)<=1;
}
function registerTransient69(def,raw){
 const id=def?.id||def?.cellId,g=grid69(id);
 if(!g||!def||!Number.isInteger(def.gridX)||!Number.isInteger(def.gridY)||g.gridX!==def.gridX||g.gridY!==def.gridY)throw Error('Tuile externe : identifiant/carroyage contradictoire');
 if(RECORDS.has(id)&&!TRANSIENT69.has(id))throw Error('Le socle original ne peut pas être remplacé par le streaming');
 if(TRANSIENT69.has(id)&&protected69(id))throw Error('Une cellule active ou voisine ne peut pas être remplacée');
 if(DISTRICT.cells.some(c=>c.id!==id&&c.gridX===g.gridX&&c.gridY===g.gridY))throw Error('Deux identifiants occupent la même cellule');
 const metric=C53.metricCell({id,gridX:g.gridX,gridY:g.gridY},DISTRICT);
 if(!Array.isArray(def.boundsL93)||def.boundsL93.length!==4||def.boundsL93.some((n,i)=>!Number.isFinite(n)||Math.abs(n-metric.boundsL93[i])>.001))throw Error('Tuile externe décalée du repère métrique');
 if(def.boundsWGS84&&!C53.bboxEqual(def.boundsWGS84,metric.boundsWGS84,1e-6))throw Error('Emprise WGS84 de tuile contradictoire');
 const record=C53.normalizeRecord(raw,id,{cells:[metric]});
 if(record.cellId!==id||C53.isSynthetic(record))throw Error('Le streaming exige une cellule de source déclarée');
 const next={...metric,title:typeof def.title==='string'?def.title.slice(0,200):id,sizeMeters:250,status:'external-source'};
 const previous=ZONES.get(id);if(previous?.static)window.__SOMA_V55__?.remember(previous);
 const index=DISTRICT.cells.findIndex(c=>c.id===id);
 if(index<0)DISTRICT.cells.push(next);else DISTRICT.cells[index]=next;
 const gridIndex=METRIC_GRID53.cells.findIndex(c=>c.id===id);
 if(gridIndex<0)METRIC_GRID53.cells.push(next);else METRIC_GRID53.cells[gridIndex]=next;
 TRANSIENT69.set(id,record);RECORDS.set(id,record);
 const z=makeZone(next,record);z.v69Transient=true;ZONES.set(id,z);WORLD.zones[z.id]=z;
 registerLinks();window.__SOMA_ARCH68__?.invalidate();window.__SOMA_PERF65__?.invalidate();
 return z;
}
function removeTransient69(ids){
 const selected=[...new Set(Array.from(ids||[]))];
 for(const id of selected){if(!TRANSIENT69.has(id))throw Error('Seules les cellules transitoires peuvent être évincées');if(protected69(id))throw Error('Cellule active ou voisine protégée');}
 for(const id of selected){
  const z=ZONES.get(id);if(z?.static)window.__SOMA_V55__?.remember(z);
  TRANSIENT69.delete(id);RECORDS.delete(id);ZONES.delete(id);
  if(z)delete WORLD.zones[z.id];
  for(const [key,child]of Object.entries(WORLD.zones))if(child?.v51ParentCellId===id)delete WORLD.zones[key];
 }
 if(selected.length){
  const removed=new Set(selected);
  DISTRICT.cells.splice(0,DISTRICT.cells.length,...DISTRICT.cells.filter(c=>!removed.has(c.id)));
  METRIC_GRID53.cells.splice(0,METRIC_GRID53.cells.length,...METRIC_GRID53.cells.filter(c=>!removed.has(c.id)));
  registerLinks();window.__SOMA_ARCH68__?.invalidate();window.__SOMA_PERF65__?.invalidate();
 }
 return selected.length;
}
"""


def _replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise ValueError(f'Streaming v69 : ancre {label} absente ou dupliquée.')
    return text.replace(old, new, 1)


def patch_v53(script: str) -> str:
    """Widen tile grid indices, without relaxing the actual geometry validator."""
    if _ID_GUARD_WIDE in script:
        raise ValueError('Streaming v69 : garde déjà étendue.')
    return _replace_once(script, _ID_GUARD, _ID_GUARD_WIDE, 'identifiant métrique')


def patch_v52(script: str) -> str:
    """Add bounded-lifetime records without changing the original IndexedDB store."""
    if _MARKER in script:
        raise ValueError('Streaming v69 : registre déjà ajouté.')
    active = 'function activeRecord(def){return importedFor(def)||EMBEDDED54.get(def.id)||surveyRecord(def.id)}'
    script = _replace_once(script, active,
                           _REGISTRY + '\nfunction activeRecord(def){return TRANSIENT69.get(def.id)||importedFor(def)||EMBEDDED54.get(def.id)||surveyRecord(def.id)}',
                           'registre de sources')
    script = _replace_once(script, 'DISTRICT.cells.length===EMBEDDED54.size&&SURVEY.size===25',
                           'DISTRICT.cells.length===EMBEDDED54.size+TRANSIENT69.size&&SURVEY.size===25',
                           'compte des cellules originales et transitoires')
    return _replace_once(script, 'window.__SOMA_V52__={v54:',
                         'window.__SOMA_V52__={v69:{register:registerTransient69,remove:removeTransient69,transientIds:()=>[...TRANSIENT69.keys()]},v54:',
                         'API de registre')


def _rewrite_script(html, script_id, transform):
    pattern = re.compile(r'(<script\b[^>]*\bid="' + re.escape(script_id) + r'"[^>]*>)(.*?)(</script>)', re.S)
    if len(pattern.findall(html)) != 1:
        raise ValueError(f'Streaming v69 : script {script_id} absent ou dupliqué.')
    return pattern.sub(lambda match: match[1]+transform(match[2])+match[3], html, count=1)


def patch_streaming(html: str) -> str:
    """Apply guarded transformations to a reconstructed document only."""
    html = _rewrite_script(html, 'soma-v53-core', patch_v53)
    return _rewrite_script(html, 'soma-v52-runtime', patch_v52)
