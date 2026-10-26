/* Pure geometry for the independent metropolitan flyover. Source data stays
 * immutable. Unknown terrain is never replaced by a plane or zero altitude.
 */
(function(root){
  'use strict';
  const finitePoint=p=>Array.isArray(p)&&p.length>=2&&Number.isFinite(p[0])&&Number.isFinite(p[1]);
  const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  const activePart=p=>p['building:part']!=null&&(typeof p['building:part']==='object'||
    !['','no','false','0'].includes(String(p['building:part']).trim().toLowerCase()));
  const hash=value=>{let n=2166136261;for(const c of String(value)){n^=c.charCodeAt(0);n=Math.imul(n,16777619);}return n>>>0;};
  const mul=(colour,factor)=>colour.map(value=>Math.max(0,Math.min(1,value*factor)));
  function landcoverAppearance(properties={}){
    const natural=String(properties.natural||'').toLowerCase(),landuse=String(properties.landuse||'').toLowerCase(),leisure=String(properties.leisure||'').toLowerCase();
    let kind='other',colour=[.21,.24,.22];
    if(['wood'].includes(natural)||landuse==='forest'){kind='forest';colour=[.09,.19,.16];}
    else if(['beach','sand','shingle'].includes(natural)){kind='beach';colour=[.46,.40,.28];}
    else if(['bare_rock','scree','rock'].includes(natural)){kind='rock';colour=[.39,.40,.36];}
    else if(natural==='wetland'){kind='wetland';colour=[.13,.23,.23];}
    else if(['scrub','heath'].includes(natural)){kind='scrub';colour=[.18,.25,.20];}
    else if(['farmland','farmyard','orchard','vineyard'].includes(landuse)){kind='agriculture';colour=[.26,.28,.18];}
    else if(landuse==='quarry'){kind='quarry';colour=[.38,.33,.26];}
    else if(['grassland'].includes(natural)||['grass','meadow','village_green'].includes(landuse)){kind='grass';colour=[.19,.28,.19];}
    else if(['park','garden','nature_reserve'].includes(leisure)){kind='park';colour=[.11,.24,.18];}
    else if(['pitch','sports_centre','golf_course'].includes(leisure)){kind='sports';colour=[.15,.28,.22];}
    else if(['industrial','commercial','retail','railway'].includes(landuse)){kind='developed';colour=[.25,.27,.28];}
    return {kind,colour,source:'interpreted-colour-from-osm-landcover'};
  }
  // Explicit OSM zeroes do not describe an elevated floor. Keep this strict:
  // coercing objects, booleans or malformed strings could hide a real datum.
  function zero(value){
    if(value===null||value===undefined||value===''||value===false)return true;
    if(typeof value==='number')return Number.isFinite(value)&&value===0;
    if(typeof value!=='string'||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(value.trim()))return false;
    return Number(value)===0;
  }

  function clipPolygon(subject,clip){
    let polygon=subject.map(p=>p.slice());
    const orientation=Math.sign(clip.reduce((sum,p,i)=>sum+cross(clip[0],p,clip[(i+1)%clip.length]),0))||1;
    for(let i=0;i<clip.length&&polygon.length;i++){
      const a=clip[i],b=clip[(i+1)%clip.length],out=[];
      let previous=polygon.at(-1),d0=cross(a,b,previous)*orientation;
      for(const p of polygon){const d1=cross(a,b,p)*orientation,inside=d1>=-1e-8,was=d0>=-1e-8;
        if(inside!==was){const t=d0/(d0-d1);out.push([previous[0]+(p[0]-previous[0])*t,previous[1]+(p[1]-previous[1])*t]);}
        if(inside)out.push(p.slice());previous=p;d0=d1;
      }polygon=out;
    }return polygon;
  }

  function emptyCounts(){return {triangles:0,terrainTriangles:0,missingTerrainTriangles:0,buildingTriangles:0,
    buildings:0,estimatedBuildings:0,ignHeightBuildings:0,missingGroundBuildings:0,
    sourceWallSegments:0,windows:0,litWindows:0,roadTriangles:0,waterTriangles:0,
    landuseTriangles:0,drapedWaterTriangles:0,unsupportedStructures:0,omittedOutlines:0,unknownFootprintAreaM2:0,
    modelledRoofs:0,unsurveyedRoofs:0,canopyBackfaceTriangles:0,estimatedRoadWidths:0,missingSurfacePieces:0};}

  // A typed DEM-only tile has no vector record, including no fabricated empty
  // FeatureCollection. Its grid is validated upstream by the terrain loader.
  function buildTerrainTile(entry,deps={},options={}){
    const tile=entry?.tile,grid=entry?.layers?.terrain?.grid,bounds=tile?.boundsL93;
    if(tile?.terrainOnly!==true||tile.vector!==null||tile.contentSHA256!==null||!tile.terrain||
      tile.surfaces!=null||tile.navigation!=null||entry?.layers?.vector!=null||
      entry?.layers?.surfaces!=null||entry?.layers?.navigation!=null||!grid||typeof grid.cellTriangles!=='function')
      throw new TypeError('A typed terrain-only tile and a validated terrain grid are required.');
    if(!Array.isArray(bounds)||bounds.length!==4||!bounds.every(Number.isFinite)||bounds[0]>=bounds[2]||bounds[1]>=bounds[3])
      throw new TypeError('Terrain-only bounds must be finite metric coordinates.');
    const maxVertices=options.maxVertices??600000;
    if(!Number.isSafeInteger(maxVertices)||maxVertices<0)throw new RangeError('Invalid terrain geometry budget.');
    const counts=emptyCounts(),values=[],centerL93=[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2];
    const result=grid.cellTriangles(bounds,t=>{
      let [a,b,c]=t;
      if(![a,b,c].every(p=>Array.isArray(p)&&p.length===3&&p.every(Number.isFinite)))throw new TypeError('Non-finite terrain geometry.');
      const u=b.map((v,i)=>v-a[i]),v=c.map((x,i)=>x-a[i]);
      let normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...normal);
      if(length<1e-11)return;
      normal=normal.map(n=>n/length);
      if(normal[1]<0){[b,c]=[c,b];normal=normal.map(n=>-n);}
      if(values.length/9+3>maxVertices)throw new RangeError('Viewer tile exceeds its geometry budget.');
      for(const p of[a,b,c])values.push(...p,...normal,.17,.23,.22);
      counts.triangles++;counts.terrainTriangles++;
    });
    counts.missingTerrainTriangles=result.missing;
    return {vertices:new Float32Array(values),counts,boundsL93:bounds.slice(),centerL93,geometryBytes:values.length*4,
      heightPolicy:'Terrain source only: absolute NGF altitudes, NoData faces omitted; no building heights supplied',
      facadePolicy:'No vector coverage: buildings, roads and facades are not modelled'};
  }

  function buildTile(entry,deps,options={}){
    if(entry?.tile?.terrainOnly===true)return buildTerrainTile(entry,deps,options);
    const record=entry?.layers?.vector,grid=entry?.layers?.terrain?.grid;
    const G=deps?.geo,F=deps?.fidelity,A=deps?.architecture;
    if(!record||!grid||!G||!F||!A||typeof grid.sample!=='function'||typeof grid.cellTriangles!=='function')throw new TypeError('A validated vector record, terrain grid and geographic cores are required.');
    const bounds=(entry.tile?.boundsL93||record.boundsL93).slice(),projector=G.metricProjector(bounds),centerL93=[(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2];
    const width=bounds[2]-bounds[0],depth=bounds[3]-bounds[1],clip=[[-width/2,-depth/2],[width/2,-depth/2],[width/2,depth/2],[-width/2,depth/2]];
    const values=[],maxVertices=options.maxVertices??600000;
    const counts=emptyCounts();
    function triangle(a,b,c,colour,category,upward=false,outward=null){
      if([a,b,c].some(p=>p.length!==3||p.some(v=>!Number.isFinite(v))))throw new TypeError('Non-finite viewer geometry.');
      let u=b.map((v,i)=>v-a[i]),v=c.map((x,i)=>x-a[i]);
      let normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...normal);
      if(length<1e-11)return;
      normal=normal.map(n=>n/length);
      if(upward&&normal[1]<0||outward&&normal.reduce((s,n,i)=>s+n*outward[i],0)<0){[b,c]=[c,b];normal=normal.map(n=>-n);}
      if(values.length/9+3>maxVertices)throw new RangeError('Viewer tile exceeds its geometry budget.');
      for(const p of[a,b,c])values.push(...p,...normal,...colour);
      counts.triangles++;counts[category]=(counts[category]||0)+1;
    }
    function quad(a,b,c,d,colour,category,outward){triangle(a,b,c,colour,category,false,outward);triangle(a,c,d,colour,category,false,outward);}
    const local=q=>projector.toLocal(q),metric=q=>projector.toMetric(q);
    function ground(q){const p=metric(q),h=grid.sample(p[0],p[1]);return Number.isFinite(h)?h:null;}

    // Clip draped surfaces to the actual fixed-diagonal terrain triangles.
    // Their three source nodes must all exist; no face bridges a NoData node.
    function drape(source,colour,offset,category){
      const clipped=clipPolygon(source,clip);if(clipped.length<3)return;
      for(let part=1;part+1<clipped.length;part++){
        const t=[clipped[0],clipped[part],clipped[part+1]];
        if(Math.abs(cross(...t))<1e-10)continue;
        const xs=t.map(p=>p[0]+centerL93[0]),ns=t.map(p=>centerL93[1]-p[1]);
        const left=Math.max(0,Math.floor((Math.min(...xs)-grid.x0)/grid.step));
        const right=Math.min(grid.cols-2,Math.floor((Math.max(...xs)-grid.x0)/grid.step));
        const top=Math.max(0,Math.floor((grid.n0-Math.max(...ns))/grid.step));
        const bottom=Math.min(grid.rows-2,Math.floor((grid.n0-Math.min(...ns))/grid.step));
        for(let row=top;row<=bottom;row++)for(let col=left;col<=right;col++){
          const point=(x,y)=>[grid.x0+x*grid.step-centerL93[0],centerL93[1]-(grid.n0-y*grid.step)];
          const a=point(col,row),b=point(col+1,row),c=point(col,row+1),d=point(col+1,row+1);
          for(const cell of[[a,c,b],[b,c,d]]){
            const poly=clipPolygon(t,cell);if(poly.length<3)continue;
            const heights=cell.map(p=>ground(p));if(heights.some(h=>h===null)){counts.missingSurfacePieces++;continue;}
            const determinant=cross(...cell);
            const lifted=poly.map(p=>{const wb=cross(cell[0],p,cell[2])/determinant,wc=cross(cell[0],cell[1],p)/determinant;
              return[p[0],heights[0]+wb*(heights[1]-heights[0])+wc*(heights[2]-heights[0])+offset,p[1]];});
            for(let i=1;i+1<lifted.length;i++)triangle(lifted[0],lifted[i],lifted[i+1],colour,category,true);
          }
        }
      }
    }

    const terrainResult=grid.cellTriangles(bounds,t=>triangle(t[0],t[1],t[2],[.17,.23,.22],'terrainTriangles',true));
    counts.missingTerrainTriangles=terrainResult.missing;
    const features=record.featureCollection.features||[],sourceSurfaces=entry.layers.surfaces;
    const surfaceCell=sourceSurfaces?.cell;
    const useSurfaces=sourceSurfaces?.schema==='soma-metropole/surface-cell/1'&&sourceSurfaces.cellId===record.cellId&&
      sourceSurfaces.sourcePbfSHA256===record.sourceReceipt.sha256&&surfaceCell?.contentSHA256===record.contentSHA256&&
      surfaceCell.sourceSHA256===record.sourceReceipt.sha256;
    const preparedRoadSurfaces=useSurfaces&&Object.values(surfaceCell.surfaces||{}).some(layer=>Array.isArray(layer)&&layer.length>0);
    if(preparedRoadSurfaces){
      const colours={road:[.065,.08,.09],unsealed:[.27,.23,.17],paved:[.23,.25,.25],foot:[.22,.26,.27],walk:[.28,.30,.28],mark:[.7,.76,.72]};
      const levels={road:.06,unsealed:.05,paved:.07,foot:.07,walk:.1,mark:.08};
      for(const [kind,triangles]of Object.entries(surfaceCell.surfaces||{}))for(const t of triangles){
        if(Array.isArray(t)&&t.length===3&&t.every(finitePoint))drape(t,colours[kind]||colours.road,levels[kind]||.06,'roadTriangles');
      }
    }

    const candidates=features.filter(f=>f.properties?.['soma:layer']==='buildings');
    const parts=candidates.filter(f=>activePart(f.properties));
    const omitted=options.omitBuildingIds||new Set();
    const polygonArea=polygon=>polygon.length<3?0:Math.abs(polygon.reduce((sum,p,i)=>sum+cross(polygon[0],p,polygon[(i+1)%polygon.length]),0))/2;
    function declaredOutlineWithLocalParts(feature){
      if(String(feature.properties['building:part']||'').toLowerCase()!=='no')return false;
      const parentTriangles=(feature.properties['soma:mesh53']||[]).flatMap(mesh=>mesh.trianglesL93);
      return parts.some(part=>part.id!==feature.id&&(part.properties['soma:mesh53']||[]).some(piece=>{
        if(!piece.trianglesL93?.length)return false;
        // Source triangulations already exclude courtyards. Area intersection
        // proves full containment; centroids or sampled edges cannot do that.
        return piece.trianglesL93.every(triangle=>{
          const expected=polygonArea(triangle);if(expected<=1e-10)return true;
          const covered=parentTriangles.reduce((sum,parent)=>sum+polygonArea(clipPolygon(triangle,parent)),0);
          return Math.abs(covered-expected)<=Math.max(1e-6,expected*1e-9);
        });
      }));
    }

    for(const feature of features){
      const p=feature.properties||{},id=String(p.canonical_id||feature.id),layer=p['soma:layer']||p.logical_layer;
      const mg=p['soma:metricGeometry'];
      if(layer==='buildings'){
        const meshes=p['soma:mesh53']||[];
        if(omitted.has(id)||declaredOutlineWithLocalParts(feature)){
          counts.omittedOutlines++;counts.unknownFootprintAreaM2+=meshes.reduce((sum,m)=>sum+m.areaM2,0);continue;
        }
        const kind=String(p.building||'yes'),fallback=(/industrial|warehouse|hangar|retail/.test(kind)?7:/church|cathedral|tower/.test(kind)?18:/garage|shed/.test(kind)?3.4:8)+(hash(id)%8)*1.35;
        const candidate=options.heightReferences?.get?.(id)||sourceSurfaces?.buildings?.[id];
        const present=value=>value!==null&&value!==undefined&&String(value).trim()!=='';
        const ownBinding=candidate&&candidate.sourceSHA256===record.sourceReceipt.sha256&&
          candidate.geometrySHA256===p['soma:geometry_sha256']&&candidate.cellContentSHA256===record.contentSHA256;
        const legacySidecar=useSurfaces&&candidate===sourceSurfaces?.buildings?.[id];
        const referenceAllowed=!present(p.height)&&!activePart(p)&&zero(p.min_height)&&zero(p['building:min_level'])&&
          zero(p.layer)&&String(p.building||'').trim().toLowerCase()!=='roof'&&
          !['underground','underwater','overground'].includes(String(p.location||'').trim().toLowerCase());
        const eavesCandidate=candidate?.heightKind==='eaves';
        const eavesReference=referenceAllowed&&ownBinding&&eavesCandidate&&candidate.roofSurveyed===false&&
          /^[a-f0-9]{64}$/i.test(candidate.proofSHA256||'')&&Number.isFinite(candidate.height)&&candidate.height>.05&&candidate.height<=1000&&Number.isFinite(candidate.groundAltitude);
        const legacyReference=referenceAllowed&&!eavesCandidate&&(ownBinding||legacySidecar)&&candidate&&F.canApplyHeight(p,candidate);
        const ref=eavesReference||legacyReference?candidate:null;
        const dim=A.roofDimensions(p,F.dimension(p,fallback,ref));if(!dim.valid)continue;
        if(options.missingCanonicalDatums?.has(id)&&dim.heightSource!=='ign-bdtopo-height'){
          counts.missingGroundBuildings++;continue;
        }
        let base=dim.heightSource==='ign-bdtopo-height'&&Number.isFinite(dim.groundAltitude)?dim.groundAltitude:options.canonicalDatumsMap?.get(id),missing=false;
        if(!Number.isFinite(base)){
          const heights=[];
          for(const mesh of meshes)for(const ring of mesh.ringsL93)for(const point of ring){const h=grid.sample(...point);if(!Number.isFinite(h))missing=true;else heights.push(h);}
          base=heights.length?Math.max(...heights):null;
        }
        if(missing||!Number.isFinite(base)){counts.missingGroundBuildings++;continue;}
        if(dim.heightSource.startsWith('estimated')||dim.heightSource==='procedural-estimate')counts.estimatedBuildings++;
        if(dim.heightSource==='ign-bdtopo-height')counts.ignHeightBuildings++;
        const material=A.appearance(p,id),canonical=options.references?.get(A.referenceKey(p,id,record));
        // IGN eaves height is the top of a modelled wall, not a roof survey.
        // Do not add an OSM roof rise or infer a dome from this measurement.
        const plan=eavesReference?{shape:'flat',modelled:false,reason:'ign-eaves-flat-roof-approximation',
          eave:dim.height,heightAt:()=>dim.height,breakLines:[],accuracy:'roof-unsurveyed'}:A.roofPlan(p,dim,canonical);
        if(eavesReference)counts.unsurveyedRoofs++;
        if(plan.modelled&&plan.shape!=='flat')counts.modelledRoofs++;
        for(const mesh of meshes){
          const triangles=mesh.trianglesL93.map(t=>t.map(local));
          for(const t of A.roofTriangles(triangles,plan,projector)){
            const lifted=t.map(([x,y,z])=>[x,base+y,z]);
            triangle(...lifted,material.roof,'buildingTriangles',true);
            if(dim.openStructure){triangle(...lifted,mul(material.roof,.7),'buildingTriangles',false,[0,-1,0]);counts.canopyBackfaceTriangles++;}
          }
          for(const [aa,bb]of mesh.wallsL93){
            const a=local(aa),b=local(bb),dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);if(length<1e-6||dim.openStructure)continue;
            let outward=[dz/length,0,-dx/length];const middle=[(aa[0]+bb[0])/2,(aa[1]+bb[1])/2];
            if(G.inPolygon([middle[0]+outward[0]*.01,middle[1]-outward[2]*.01],mesh.ringsL93))outward=outward.map(v=>-v);
            const ha=base+plan.heightAt(...aa),hb=base+plan.heightAt(...bb),floor=base+dim.minHeight;
            for(const wall of A.wallSegments(a,b,plan,projector)){
              quad([wall.a[0],floor,wall.a[1]],[wall.b[0],floor,wall.b[1]],
                [wall.b[0],base+wall.topB,wall.b[1]],[wall.a[0],base+wall.topA,wall.a[1]],
                mul(material.wall,.88+.08*Math.abs(outward[0])),'buildingTriangles',outward);
            }
            counts.sourceWallSegments++;
            // Foundation skirts follow original source walls only; unknown
            // ground endpoints are withheld rather than assigned zero height.
            if(dim.minHeight===0){const ga=grid.sample(...aa),gb=grid.sample(...bb);
              if(Number.isFinite(ga)&&Number.isFinite(gb)&&(Math.abs(base-ga)>1e-5||Math.abs(base-gb)>1e-5))quad([a[0],ga,a[1]],[b[0],gb,b[1]],[b[0],base,b[1]],[a[0],base,a[1]],mul(material.wall,.65),'buildingTriangles',outward);
            }
            const monument=!!p.heritage||!!p.historic||/church|cathedral|chapel|basilica/.test(kind)||p.amenity==='place_of_worship'||activePart(p);
            if(!monument&&Math.min(ha,hb)-floor>5&&options.details!==false){
              const panels=A.facadePanels(a,b,projector,id,1.1,3.6),rows=Math.min(options.maxWindowRows??3,Math.floor((Math.min(ha,hb)-floor-1)/3.05));
              for(let row=0;row<rows;row++)for(const item of panels){
                const y=floor+1.85+row*3.05;if(y+.6>=Math.min(ha,hb))continue;
                const light=A.windowLight(id,row,item.slot),x=item.center[0]+outward[0]*.025,z=item.center[1]+outward[2]*.025,tx=dx/length,tz=dz/length,w=item.width/2;
                quad([x-tx*w,y-.55,z-tz*w],[x+tx*w,y-.55,z+tz*w],[x+tx*w,y+.55,z+tz*w],[x-tx*w,y+.55,z-tz*w],light.colour,'buildingTriangles',outward);counts.windows++;if(light.lit)counts.litWindows++;
              }
            }
          }
        }counts.buildings++;
      }else if(layer==='roads'||layer==='rail'){
        const structural=deps.terrain?.structure?.(p)||F.roadProfile(p).structural||
          ['yes','true','1'].includes(String(p.indoor||'').toLowerCase())||['yes','true','1'].includes(String(p.covered||'').toLowerCase());
        if(structural){counts.unsupportedStructures++;continue;}
        if(layer==='roads'&&preparedRoadSurfaces)continue;
        const lines=mg?.type==='LineString'?[mg.coordinates]:mg?.type==='MultiLineString'?mg.coordinates:[];
        if(!lines.length)continue;
        const profile=F.roadProfile(p),roadWidth=layer==='rail'?1.4:profile.width;
        if(layer==='roads'&&!profile.widthSource.startsWith('osm-'))counts.estimatedRoadWidths++;
        for(const line of lines)for(let i=1;i<line.length;i++){
          const a=local(line[i-1]),b=local(line[i]),dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);if(length<1e-6)continue;
          const nx=-dz/length*roadWidth/2,nz=dx/length*roadWidth/2;
          const ring=[[a[0]+nx,a[1]+nz],[b[0]+nx,b[1]+nz],[b[0]-nx,b[1]-nz],[a[0]-nx,a[1]-nz]];
          const colour=layer==='rail'?[.31,.35,.36]:profile.foot?[.28,.31,.30]:profile.unsealed?[.27,.23,.18]:[.065,.085,.10];
          drape([ring[0],ring[1],ring[2]],colour,.06,'roadTriangles');drape([ring[0],ring[2],ring[3]],colour,.06,'roadTriangles');
        }
      }else if(layer==='landuse'){
        const material=landcoverAppearance(p);
        for(const mesh of p['soma:mesh53']||[])for(const t of mesh.trianglesL93)drape(t.map(local),material.colour,.025,'landuseTriangles');
      }else if(layer==='hydrography'){
        const explicit=typeof p.ele==='number'?p.ele:typeof p.ele==='string'&&/^-?\d+(?:\.\d+)?$/.test(p.ele.trim())?Number(p.ele):null;
        const sea=['sea','harbour','bay'].includes(String(p.water||''))||p.natural==='bay';
        const level=Number.isFinite(explicit)?explicit:sea?0:null;
        for(const mesh of p['soma:mesh53']||[])for(const t of mesh.trianglesL93){
          if(level!==null)triangle(...t.map(q=>{const l=local(q);return[l[0],level,l[1]];}),[.025,.14,.18],'waterTriangles',true);
          else{const before=counts.waterTriangles;drape(t.map(local),[.035,.16,.19],.035,'waterTriangles');counts.drapedWaterTriangles+=counts.waterTriangles-before;}
        }
      }
    }
    return {vertices:new Float32Array(values),counts,boundsL93:bounds,centerL93,geometryBytes:values.length*4,
      heightPolicy:'OSM explicit height, then source-bound IGN reference; eaves use an unsurveyed flat roof, other missing heights are labelled estimates',
      facadePolicy:'interpreted cyberpunk windows, no physical navigation or collision claim',
      landscapePolicy:'source landcover colours are interpreted; inland water without a declared level is a visual footprint draped only on valid DEM faces; sea, harbour and bay retain a conventional 0 m visual level, not a water-level survey'};
  }
  const API={buildTile,buildTerrainTile,landcoverAppearance};root.__SOMA_METRO_VIEW_CORE__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
