/* Source-axis route analysis across a bounded, endpoint-preserving corridor.
 * No DOM, network owner, campaign state, physical controller or free connector.
 * The caller supplies the original, hash-pinned core63 and a bounded byte reader.
 */
(function(root){
  'use strict';
  const CORE_SHA='d2dc3ea29f653a066e3a812b7db3b79c0c8bb81cb97319ad888618048f37d9ae';
  const BASELINE_SHA='f1a6ce4b5957f634ff9fdbfaccfcf11c9e0d22159d01758dd56e29513581a014';
  const ORIGIN=[892951.6480966414,6247274.566415883],HASH=/^[a-f0-9]{64}$/;
  const BAD=new Set(['__proto__','prototype','constructor']),EPS=1e-6;
  const DEFAULTS=Object.freeze({maxCells:96,maxNodes:24000,maxEdges:32000,maxTurns:4000,
    maxEncodedBytes:4*1024*1024,maxDecodedBytes:8*1024*1024,maxAssetEncodedBytes:512*1024,
    maxAssetDecodedBytes:2*1024*1024,maxResidentBytes:128*1024*1024,memoryFactor:8,
    maxExpanded:120000,maxMilliseconds:6000,corridorM:75,maxAxisDistanceM:10});
  const LIMITS={maxCells:192,maxNodes:48000,maxEdges:64000,maxTurns:8000,maxEncodedBytes:8*1024*1024,
    maxDecodedBytes:16*1024*1024,maxAssetEncodedBytes:1024*1024,maxAssetDecodedBytes:4*1024*1024,
    maxResidentBytes:128*1024*1024,memoryFactor:16,maxExpanded:240000,maxMilliseconds:10000,
    corridorM:500,maxAxisDistanceM:20};
  class PreviewError extends Error{constructor(code,message){super(message);this.name='RoutePreviewError';this.code=code;}}
  const fail=(code,message)=>{throw new PreviewError(code,message);};
  const plain=v=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&[Object.prototype,null].includes(Object.getPrototypeOf(v));
  const point=p=>plain(p)&&Number.isFinite(p.e)&&Number.isFinite(p.n);
  const dist=(a,b)=>Math.hypot(a.e-b.e,a.n-b.n);
  function canonical(v){
    if(v===null||typeof v==='string'||typeof v==='boolean')return JSON.stringify(v);
    if(typeof v==='number'&&Number.isFinite(v))return JSON.stringify(v);
    if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';
    if(plain(v))return '{'+Object.keys(v).sort().map(k=>{if(BAD.has(k))fail('invalid_data','Clé interdite.');return JSON.stringify(k)+':'+canonical(v[k]);}).join(',')+'}';
    fail('invalid_data','Valeur JSON invalide.');
  }
  const copy=v=>JSON.parse(canonical(v));
  function bytes(v){if(v instanceof Uint8Array)return v;if(v instanceof ArrayBuffer)return new Uint8Array(v);fail('invalid_data','Octets Uint8Array attendus.');}
  async function sha256(value){
    if(root.crypto?.subtle)return [...new Uint8Array(await root.crypto.subtle.digest('SHA-256',value))].map(n=>n.toString(16).padStart(2,'0')).join('');
    if(typeof require==='function')return require('node:crypto').createHash('sha256').update(value).digest('hex');
    fail('integrity','SHA256 indisponible.');
  }
  async function decodeAsset(data,encoding,{signal,maxDecodedBytes}){
    if(encoding==='json')return data;
    if(encoding!=='gzip-json'||typeof DecompressionStream!=='function')fail('decode','Décompression gzip indisponible.');
    const reader=new Blob([data]).stream().pipeThrough(new DecompressionStream('gzip')).getReader();
    const chunks=[];let size=0;
    const cancel=()=>{reader.cancel().catch(()=>{});};signal.addEventListener('abort',cancel,{once:true});
    try{while(true){if(signal.aborted)fail('cancelled','Analyse annulée.');const {value,done}=await reader.read();if(done)break;
      size+=value.byteLength;if(size>maxDecodedBytes)fail('decoded_budget','Budget de décompression atteint.');chunks.push(value);}
      const out=new Uint8Array(size);let offset=0;for(const part of chunks){out.set(part,offset);offset+=part.length;}return out;
    }finally{signal.removeEventListener('abort',cancel);try{await reader.cancel();}catch{}reader.releaseLock();}
  }
  function descriptor(v){
    if(!plain(v)||typeof v.path!=='string'||v.path.length>1000||! /^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(v.path)||
      v.path.includes('//')||v.path.split('/').some(p=>!p||p==='.'||p==='..')||!HASH.test(v.sha256)||
      !Number.isSafeInteger(v.bytes)||v.bytes<=0||!['json','gzip-json'].includes(v.encoding)||
      v.decodedBytes!==undefined&&(!Number.isSafeInteger(v.decodedBytes)||v.decodedBytes<=0))fail('manifest','Descripteur NAV invalide.');
    return Object.freeze({path:v.path,sha256:v.sha256,bytes:v.bytes,encoding:v.encoding,
      ...(v.decodedBytes===undefined?{}:{decodedBytes:v.decodedBytes})});
  }
  function settings(input={}){
    if(!plain(input)||Object.keys(input).some(k=>!Object.hasOwn(DEFAULTS,k)))fail('budget','Budget inconnu.');
    const b={...DEFAULTS,...input};for(const [k,v]of Object.entries(b))if(!Number.isFinite(v)||v<=0||v>LIMITS[k]||
      (!['corridorM','maxAxisDistanceM'].includes(k)&&!Number.isSafeInteger(v)))fail('budget','Budget invalide : '+k);
    if(b.memoryFactor<8||b.maxDecodedBytes*b.memoryFactor>b.maxResidentBytes||b.maxExpanded<24)fail('budget','Comptabilisation mémoire ou recherche insuffisante.');return Object.freeze(b);
  }
  function cellGrid(id){
    if(typeof id!=='string')return null;
    let m=id.match(/^V52-MC-([1-5])([1-5])$/);if(m)return {x:Number(m[2])-3,y:Number(m[1])-3};
    m=id.match(/^V52-MC-([EW])(\d{2,4})-([NS])(\d{2,4})$/);
    return m?{x:(m[1]==='W'?-1:1)*Number(m[2]),y:(m[3]==='N'?-1:1)*Number(m[4])}:null;
  }
  function catalogue(world,b){
    if(!plain(world)||world.schema!=='soma-metropole/world-manifest/1'||world.crs!=='EPSG:2154'||world.units!=='m'||world.cellSize!==250||
      !Array.isArray(world.origin)||world.origin.length!==2||world.origin.some((v,i)=>!Number.isFinite(v)||Math.abs(v-ORIGIN[i])>EPS)||
      !HASH.test(world.source?.sha256)||!HASH.test(world.sourcePackSHA256)||!HASH.test(world.nativeTopologySHA256)||
      world.coverageExplicitPartial!==true||world.physicalMovementReady!==false||world.campaignRoutingActivated!==false||
      !Array.isArray(world.tiles)||world.tiles.length>100000)fail('manifest','Monde NAV préparé incompatible.');
    const c=world.navigationCore;
    if(c?.scriptId!=='soma-v63-nav-core'||c.version!=='0.63.0'||c.sha256!==CORE_SHA||c.baselineSHA256!==BASELINE_SHA)
      fail('core','Empreinte du moteur NAV incompatible.');
    const tiles=new Map(),positions=new Set(),encoder=new TextEncoder();let metadataBytes=0;
    for(const t of world.tiles){
      if(!t.navigation)continue;
      const grid=cellGrid(t.cellId);
      if(!grid||grid.x!==t.gridX||grid.y!==t.gridY||!Number.isSafeInteger(t.gridX)||!Number.isSafeInteger(t.gridY)||
        !HASH.test(t.contentSHA256)||!Array.isArray(t.boundsL93)||t.boundsL93.length!==4||!t.boundsL93.every(Number.isFinite)||
        t.terrainOnly===true||tiles.has(t.cellId)||positions.has(t.gridX+':'+t.gridY))fail('manifest','Cellule NAV invalide ou dupliquée.');
      const e=ORIGIN[0]+t.gridX*250,n=ORIGIN[1]-t.gridY*250;
      if([e-125,n-125,e+125,n+125].some((v,i)=>Math.abs(v-t.boundsL93[i])>.001))fail('manifest','Emprise NAV décalée.');
      const tile=Object.freeze({cellId:t.cellId,gridX:t.gridX,gridY:t.gridY,contentSHA256:t.contentSHA256,
        boundsL93:Object.freeze(t.boundsL93.slice()),navigation:descriptor(t.navigation)});
      metadataBytes+=encoder.encode(JSON.stringify(tile)).byteLength;
      if(metadataBytes*2>b.maxResidentBytes)fail('catalogue_budget','Index NAV supérieur au budget résident.');
      tiles.set(t.cellId,tile);positions.add(t.gridX+':'+t.gridY);
    }
    return {tiles,sourcePbfSHA256:world.source.sha256,sourcePackSHA256:world.sourcePackSHA256,
      nativeTopologySHA256:world.nativeTopologySHA256,routingCoreSHA256:CORE_SHA,catalogueAccountedBytes:metadataBytes*2};
  }
  function projection(p,a,b){const dx=b.e-a.e,dy=b.n-a.n,l=dx*dx+dy*dy,t=l?Math.max(0,Math.min(1,((p.e-a.e)*dx+(p.n-a.n)*dy)/l)):0;
    return {e:a.e+dx*t,n:a.n+dy*t,t};}
  // Slab intersection with an expanded source cell. Never manufacture an edge
  // between cells: this selects files only; merge still requires native identity.
  function intersects(start,end,bounds,padding){
    let lo=0,hi=1;
    for(const [axis,min,max]of [['e',bounds[0]-padding,bounds[2]+padding],['n',bounds[1]-padding,bounds[3]+padding]]){
      const delta=end[axis]-start[axis];
      if(Math.abs(delta)<EPS){if(start[axis]<min||start[axis]>max)return false;continue;}
      let a=(min-start[axis])/delta,z=(max-start[axis])/delta;if(a>z)[a,z]=[z,a];
      lo=Math.max(lo,a);hi=Math.min(hi,z);if(lo>hi)return false;
    }
    return true;
  }
  function plan(index,start,end,b){
    const candidates=[];
    for(const tile of index.tiles.values()){
      if(!intersects(start,end,tile.boundsL93,Math.max(b.corridorM,b.maxAxisDistanceM)))continue;
      const center={e:(tile.boundsL93[0]+tile.boundsL93[2])/2,n:(tile.boundsL93[1]+tile.boundsL93[3])/2},q=projection(center,start,end);
      candidates.push({tile,along:q.t,distance:dist(center,q),spine:intersects(start,end,tile.boundsL93,b.maxAxisDistanceM)});
    }
    // Reserve every cell of the entire direct spine before buying lateral
    // coverage. Prefix truncation used to consume the budget near departure.
    candidates.sort((a,b)=>Number(b.spine)-Number(a.spine)||a.distance-b.distance||a.along-b.along||a.tile.cellId.localeCompare(b.tile.cellId));
    const selected=candidates.slice(0,b.maxCells),omitted=candidates.slice(b.maxCells);
    selected.sort((a,b)=>a.along-b.along||a.distance-b.distance||a.tile.cellId.localeCompare(b.tile.cellId));
    return {selected:selected.map(v=>v.tile),requested:candidates.length,spineCells:candidates.filter(v=>v.spine).length,
      uncoveredSpineCells:omitted.filter(v=>v.spine).map(v=>v.tile.cellId),omitted:omitted.map(v=>v.tile.cellId)};
  }
  function validateGraph(g,t,index,b,core){
    if(!plain(g)||g.schema!=='soma/navigation-source/1'||g.sourcePbfSHA256!==index.sourcePbfSHA256||
      g.sourcePackSHA256!==index.sourcePackSHA256||g.nativeTopologySHA256!==index.nativeTopologySHA256||
      g.routingCoreSHA256!==CORE_SHA||!plain(g.cellHashes)||Object.keys(g.cellHashes).length!==1||g.cellHashes[t.cellId]!==t.contentSHA256||
      !plain(g.sourceStatus)||g.sourceStatus.nativeNodeIdentity!==true||g.sourceStatus.vectorConstrained!==true||
      g.sourceStatus.nodeTagsComplete!==true||g.sourceStatus.physicalAccessibilityVerified!==false||
      g.sourceStatus.physicalMovementReady!==false||g.sourceStatus.campaignRoutingActivated!==false||
      !Array.isArray(g.nodes)||!Array.isArray(g.edges)||!Array.isArray(g.turns)||g.nodes.length>b.maxNodes||g.edges.length>b.maxEdges||g.turns.length>b.maxTurns||
      !Array.isArray(g.edgeSources)||g.edgeSources.length!==g.edges.length||!Array.isArray(g.bicycleMasks)||g.bicycleMasks.length!==g.edges.length||
      !plain(g.nodeTags)||!plain(g.ways))fail('integrity','Graphe lié à une autre édition ou hors budget.');
    core.validate(g);
    const ids=new Set(g.nodes.map(n=>n[0]));
    for(const [id,e,n]of g.nodes)if(!/^(n\/[1-9]\d*|clip\/[1-9]\d*\/[1-9]\d*\/[01]\.\d{12})$/.test(id)||
      e<t.boundsL93[0]-.05||e>t.boundsL93[2]+.05||n<t.boundsL93[1]-.05||n>t.boundsL93[3]+.05)
      fail('integrity','Identité native ou coordonnées hors cellule.');
    for(const [id,tags]of Object.entries(g.nodeTags))if(!ids.has(id)||!id.startsWith('n/')||!plain(tags))fail('integrity','Attributs de nœud sans identité native.');
    for(const [id,w]of Object.entries(g.ways))if(!/^[1-9]\d*$/.test(id)||!plain(w)||!HASH.test(w.geometrySHA256))fail('integrity','Voie sans identité géométrique.');
    for(let i=0;i<g.edges.length;i++){
      const e=g.edges[i],s=g.edgeSources[i],a=g.nodes[e[0]],z=g.nodes[e[1]];
      if(!plain(s)||s.wayId!==e[2]||!Number.isSafeInteger(s.segmentIndex)||s.segmentIndex<1||e[7]!==s.segmentIndex||
        !Number.isFinite(s.t0)||!Number.isFinite(s.t1)||s.t0<0||s.t0>=s.t1||s.t1>1||
        s.startNative!==a[0].startsWith('n/')||s.endNative!==z[0].startsWith('n/')||
        Math.abs(Math.hypot(a[1]-z[1],a[2]-z[2])-e[3])>EPS||!Number.isInteger(g.bicycleMasks[i])||g.bicycleMasks[i]<0||g.bicycleMasks[i]>3||
        e[6].length!==1||e[6][0]!==t.cellId)fail('integrity','Origine native du segment invalide.');
      for(const [node,param]of [[a,s.t0],[z,s.t1]])if(node[0].startsWith('clip/')){
        const expected='clip/'+s.wayId+'/'+s.segmentIndex+'/'+param.toFixed(12);
        if(node[0]!==expected)fail('integrity','Identité de découpe divergente.');
      }
    }
  }
  function merge(graphs,index,b,check){
    const nodes=new Map(),ways=new Map(),tags=new Map(),edges=new Map(),turns=new Map(),hashes={};
    let originalNodes=0,originalEdges=0;
    for(const g of graphs){check();originalNodes+=g.nodes.length;originalEdges+=g.edges.length;
      if(originalNodes>b.maxNodes||originalEdges>b.maxEdges)fail('graph_budget','Budget des graphes résidents atteint.');
      for(const n of g.nodes){const old=nodes.get(n[0]);if(old&&Math.hypot(old[1]-n[1],old[2]-n[2])>EPS)fail('conflict','Coordonnées natives contradictoires.');nodes.set(n[0],n.slice());}
      for(const [id,w]of Object.entries(g.ways)){if(ways.has(id)&&canonical(ways.get(id))!==canonical(w))fail('conflict','Attributs de voie contradictoires.');ways.set(id,w);}
      for(const [id,t]of Object.entries(g.nodeTags)){if(tags.has(id)&&canonical(tags.get(id))!==canonical(t))fail('conflict','Attributs de nœud contradictoires.');tags.set(id,t);}
      Object.assign(hashes,g.cellHashes);
      for(let i=0;i<g.edges.length;i++){
        const e=g.edges[i],s=g.edgeSources[i],a=g.nodes[e[0]][0],z=g.nodes[e[1]][0];
        const key=canonical([a,z,e[2],s.segmentIndex,s.t0,s.t1]),old=edges.get(key);
        if(old){if(canonical(old.edge.slice(4,6))!==canonical(e.slice(4,6))||old.bike!==g.bicycleMasks[i]||canonical(old.source)!==canonical(s))fail('conflict','Permissions de segment contradictoires.');old.edge[6]=[...new Set([...old.edge[6],...e[6]])].sort();}
        else edges.set(key,{edge:[a,z,...e.slice(2,6),e[6].slice(),e[7]],source:s,bike:g.bicycleMasks[i]});
      }
      for(const r of g.turns){const key=r.id+'|'+r.via,old=turns.get(key);if(old&&canonical(old)!==canonical(r))fail('conflict','Restriction native contradictoire.');turns.set(key,r);}
      if(nodes.size>b.maxNodes||edges.size>b.maxEdges||turns.size>b.maxTurns)fail('graph_budget','Budget de fusion atteint.');
    }
    const ordered=[...nodes.values()].sort((a,b)=>a[0].localeCompare(b[0])),ids=new Map(ordered.map((n,i)=>[n[0],i])),merged=[],origins=[],bike=[];
    for(const [,{edge,source,bike:mask}]of [...edges].sort(([a],[b])=>a.localeCompare(b))){merged.push([ids.get(edge[0]),ids.get(edge[1]),...edge.slice(2)]);origins.push(source);bike.push(mask);}
    return {schema:'soma/navigation-source/1',version:'0.72.0',...index,tiles:undefined,nodes:ordered,edges:merged,
      ways:Object.fromEntries(ways),nodeTags:Object.fromEntries(tags),turns:[...turns.values()],cellHashes:hashes,edgeSources:origins,bicycleMasks:bike};
  }
  function anchor(router,g,input,options,selector){
    const candidates=Array.from(router.candidates(input,options),q=>({...q,key:canonical([g.edges[q.edge][2],g.edgeSources[q.edge].segmentIndex,g.edgeSources[q.edge].t0,g.edgeSources[q.edge].t1])}));
    if(selector!==undefined&&typeof selector!=='string')fail('position','Sélection de voie invalide.');
    if(selector!==undefined){const q=candidates.find(q=>q.key===selector);if(!q)fail('axis_unavailable','La voie choisie est absente ou incompatible.');return {selected:q,choices:candidates};}
    if(!candidates.length)fail('axis_unavailable','Aucun axe compatible assez proche.');
    const q=candidates[0],incidentId=v=>v.t<EPS?g.nodes[g.edges[v.edge][0]][0]:v.t>1-EPS?g.nodes[g.edges[v.edge][1]][0]:null;
    const id=incidentId(q);
    if(candidates.some(v=>v.edge!==q.edge&&v.distance<=q.distance+.25&&(!id||incidentId(v)!==id)))
      return {selected:null,choices:candidates};
    return {selected:q,choices:candidates};
  }
  function anchorInfo(q,g,input){return {key:q.key,input:{e:input.e,n:input.n},axis:{e:q.e,n:q.n},distanceMeters:q.distance,
    wayId:g.edges[q.edge][2],name:typeof g.ways[g.edges[q.edge][2]].name==='string'?g.ways[g.edges[q.edge][2]].name:null,steps:g.edges[q.edge][5]===1,segmentIndex:g.edgeSources[q.edge].segmentIndex,cellIds:g.edges[q.edge][6].slice(),connectionProvided:false};}
  function endpointCompatible(segment,q,g,start){
    if(!segment)return true;
    if(segment.edge===q.edge)return true;
    const a=g.edges[q.edge],id=q.t<EPS?g.nodes[a[0]][0]:q.t>1-EPS?g.nodes[a[1]][0]:null;
    if(!id)return false;
    const e=g.edges[segment.edge],p=start?segment.a:segment.b;
    return [e[0],e[1]].some(i=>g.nodes[i][0]===id&&Math.hypot(g.nodes[i][1]-p.e,g.nodes[i][2]-p.n)<EPS);
  }
  function create({world,routerCore,routerCoreSHA256,loadAsset,decode=decodeAsset,budgets={},now=()=>performance.now()}={}){
    if(routerCoreSHA256!==CORE_SHA||typeof routerCore?.validate!=='function'||typeof routerCore?.createRouter!=='function'||typeof routerCore?.project!=='function')fail('core','Le moteur original vérifié est requis.');
    if(typeof loadAsset!=='function'||typeof decode!=='function'||typeof now!=='function')fail('configuration','Lecteur borné et horloge requis.');
    const defaults=settings(budgets),index=catalogue(world,defaults);let busy=false,controller=null,last=null,residentGraphs=0;
    async function preview(request){
      if(busy)fail('busy','Une analyse est déjà en cours.');
      busy=true;controller=new AbortController();const active=controller,started=now();let timer,externalAbort;
      const stage=request?.corridorStage===1?1:0;
      // Expansion is a fresh, explicit analysis: no graph survives an attempt.
      const b=stage===1?settings({...defaults,maxCells:Math.min(192,defaults.maxCells*2),corridorM:Math.min(500,Math.max(250,defaults.corridorM*2)),
        maxNodes:Math.min(48000,defaults.maxNodes*2),maxEdges:Math.min(64000,defaults.maxEdges*2),maxExpanded:Math.min(240000,defaults.maxExpanded*2)}):defaults;
      const coverage={requestedCells:0,selectedCells:[],loadedCells:[],missingCells:[],omittedCells:[],completeRequestedSector:false,corridorStage:stage,corridorMeters:b.corridorM,spineCells:0,uncoveredSpineCells:[]};
      const resources={encodedBytes:0,decodedBytes:0,catalogueAccountedBytes:index.catalogueAccountedBytes,
        accountedResidentBytes:index.catalogueAccountedBytes,nodes:0,edges:0,expanded:0};
      const base={schema:'soma-metropole/route-preview/1',sourcePbfSHA256:index.sourcePbfSHA256,sourcePackSHA256:index.sourcePackSHA256,
        nativeTopologySHA256:index.nativeTopologySHA256,routingCoreSHA256:CORE_SHA,
        physicalAccessibilityVerified:false,physicalMovementReady:false,campaignRoutingActivated:false,
        searchScope:'bounded_source_corridor',globalDisconnectionProven:false,
        meaning:'Analyse des axes OSM du secteur chargé. Aucun accès physique, trottoir, dégagement ou raccord depuis le clic n’est garanti.'};
      const abortedCode=()=>active.signal.reason==='cancelled'||request?.signal?.aborted?'cancelled':'time_budget';
      const check=()=>{if(active.signal.aborted)fail(abortedCode(),'Analyse interrompue.');if(now()-started>=b.maxMilliseconds)fail('time_budget','Budget de temps atteint.');};
      const wait=async operation=>{
        check();let rejectAbort;
        const aborted=new Promise((_,reject)=>{rejectAbort=()=>reject(new PreviewError(abortedCode(),'Analyse interrompue.'));active.signal.addEventListener('abort',rejectAbort,{once:true});});
        try{const value=await Promise.race([operation,aborted]);check();return value;}finally{active.signal.removeEventListener('abort',rejectAbort);}
      };
      function result(status,code,extra={}){return {...base,status,code,route:null,coverage:copy(coverage),
        continuation:{available:stage===0&&status!=='route'&&status!=='refused'&&code!=='cancelled'&&code!=='axis_ambiguous',nextStage:stage===0?1:null,requiresExplicitRequest:true},resources:{...resources,elapsedMilliseconds:Math.max(0,now()-started),
        maxResidentBytes:b.maxResidentBytes,memoryAccounting:'owned catalogue JSON bytes × 2 + decoded bytes × memoryFactor, including graph/router allowance; caller world and byte cache excluded; not a heap measurement',
        synchronousSearchBound:'core63 maxExpanded; elapsed deadline checked before and after the synchronous call'},...extra};}
      try{
        if(!plain(request)||!point(request.start)||!point(request.end)||!['foot','car'].includes(request.mode||'foot')||
          request.avoidSteps!==undefined&&typeof request.avoidSteps!=='boolean'||request.corridorStage!==undefined&&![0,1].includes(request.corridorStage)||request.signal!==undefined&&
          (!request.signal||typeof request.signal.addEventListener!=='function'||typeof request.signal.removeEventListener!=='function'))fail('position','Position, mode ou option invalide.');
        // Awaiting a reader must not let a caller change the chosen sector,
        // endpoints or source selections halfway through an analysis.
        request={start:{e:request.start.e,n:request.start.n},end:{e:request.end.e,n:request.end.n},mode:request.mode,
          avoidSteps:request.avoidSteps,maxAxisDistanceM:request.maxAxisDistanceM,startAxisKey:request.startAxisKey,
          endAxisKey:request.endAxisKey,corridorStage:stage,signal:request.signal};
        if(request.signal?.aborted)fail('cancelled','Analyse annulée.');
        externalAbort=()=>active.abort('cancelled');request.signal?.addEventListener('abort',externalAbort,{once:true});
        timer=setTimeout(()=>active.abort('time_budget'),b.maxMilliseconds);
        const axisDistance=request.maxAxisDistanceM??b.maxAxisDistanceM;
        if(!Number.isFinite(axisDistance)||axisDistance<=0||axisDistance>b.maxAxisDistanceM)fail('position','Distance à l’axe hors budget.');
        const sector=plan(index,request.start,request.end,b);check();coverage.requestedCells=sector.requested;
        coverage.selectedCells=sector.selected.map(t=>t.cellId);coverage.omittedCells=sector.omitted;
        coverage.spineCells=sector.spineCells;coverage.uncoveredSpineCells=sector.uncoveredSpineCells;
        if(sector.uncoveredSpineCells.length)return result('interrupted','corridor_cell_budget',{reason:'Le corridor entre les deux points dépasse le budget de cellules. Aucun préfixe trompeur chargé.'});
        // Descriptor preflight bounds IO and retains the arrival. Missing legacy
        // decodedBytes are accounted while reading, as in the original core.
        let plannedEncoded=0,plannedDecoded=0;
        for(const tile of sector.selected){const d=tile.navigation;plannedEncoded+=d.bytes;plannedDecoded+=d.decodedBytes||0;
          if(d.bytes>b.maxAssetEncodedBytes||d.decodedBytes>b.maxAssetDecodedBytes)return result('interrupted','asset_budget');}
        if(plannedEncoded>b.maxEncodedBytes)return result('interrupted','asset_budget');
        if(plannedDecoded>b.maxDecodedBytes)return result('interrupted','decoded_budget');
        if(index.catalogueAccountedBytes+plannedDecoded*b.memoryFactor>b.maxResidentBytes)return result('interrupted','resident_budget');
        if(!sector.selected.length)return result('unavailable','no_navigation_sector');
        const graphs=[];
        for(const tile of sector.selected){check();const d=tile.navigation;
          if(d.bytes>b.maxAssetEncodedBytes||d.bytes+resources.encodedBytes>b.maxEncodedBytes||
            d.decodedBytes!==undefined&&(d.decodedBytes>b.maxAssetDecodedBytes||d.decodedBytes+resources.decodedBytes>b.maxDecodedBytes))fail('asset_budget','Budget de fichiers atteint.');
          let encoded;
          try{encoded=bytes(await wait(loadAsset(d,{signal:active.signal,maxEncodedBytes:Math.min(d.bytes,b.maxAssetEncodedBytes),maxDecodedBytes:b.maxAssetDecodedBytes,cellId:tile.cellId})));}
          catch(error){if(error?.code==='missing'||error?.status===404){coverage.missingCells.push(tile.cellId);continue;}throw error;}
          if(encoded.byteLength!==d.bytes||await wait(sha256(encoded))!==d.sha256)fail('integrity','Taille ou SHA256 du fichier NAV incorrect.');
          resources.encodedBytes+=encoded.byteLength;
          const maximum=Math.min(b.maxAssetDecodedBytes,b.maxDecodedBytes-resources.decodedBytes),decoded=bytes(await wait(decode(encoded,d.encoding,{signal:active.signal,maxDecodedBytes:maximum})));
          if(decoded.byteLength>maximum||d.decodedBytes!==undefined&&decoded.byteLength!==d.decodedBytes)fail('decoded_budget','Taille décodée NAV hors budget.');
          resources.decodedBytes+=decoded.byteLength;resources.accountedResidentBytes=index.catalogueAccountedBytes+resources.decodedBytes*b.memoryFactor;
          if(resources.accountedResidentBytes>b.maxResidentBytes)fail('resident_budget','Budget résident atteint.');
          let g;try{g=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(decoded),(key,value)=>{if(BAD.has(key))fail('integrity','Clé JSON interdite.');return value;});}
          catch(error){if(error instanceof PreviewError)throw error;fail('integrity','JSON NAV invalide.');}
          validateGraph(g,tile,index,b,routerCore);check();graphs.push(g);residentGraphs=graphs.length;coverage.loadedCells.push(tile.cellId);
          resources.nodes+=g.nodes.length;resources.edges+=g.edges.length;
          if(resources.nodes>b.maxNodes||resources.edges>b.maxEdges)fail('graph_budget','Budget des graphes résidents atteint.');
        }
        coverage.completeRequestedSector=coverage.omittedCells.length===0&&coverage.missingCells.length===0;
        if(!graphs.length)return result('unavailable','no_loaded_navigation');
        const g=merge(graphs,index,b,check);check();const router=routerCore.createRouter(g);check();
        // core63 retries at most twelve endpoint pairs. It counts one failed
        // expansion beyond its cap; reserve that unit for every attempt.
        const options={mode:request.mode||'foot',avoidSteps:request.avoidSteps===true,maxSnap:axisDistance,maxExpanded:Math.floor(b.maxExpanded/12)-1};
        const start=anchor(router,g,request.start,options,request.startAxisKey),end=anchor(router,g,request.end,options,request.endAxisKey);
        if(!start.selected||!end.selected)return result('unavailable','axis_ambiguous',{axisChoices:{start:start.choices.map(q=>anchorInfo(q,g,request.start)),end:end.choices.map(q=>anchorInfo(q,g,request.end))}});
        const s=start.selected,t=end.selected,anchors={start:anchorInfo(s,g,request.start),end:anchorInfo(t,g,request.end)};
        // Query only the explicitly selected axis positions, never the clicks.
        // core63 may retry coincident crossing edges: validate its first/last
        // native incidence below instead of accepting such an alternative.
        const routed=router.route({e:s.e,n:s.n},{e:t.e,n:t.n},{...options,maxSnap:1e-7});check();
        resources.expanded=routed.expanded||0;
        if(!routed.ok)return result('interrupted',/budget/.test(routed.reason)?'search_budget':
          !coverage.completeRequestedSector?'corridor_incomplete':'no_route_in_loaded_network',{anchors,reason:routed.reason});
        if(routed.segments.length>16000)return result('interrupted','route_output_budget',{anchors,reason:'La restitution dépasse le budget de segments source.'});
        const sameEndpoint=()=>{
          if(s.edge===t.edge)return true;
          const id=q=>q.t<EPS?g.nodes[g.edges[q.edge][0]][0]:q.t>1-EPS?g.nodes[g.edges[q.edge][1]][0]:null;
          return id(s)!==null&&id(s)===id(t);
        };
        if(!endpointCompatible(routed.segments[0],s,g,true)||!endpointCompatible(routed.segments.at(-1),t,g,false)||
          dist(routed.startSnap,s)>EPS||dist(routed.endSnap,t)>EPS||!routed.segments.length&&(dist(s,t)>EPS||!sameEndpoint()))
          return result('interrupted','source_endpoint_conflict',{anchors,reason:'Le moteur a proposé une autre voie sans identité native commune. Aucun raccord accepté.'});
        const segments=Array.from(routed.segments,q=>{
          const edge=g.edges[q.edge],origin=g.edgeSources[q.edge],a={e:g.nodes[edge[0]][1],n:g.nodes[edge[0]][2]},z={e:g.nodes[edge[1]][1],n:g.nodes[edge[1]][2]};
          return {a:{e:q.a.e,n:q.a.n},b:{e:q.b.e,n:q.b.n},wayId:edge[2],name:typeof g.ways[edge[2]].name==='string'?g.ways[edge[2]].name:null,
            segmentIndex:origin.segmentIndex,sourceT0:origin.t0+(origin.t1-origin.t0)*routerCore.project(q.a,a,z).t,
            sourceT1:origin.t0+(origin.t1-origin.t0)*routerCore.project(q.b,a,z).t,steps:edge[5]===1,cellIds:edge[6].slice()};
        });
        return result('route','source_axis_route',{anchors,route:{mode:options.mode,avoidSteps:options.avoidSteps,lengthMeters:routed.lengthMeters,
          points:Array.from(routed.points,p=>({e:p.e,n:p.n})),segments,cells:Array.from(routed.cells),completeBetweenAnchors:true,
          partialNetwork:true,physicalAccessibilityVerified:false},restrictionsRetained:g.turns.length});
      }catch(error){
        if(error instanceof PreviewError)return result(['integrity','conflict','invalid_data'].includes(error.code)?'refused':'interrupted',error.code,{reason:error.message});
        return result('refused','load_or_validation_failure',{reason:String(error?.message||error).slice(0,500)});
      }finally{clearTimeout(timer);request?.signal?.removeEventListener?.('abort',externalAbort);controller=null;busy=false;residentGraphs=0;
        last={loadedCells:coverage.loadedCells.length,...resources,elapsedMilliseconds:Math.max(0,now()-started)};}
    }
    return Object.freeze({preview,cancel(){controller?.abort('cancelled');},snapshot(){return {busy,catalogueCells:index.tiles.size,
      catalogueAccountedBytes:index.catalogueAccountedBytes,residentGraphs,
      retention:'No graph cache between analyses; caller owns encoded byte caches.',budgets:{...defaults},last:last&&{...last}};}});
  }
  const API=Object.freeze({VERSION:'0.72.0',CORE_SHA256:CORE_SHA,BASELINE_SHA256:BASELINE_SHA,DEFAULTS,create});
  root.__SOMA_ROUTE72_CORE__=API;root.__SOMA_ROUTE70_CORE__=API;if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof globalThis!=='undefined'?globalThis:this);
