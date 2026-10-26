/* Metric metadata indices only. Input world/contours remain read-only, and no
 * tile, elevation or architectural coverage is synthesized by these queries.
 * Rebuild this index atomically when the source world changes.
 */
(function(root){
  'use strict';
  const ORIGIN=[892951.6480966414,6247274.566415883],CELL_SIZE=250;
  const CELL=/^V52-MC-(?:[1-5][1-5]|[EW][0-9]{2,4}-[NS][0-9]{2,4})$/;
  const fail=message=>{throw new Error('World index: '+message);};
  const finitePoint=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
  const key=(x,y)=>x+':'+y;
  const centre=t=>[(t.boundsL93[0]+t.boundsL93[2])/2,(t.boundsL93[1]+t.boundsL93[3])/2];

  function gridForId(id){
    if(typeof id!=='string'||!CELL.test(id))return null;
    const old=id.match(/^V52-MC-([1-5])([1-5])$/);
    if(old)return{x:Number(old[2])-3,y:Number(old[1])-3};
    const q=id.match(/^V52-MC-([EW])([0-9]{2,4})-([NS])([0-9]{2,4})$/);
    return{x:Number(q[2])*(q[1]==='W'?-1:1),y:Number(q[4])*(q[3]==='N'?-1:1)};
  }

  function flightLayers(tile){
    if(!tile?.terrain)return null;
    return tile.terrainOnly===true?(tile.vector===null?['terrain']:null):(tile.vector?['vector','terrain']:null);
  }

  function terrainStatus(tile){
    return !tile?.terrain?'missing':tile.terrain.complete===true?'complete':tile.terrain.complete===false?'partial':'unknown';
  }

  function inside(point,ring){
    let yes=false;
    for(let i=0,j=ring.length-1;i<ring.length;j=i++){
      const a=ring[i],b=ring[j];
      if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;
    }
    return yes;
  }

  function createWorldIndex(manifest,options={}){
    if(manifest?.schema!=='soma-metropole/world-manifest/1'||manifest.crs!=='EPSG:2154'||manifest.units!=='m'||
        manifest.cellSize!==CELL_SIZE||!finitePoint(manifest.origin)||manifest.origin.some((n,i)=>Math.abs(n-ORIGIN[i])>1e-6)||
        !Array.isArray(manifest.tiles)||manifest.tiles.length>100000)fail('incompatible metric manifest');
    const maxRadius=options.maxRadius??3,maxSearchRadius=options.maxSearchRadius??4000,bucketSize=options.communeBucketSize??2000;
    const maxBucketReferences=options.maxCommuneBucketReferences??250000;
    if(!Number.isInteger(maxRadius)||maxRadius<0||maxRadius>3||!Number.isFinite(maxSearchRadius)||maxSearchRadius<2000||maxSearchRadius>10000||
        !Number.isFinite(bucketSize)||bucketSize<250||bucketSize>10000||!Number.isInteger(maxBucketReferences)||maxBucketReferences<=0||maxBucketReferences>1000000)
      fail('invalid query/index budgets');
    if(options.projectWGS84!==undefined&&typeof options.projectWGS84!=='function')fail('projectWGS84 must be a function');
    const tiles=manifest.tiles,byGrid=new Map(),byId=new Map(),stats=options.instrument?{cellQueries:0,gridLookups:0,communeQueries:0,polygonTests:0}:null;
    let flightCount=0,terrainOnlyCount=0,partialCount=0;
    const bounds=[Infinity,Infinity,-Infinity,-Infinity];
    for(let rank=0;rank<tiles.length;rank++){
      const tile=tiles[rank],grid=gridForId(tile?.cellId);
      if(!grid||!Number.isInteger(tile.gridX)||!Number.isInteger(tile.gridY)||grid.x!==tile.gridX||grid.y!==tile.gridY||
          byId.has(tile.cellId)||byGrid.has(key(grid.x,grid.y)))fail('duplicate or inconsistent cell identity/grid');
      const e=ORIGIN[0]+grid.x*250,n=ORIGIN[1]-grid.y*250,expected=[e-125,n-125,e+125,n+125];
      if(!Array.isArray(tile.boundsL93)||tile.boundsL93.length!==4||tile.boundsL93.some((v,i)=>!Number.isFinite(v)||Math.abs(v-expected[i])>1e-6))fail('shifted cell bounds');
      if(tile.terrainOnly===true&&(tile.vector!==null||tile.contentSHA256!==null||!tile.terrain||tile.surfaces!=null||tile.navigation!=null))fail('contradictory terrain-only cell');
      byGrid.set(key(grid.x,grid.y),rank);byId.set(tile.cellId,rank);
      flightCount+=!!flightLayers(tile);terrainOnlyCount+=tile.terrainOnly===true;partialCount+=terrainStatus(tile)==='partial';
      bounds[0]=Math.min(bounds[0],tile.boundsL93[0]);bounds[1]=Math.min(bounds[1],tile.boundsL93[1]);
      bounds[2]=Math.max(bounds[2],tile.boundsL93[2]);bounds[3]=Math.max(bounds[3],tile.boundsL93[3]);
    }
    const communes=options.communes??[],byCode=new Map(),polygons=[],buckets=new Map();
    let bucketReferences=0,vertices=0;
    if(!Array.isArray(communes)||communes.length>128)fail('commune index exceeds its budget');
    const projected=[];
    for(let rank=0;rank<communes.length;rank++){
      const commune=communes[rank];
      if(typeof commune?.code!=='string'||!/^[0-9]{5}$/.test(commune.code)||byCode.has(commune.code))fail('invalid or duplicated commune code');
      byCode.set(commune.code,rank);
      let rings=commune.polygons;
      if(rings===undefined){
        const geometry=commune.geometry;
        if(geometry==null)rings=[];
        else{
          if(typeof options.projectWGS84!=='function'||!['Polygon','MultiPolygon'].includes(geometry.type))fail('explicit WGS84 projection is required');
          const input=geometry.type==='Polygon'?[geometry.coordinates]:geometry.coordinates;
          if(!Array.isArray(input))fail('invalid commune polygons');
          rings=input.map(poly=>poly.map(ring=>ring.map(point=>options.projectWGS84(point))));
        }
      }
      if(!Array.isArray(rings))fail('invalid metric commune polygons');
      const own=[];
      for(const polygon of rings){
        if(!Array.isArray(polygon)||!polygon.length)fail('empty commune polygon');
        const box=[Infinity,Infinity,-Infinity,-Infinity];
        for(const ring of polygon){
          if(!Array.isArray(ring)||ring.length<4||!finitePoint(ring[0])||!finitePoint(ring[ring.length-1])||
              ring[0].some((v,i)=>v!==ring[ring.length-1][i]))fail('open or invalid commune ring');
          for(const point of ring){
            if(!finitePoint(point))fail('non-finite metric commune point');
            if(++vertices>1000000)fail('commune vertex budget exceeded');
            box[0]=Math.min(box[0],point[0]);box[1]=Math.min(box[1],point[1]);box[2]=Math.max(box[2],point[0]);box[3]=Math.max(box[3],point[1]);
          }
        }
        const id=polygons.length;polygons.push({rank,rings:polygon,bounds:box});own.push(id);
        const x0=Math.floor(box[0]/bucketSize),x1=Math.floor(box[2]/bucketSize),y0=Math.floor(box[1]/bucketSize),y1=Math.floor(box[3]/bucketSize);
        const references=(x1-x0+1)*(y1-y0+1);
        if(![x0,x1,y0,y1].every(Number.isSafeInteger)||!Number.isSafeInteger(references)||references<=0||bucketReferences+references>maxBucketReferences)fail('commune bucket budget exceeded');
        bucketReferences+=references;
        for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
          const name=key(x,y);let list=buckets.get(name);if(!list)buckets.set(name,list=[]);list.push(id);
        }
      }
      projected.push(own);
    }

    function lookup(x,y){if(stats)stats.gridLookups++;const rank=byGrid.get(key(x,y));return rank===undefined?null:tiles[rank];}
    function gridAt(e,n){
      if(!Number.isFinite(e)||!Number.isFinite(n))return null;
      const x=Math.round((e-ORIGIN[0])/250),y=Math.round((ORIGIN[1]-n)/250);
      // No indexed ID exceeds 9999. Reject extreme inputs before bounded
      // integer loops, where incrementing huge floating values would stall.
      return Number.isSafeInteger(x)&&Number.isSafeInteger(y)&&Math.abs(x)<=1000000&&Math.abs(y)<=1000000?{x,y}:null;
    }
    function cellAt(e,n){if(stats)stats.cellQueries++;const grid=gridAt(e,n);return grid?lookup(grid.x,grid.y):null;}
    function desiredTiles(e,n,radius=Math.min(1,maxRadius)){
      if(!Number.isInteger(radius)||radius<0||radius>maxRadius)fail('neighbourhood radius exceeds its budget');
      const grid=gridAt(e,n);if(!grid)return[];
      const result=[];
      for(let y=grid.y-radius;y<=grid.y+radius;y++)for(let x=grid.x-radius;x<=grid.x+radius;x++){
        const tile=lookup(x,y);if(flightLayers(tile))result.push(tile);
      }
      // Exact compatibility with the old stable filter/sort: equal distances
      // retain the original manifest order, including historical aliases.
      return result.sort((a,b)=>((a.gridX-grid.x)**2+(a.gridY-grid.y)**2)-((b.gridX-grid.x)**2+(b.gridY-grid.y)**2)||byId.get(a.cellId)-byId.get(b.cellId));
    }
    function polygonContains(id,e,n){
      const poly=polygons[id],b=poly.bounds;
      if(e<b[0]||e>b[2]||n<b[1]||n>b[3])return false;
      if(stats)stats.polygonTests++;
      return inside([e,n],poly.rings[0])&&!poly.rings.slice(1).some(ring=>inside([e,n],ring));
    }
    function containsCommune(code,e,n){
      const rank=byCode.get(code);return rank!==undefined&&Number.isFinite(e)&&Number.isFinite(n)&&projected[rank].some(id=>polygonContains(id,e,n));
    }
    function communeAt(e,n){
      if(stats)stats.communeQueries++;
      if(!Number.isFinite(e)||!Number.isFinite(n))return null;
      const candidates=buckets.get(key(Math.floor(e/bucketSize),Math.floor(n/bucketSize)))||[];
      for(const id of candidates)if(polygonContains(id,e,n))return communes[polygons[id].rank];
      return null;
    }
    function nearestTile(e,n,{radiusM=2000,predicate=null}={}){
      if(!Number.isFinite(radiusM)||radiusM<=0||radiusM>maxSearchRadius||predicate!==null&&typeof predicate!=='function')fail('nearest-cell search exceeds its budget');
      const grid=gridAt(e,n);if(!grid)return null;
      const r=Math.ceil(radiusM/250)+1;let best=null,distance=radiusM,rank=Infinity;
      for(let y=grid.y-r;y<=grid.y+r;y++)for(let x=grid.x-r;x<=grid.x+r;x++){
        const tile=lookup(x,y);if(!flightLayers(tile))continue;
        const p=centre(tile),d=Math.hypot(p[0]-e,p[1]-n),order=byId.get(tile.cellId);
        if(d>=radiusM||d>distance||d===distance&&order>=rank||predicate&&!predicate(tile,p))continue;
        best=tile;distance=d;rank=order;
      }
      return best;
    }
    function coverageAt(e,n){
      const tile=cellAt(e,n);
      return{tile,terrain:terrainStatus(tile),terrainOnly:tile?.terrainOnly===true,hasVector:!!tile?.vector,
        flightLayers:flightLayers(tile),pointTerrainSampled:false};
    }
    const destinations=new Map();
    for(const commune of communes){
      let anchor=commune.anchorL93;
      if(anchor==null&&finitePoint(commune.anchorWGS84)&&typeof options.projectWGS84==='function')anchor=options.projectWGS84(commune.anchorWGS84);
      if(anchor!=null&&!finitePoint(anchor))fail('invalid projected destination anchor');
      let point=anchor?anchor.slice():null,tile=point?cellAt(...point):null,reason='source-anchor',fallback=false;
      if(!point)reason='missing-projected-anchor';
      else if(!containsCommune(commune.code,...point)){point=null;tile=null;reason='anchor-outside-source-contour';}
      else if(!flightLayers(tile)){
        tile=nearestTile(...point,{radiusM:2000,predicate:(_,p)=>containsCommune(commune.code,...p)});
        point=tile?centre(tile):null;fallback=!!tile;reason=tile?'nearest-source-cell-in-commune':'no-flight-cell-within-2000m';
      }
      const result={code:commune.code,commune,available:!!point&&!!flightLayers(tile),point:point?Object.freeze(point):null,tile,
        reason,fallback,anchorSource:commune.anchorSource??null,terrain:terrainStatus(tile),pointTerrainSampled:false,
        displacementM:point&&anchor?Math.hypot(point[0]-anchor[0],point[1]-anchor[1]):null};
      destinations.set(commune.code,Object.freeze(result));
    }
    return Object.freeze({
      get(id){const rank=byId.get(id);return rank===undefined?null:tiles[rank];},gridAt,cellAt,desiredTiles,nearestTile,
      communeAt,containsCommune,coverageAt,destination:code=>destinations.get(code)||null,
      destinations:()=>Object.freeze([...destinations.values()]),
      snapshot:()=>({tiles:tiles.length,flightTiles:flightCount,terrainOnlyTiles:terrainOnlyCount,partialTerrainTiles:partialCount,
        gridEntries:byGrid.size,boundsL93:tiles.length?bounds.slice():null,communes:communes.length,communePolygons:polygons.length,
        communeVertices:vertices,communeBuckets:buckets.size,communeBucketReferences:bucketReferences,queries:stats?{...stats}:null})
    });
  }

  function createTargetTracker(index,{maxTargets=64}={}){
    if(typeof index?.get!=='function'||!Number.isInteger(maxTargets)||maxTargets<1||maxTargets>256)fail('invalid target tracker');
    let ids=[],active=new Map(),issued=new WeakSet(),generation=0,epoch=0,serial=0;
    function update(next,{force=false}={}){
      if(typeof force!=='boolean')fail('force must be boolean');
      if(!Array.isArray(next)||next.length>maxTargets||new Set(next).size!==next.length||next.some(id=>!index.get(id)))fail('unknown, duplicate or excessive targets');
      const set=new Set(next),changed=force||next.length!==ids.length||ids.some(id=>!set.has(id));
      const orderChanged=next.length!==ids.length||next.some((id,i)=>id!==ids[i]);
      const entering=force?next.slice():next.filter(id=>!active.has(id)),leaving=force?ids.slice():ids.filter(id=>!set.has(id));
      const retained=force?[]:next.filter(id=>active.has(id));
      if(changed){generation++;for(const id of leaving)active.delete(id);for(const id of entering)active.set(id,++serial);}
      ids=next.slice();return{changed,orderChanged,generation,epoch,ids:ids.slice(),entering,leaving,retained};
    }
    return Object.freeze({update,
      capture(id){if(!active.has(id))return null;const ticket=Object.freeze({id,epoch,serial:active.get(id)});issued.add(ticket);return ticket;},
      accepts(ticket){return!!ticket&&typeof ticket==='object'&&issued.has(ticket)&&ticket.epoch===epoch&&active.has(ticket.id)&&active.get(ticket.id)===ticket.serial;},
      reset(){const leaving=ids.slice();ids=[];active=new Map();issued=new WeakSet();generation++;epoch++;return{changed:true,generation,epoch,ids:[],entering:[],leaving,retained:[]};},
      snapshot:()=>({generation,epoch,ids:ids.slice(),active:active.size,maxTargets})
    });
  }
  const API=Object.freeze({createWorldIndex,createTargetTracker,gridForId,flightLayers,terrainStatus,inside});
  root.__SOMA_WORLD70_INDEX__=API;
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof globalThis!=='undefined'?globalThis:this);
