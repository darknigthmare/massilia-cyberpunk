/* Independent metropolitan flight. No campaign module, save key or navigation
 * controller is loaded. Vector/terrain readiness belongs to this viewer only.
 */
(function(root){
  'use strict';
  function safeWorldPath(value){
    return typeof value==='string'&&value.length<=1000&&/^[A-Za-z0-9][A-Za-z0-9._/-]*\.json$/.test(value)&&
      !value.split('/').some(part=>!part||part==='.'||part==='..');
  }
  function sceneRegistry(driver,budget=128*1024*1024){
    const meshes=new Map();let bytes=0;
    function detach(id){const old=meshes.get(id);if(!old)return false;driver.release(old.handle);meshes.delete(id);bytes-=old.geometry.geometryBytes;return true;}
    return {meshes,attach(id,geometry,token){
      if(!(geometry.vertices instanceof Float32Array)||geometry.vertices.length%9||geometry.geometryBytes!==geometry.vertices.byteLength)throw new TypeError('Invalid viewer geometry.');
      const old=meshes.get(id),required=bytes-(old?.geometry.geometryBytes||0)+geometry.geometryBytes;
      if(required>budget)throw new RangeError('Budget géométrique du survol atteint.');
      const handle=driver.upload(geometry.vertices);
      if(old)detach(id);meshes.set(id,{handle,geometry,token});bytes+=geometry.geometryBytes;return handle;
    },detach,prune(keep){for(const id of[...meshes.keys()])if(!keep.has(id))detach(id);},
      clear(){for(const id of[...meshes.keys()])detach(id);},snapshot(){return{meshes:meshes.size,bytes,maxBytes:budget};}};
  }
  function desiredTiles(manifest,e,n,radius=1){
    const x=Math.round((e-manifest.origin[0])/250),y=Math.round((manifest.origin[1]-n)/250);
    return manifest.tiles.filter(t=>flightLayers(t)&&Math.abs(t.gridX-x)<=radius&&Math.abs(t.gridY-y)<=radius)
      .sort((a,b)=>(a.gridX-x)**2+(a.gridY-y)**2-((b.gridX-x)**2+(b.gridY-y)**2));
  }
  function flightLayers(tile){
    if(!tile?.terrain)return null;
    if(tile.terrainOnly===true)return tile.vector===null?['terrain']:null;
    return tile.vector?['vector','terrain']:null;
  }
  function requestFlightTiles(store,tiles){
    const ids=tiles.map(t=>t.cellId);
    // One request owns cancellation/protection for the whole mixed target.
    // Vector callers immediately extend the same in-flight tasks. Terrain-only
    // tasks never request a vector or vector-derived layer.
    const terrain=store.request(ids,{layers:['terrain'],protectedIds:ids});
    const results=Promise.allSettled(tiles.map(t=>store.load(t.cellId,{layers:flightLayers(t)})));
    return Promise.all([terrain,results]).then(([,outcomes])=>outcomes);
  }
  const abortError=()=>Object.assign(new Error('Chargement du monde remplacé ou annulé.'),{name:'AbortError'});
  function parseJSON(data){
    return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(data),(key,value)=>{if(['__proto__','prototype','constructor'].includes(key))throw new Error('Clé JSON interdite.');return value;});
  }
  async function readBytes(url,maximum,{fetcher=root.fetch.bind(root),signal}={}){
    if(signal?.aborted)throw abortError();
    const response=await fetcher(url,{credentials:'same-origin',redirect:'error',signal});
    if(signal?.aborted){try{await response.body?.cancel();}catch{}throw abortError();}
    if(!response.ok){try{await response.body?.cancel();}catch{}throw Object.assign(new Error('Données indisponibles : HTTP '+response.status),{status:response.status});}
    if(response.redirected){try{await response.body?.cancel();}catch{}throw new Error('Redirection de données interdite.');}
    if(!response.body)throw new Error('Réponse de données sans contenu.');
    const reader=response.body.getReader(),chunks=[];let size=0;
    const cancel=()=>{reader.cancel(abortError()).catch(()=>{});};signal?.addEventListener('abort',cancel,{once:true});
    try{while(true){if(signal?.aborted)throw abortError();const {done,value}=await reader.read();if(signal?.aborted)throw abortError();if(done)break;size+=value.byteLength;if(size>maximum)throw new Error('Le fichier dépasse le budget de lecture.');chunks.push(value);}}
    catch(error){try{await reader.cancel(error);}catch{}throw error;}
    finally{signal?.removeEventListener('abort',cancel);reader.releaseLock();}
    const data=new Uint8Array(size);let at=0;for(const chunk of chunks){data.set(chunk,at);at+=chunk.byteLength;}return data;
  }
  async function readJSON(url,maximum=128*1024*1024,fetcher=root.fetch.bind(root),signal){
    return parseJSON(await readBytes(url,maximum,{fetcher,signal}));
  }
  async function loadBuildingParts(manifest,manifestURL,{fetcher=root.fetch.bind(root),signal,embeddedProof,sha256}={}){
    if(signal?.aborted)throw abortError();
    const descriptor=manifest.buildingParts;
    if(descriptor==null)return embeddedProof?.sourceSHA256===manifest.source.sha256?embeddedProof:null;
    const hash=value=>typeof value==='string'&&/^[a-f0-9]{64}$/i.test(value);
    if(typeof descriptor!=='object'||Array.isArray(descriptor)||!safeWorldPath(descriptor.path)||descriptor.encoding!=='json'||
      !Number.isSafeInteger(descriptor.bytes)||descriptor.bytes<=0||descriptor.bytes>64*1024*1024||
      !hash(descriptor.sha256)||!hash(descriptor.proofSHA256)||!hash(descriptor.sourcePbfSHA256)||
      descriptor.sourcePbfSHA256!==manifest.source.sha256||!hash(manifest.sourcePackSHA256)||typeof sha256!=='function')
      throw new Error('Descripteur de parties de bâtiments invalide ou lié à une autre source.');
    const base=new URL('.',manifestURL),url=new URL(descriptor.path,base);
    if(!['http:','https:'].includes(base.protocol)||url.origin!==base.origin||!url.pathname.startsWith(base.pathname))throw new Error('Le fichier de parties doit rester dans le dossier du manifeste.');
    let bytes;
    try{bytes=await readBytes(url,descriptor.bytes,{fetcher,signal});}
    catch(error){error.stage='buildingParts';throw error;}
    if(bytes.byteLength!==descriptor.bytes||await sha256(bytes)!==descriptor.sha256)throw new Error('SHA256 ou taille du fichier de parties incorrect.');
    if(signal?.aborted)throw abortError();
    const proof=parseJSON(bytes);
    if(proof?.schema!=='soma-massilia/building-parts-proof/1'||proof.proofSHA256!==descriptor.proofSHA256||
      proof.sourceSHA256!==manifest.source.sha256||proof.selectionProvenance?.vectorManifestSHA256!==manifest.sourcePackSHA256)
      throw new Error('La preuve de parties ne correspond pas à cette édition géographique.');
    return proof;
  }
  function atomicWorldLoader({prepare,commit}){
    let nonce=0,controller=null;
    return {async load(argument){
      const current=++nonce;controller?.abort();const active=new AbortController();controller=active;
      try{const prepared=await prepare(argument,{signal:active.signal,nonce:current});
        if(current!==nonce||active.signal.aborted)throw abortError();return commit(prepared,argument);
      }catch(error){if(current!==nonce||active.signal.aborted)throw abortError();throw error;}
      finally{if(controller===active)controller=null;}
    },cancel(){nonce++;controller?.abort();controller=null;}};
  }
  const API={safeWorldPath,sceneRegistry,desiredTiles,flightLayers,requestFlightTiles,readJSON,loadBuildingParts,atomicWorldLoader};
  if(typeof module!=='undefined'&&module.exports)module.exports=API;
  root.__SOMA_METRO_VIEWER_UTILS__=API;
  if(!root.document)return;

  const $=id=>document.getElementById(id),G=root.__SOMA_V53_CORE__,T=root.__SOMA_TERRAIN56_CORE__,
    F=root.__SOMA_FIDELITY59_CORE__,A=root.__SOMA_ARCH68_CORE__,S=root.__SOMA_STREAM69_CORE__,Geometry=root.__SOMA_METRO_VIEW_CORE__;
  const metadata=JSON.parse($('soma-viewer-data').textContent),embeddedParts=JSON.parse($('soma-viewer-parts').textContent);let parts=null;
  const errors=[],keys=new Set(),entries=new Map(),jobs=new Map();
  let store=null,manifest=null,manifestURL=null,mode='',generation=0,targetIds=new Set(),lastCell='',lastUpdate=0,lastHUD=0;
  let requestPromise=Promise.resolve(),worldPromise=Promise.resolve(),options={},mapProjection=null,mapDirty=true,frame=0,renderedFrames=0,buildFailures=0;
  const camera={e:892100,n:6247000,h:190,yaw:.35,pitch:-.55,speed:45};
  const communes=(metadata.territory?.communes||[]).map(c=>({...c,polygons:c.geometry?(c.geometry.type==='Polygon'?[c.geometry.coordinates]:c.geometry.coordinates).map(poly=>poly.map(ring=>ring.map(G.forward))):[]}));

  function logError(error){const message=error?.message||String(error);if(error?.name==='AbortError')return;errors.push(message);if(errors.length>30)errors.shift();$('loading').textContent=message;console.warn('Survol : '+message);}
  function fatal(error){if(error?.name==='AbortError')return;logError(error);$('error-message').textContent=error?.message||String(error);$('error').hidden=false;$('loading').textContent='';}
  function releaseMouse(){if(document.pointerLockElement)document.exitPointerLock();keys.clear();}
  function openDialog(id){releaseMouse();$(id).showModal();if(id==='map-dialog'){mapDirty=true;drawMap();}}

  function multiply(a,b){const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;}
  function perspective(aspect){const f=1/Math.tan(58*Math.PI/360),near=.5,far=12000,nf=1/(near-far),out=new Float32Array(16);out[0]=f/aspect;out[5]=f;out[10]=(far+near)*nf;out[11]=-1;out[14]=2*far*near*nf;return out;}
  function view(eye,forward){
    const z=forward.map(v=>-v),len=Math.hypot(z[0],z[2])||1,x=[z[2]/len,0,-z[0]/len],y=[z[1]*x[2],z[2]*x[0]-z[0]*x[2],-z[1]*x[0]];
    return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,
      -x.reduce((s,v,i)=>s+v*eye[i],0),-y.reduce((s,v,i)=>s+v*eye[i],0),-z.reduce((s,v,i)=>s+v*eye[i],0),1]);
  }
  function createRenderer(canvas){
    const gl=canvas.getContext('webgl2',{alpha:false,antialias:true,powerPreference:'high-performance'});
    if(!gl)throw new Error('WebGL 2 n’est pas disponible dans ce navigateur.');
    function shader(type,text){const object=gl.createShader(type);gl.shaderSource(object,text);gl.compileShader(object);if(!gl.getShaderParameter(object,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(object));return object;}
    const vertex=shader(gl.VERTEX_SHADER,`#version 300 es
precision highp float;in vec3 aPosition;in vec3 aNormal;in vec3 aColour;uniform mat4 uVP;uniform vec3 uTile;uniform vec3 uCamera;out vec3 colour;out float fog;
void main(){vec3 p=aPosition+uTile;gl_Position=uVP*vec4(p,1.0);vec3 n=length(aNormal)>.1?normalize(aNormal):vec3(0,1,0);float light=.5+.5*max(0.0,dot(n,normalize(vec3(-.35,.85,.28))));float emission=step(1.25,max(aColour.r,max(aColour.g,aColour.b)));colour=mix(aColour*light,clamp(aColour,0.0,1.0),emission);fog=smoothstep(550.0,2300.0,distance(p,uCamera));}`);
    const fragment=shader(gl.FRAGMENT_SHADER,`#version 300 es
precision highp float;in vec3 colour;in float fog;out vec4 pixel;void main(){pixel=vec4(mix(colour,vec3(.024,.055,.075),fog*.88),1.0);}`);
    const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
    const loc={vp:gl.getUniformLocation(program,'uVP'),tile:gl.getUniformLocation(program,'uTile'),camera:gl.getUniformLocation(program,'uCamera')};
    const attrib=[gl.getAttribLocation(program,'aPosition'),gl.getAttribLocation(program,'aNormal'),gl.getAttribLocation(program,'aColour')];
    const driver={upload(vertices){const vao=gl.createVertexArray(),buffer=gl.createBuffer();gl.bindVertexArray(vao);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);for(let i=0;i<3;i++){gl.enableVertexAttribArray(attrib[i]);gl.vertexAttribPointer(attrib[i],3,gl.FLOAT,false,36,i*12);}return{vao,buffer,count:vertices.length/9};},
      release(handle){gl.deleteBuffer(handle.buffer);gl.deleteVertexArray(handle.vao);}};
    const registry=sceneRegistry(driver),errorCodes=[];
    // Keep errors for QA: inspecting a snapshot must not consume and hide a
    // transient WebGL failure from later validation.
    function collectErrors(){for(let i=0;i<16;i++){const code=gl.getError();if(code===gl.NO_ERROR)break;if(!errorCodes.includes(code)&&errorCodes.length<32)errorCodes.push(code);}}
    gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.enable(gl.CULL_FACE);gl.cullFace(gl.BACK);
    return {gl,registry,errorCodes,draw(){
      const ratio=Math.min(root.devicePixelRatio||1,1.5),w=Math.max(1,Math.round(canvas.clientWidth*ratio)),h=Math.max(1,Math.round(canvas.clientHeight*ratio));
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
      gl.clearColor(.024,.055,.075,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);
      const origin=[Math.floor(camera.e/1000)*1000,Math.floor(camera.n/1000)*1000],eye=[camera.e-origin[0],camera.h,origin[1]-camera.n];
      const forward=[Math.sin(camera.yaw)*Math.cos(camera.pitch),Math.sin(camera.pitch),-Math.cos(camera.yaw)*Math.cos(camera.pitch)];
      gl.uniformMatrix4fv(loc.vp,false,multiply(perspective(w/h),view(eye,forward)));gl.uniform3fv(loc.camera,eye);
      for(const [id,item]of registry.meshes){if(!targetIds.has(id))continue;const center=item.geometry.centerL93;gl.uniform3f(loc.tile,center[0]-origin[0],0,origin[1]-center[1]);gl.bindVertexArray(item.handle.vao);gl.drawArrays(gl.TRIANGLES,0,item.handle.count);}
      renderedFrames++;collectErrors();
    }};
  }
  let renderer;

  function validators(){return {
    vector(record,tile){
      const normalized=G.normalizeRecord(record,tile.cellId,{cells:[{id:tile.cellId,boundsL93:tile.boundsL93}]});
      if(normalized.v53Synthetic)throw new Error('Données synthétiques refusées dans le survol réel.');return normalized;
    },
    terrain(pack,tile){
      if(pack.testOnly||pack.source?.testOnly||pack.source?.truth==='fixture')throw new Error('Relief de test refusé.');
      return {grid:T.load(pack,tile.boundsL93),pack};
    },
    surfaces(value,tile,world){
      if(value.schema!=='soma-metropole/surface-cell/1'||value.cellId!==tile.cellId||value.sourcePbfSHA256!==world.source.sha256||
        value.cell?.sourceSHA256!==world.source.sha256)throw new Error('Surface géographique non liée à la source du monde.');
      const record=entries.get(tile.cellId)?.layers.vector;
      if(!record||value.contentSHA256!==record.contentSHA256||value.cell?.contentSHA256!==record.contentSHA256)throw new Error('Surface issue d’une autre version de cellule.');
      return value;
    }
  };}
  function proofMatch(record,p,id){const row=parts?.parents?.[id];return row&&row.sourceSHA256===record.sourceReceipt.sha256&&row.parentGeometrySHA256===p['soma:geometry_sha256']&&row.cells?.[record.cellId]===record.contentSHA256?row:null;}
  function rebuildOptions(){
    const records=[...entries.values()].map(e=>e.layers.vector).filter(Boolean),useful=records.map(r=>({...r,featureCollection:{...r.featureCollection,
      features:r.featureCollection.features.filter(f=>['skillion','pyramidal','dome'].includes(String(f.properties?.['roof:shape']||'').toLowerCase()))}}));
    const datums=new Map(),missingCanonicalDatums=new Set(),aliases=new Map(),omitBuildingIds=new Set();
    for(const entry of entries.values()){
      const r=entry.layers.vector,grid=entry.layers.terrain.grid;if(!r)continue;
      for(const f of r.featureCollection.features){const p=f.properties||{},id=p.canonical_id||f.id;if(p['soma:layer']!=='buildings')continue;
        for(const mesh of p['soma:mesh53']||[])for(const ring of mesh.ringsL93)for(const point of ring){const h=grid.sample(...point);if(Number.isFinite(h))datums.set(id,Math.max(datums.get(id)??-Infinity,h));else missingCanonicalDatums.add(id);}
        if(proofMatch(r,p,id))omitBuildingIds.add(id);
        const link=parts?.partParents?.[id];if(link&&link.sourceSHA256===r.sourceReceipt.sha256&&link.geometrySHA256===p['soma:geometry_sha256']&&link.cells?.[r.cellId]===r.contentSHA256)aliases.set(id,link.parentId);
      }
    }
    for(const [id,parent]of aliases){if(datums.has(parent))datums.set(id,datums.get(parent));if(missingCanonicalDatums.has(parent))missingCanonicalDatums.add(id);}
    options={canonicalDatumsMap:datums,missingCanonicalDatums,omitBuildingIds,references:A.referenceIndex(useful),maxVertices:600000,maxWindowRows:3};
  }
  function enqueueVisible(){
    // Cache hits publish a fresh store wrapper without onAttach; synchronize
    // the identity used by stale-job checks before rebuilding those meshes.
    for(const id of targetIds){const entry=store?.get(id);if(entry)entries.set(id,entry);}
    rebuildOptions();for(const id of targetIds){const entry=entries.get(id);if(entry)jobs.set(id,{entry,generation});}
  }
  function buildOne(){
    const first=jobs.entries().next();if(first.done)return;const [id,job]=first.value;jobs.delete(id);
    if(job.generation!==generation||!targetIds.has(id)||entries.get(id)!==job.entry)return;
    try{
      const surface=job.entry.layers.surfaces,vector=job.entry.layers.vector;
      if(surface&&surface.contentSHA256!==vector?.contentSHA256)throw new Error('Surface issue d’une autre version de cellule.');
      const geometry=Geometry.buildTile(job.entry,{geo:G,terrain:T,fidelity:F,architecture:A},options);
      renderer.registry.attach(id,geometry,job.entry);mapDirty=true;
    }catch(error){buildFailures++;logError(error);}
  }
  function cellAt(e,n){const x=Math.round((e-manifest.origin[0])/250),y=Math.round((manifest.origin[1]-n)/250);return manifest.tiles.find(t=>t.gridX===x&&t.gridY===y)||null;}
  function sampleGround(e,n){const tile=cellAt(e,n),entry=tile&&entries.get(tile.cellId);return entry?.layers.terrain.grid.sample(e,n)??null;}
  function updateTarget(force=false){
    if(!store)return Promise.resolve();
    const x=Math.round((camera.e-manifest.origin[0])/250),y=Math.round((manifest.origin[1]-camera.n)/250),key=x+':'+y;
    if(!force&&key===lastCell)return requestPromise;lastCell=key;generation++;
    const token=generation,wanted=desiredTiles(manifest,camera.e,camera.n),ids=wanted.map(t=>t.cellId);
    targetIds=new Set(ids);renderer.registry.prune(targetIds);for(const id of[...jobs.keys()])if(!targetIds.has(id))jobs.delete(id);
    $('loading').textContent=ids.length?'Chargement des secteurs…':'Ce secteur n’est pas encore reconstitué.';
    requestPromise=requestFlightTiles(store,wanted).then(async outcomes=>{
      if(token!==generation)return;
      for(const result of outcomes)if(result.status==='rejected')logError(result.reason);
      enqueueVisible();
      const upgrades=wanted.filter(t=>t.vector&&t.surfaces&&store.get(t.cellId));
      await Promise.allSettled(upgrades.map(t=>store.load(t.cellId,{layers:['vector','terrain','surfaces']})));
      if(token!==generation)return;enqueueVisible();$('loading').textContent=outcomes.some(x=>x.status==='rejected')?'Certains secteurs n’ont pas pu être validés.':'';
    }).catch(logError);
    return requestPromise;
  }
  function inside(point,ring){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
  function inCommune(e,n,commune){return commune.polygons.some(poly=>inside([e,n],poly[0])&&!poly.slice(1).some(r=>inside([e,n],r)));}
  function communeAt(e,n){return communes.find(c=>inCommune(e,n,c));}
  function teleportMetric(e,n,h=null){
    if(!Number.isFinite(e)||!Number.isFinite(n))return false;
    const tile=cellAt(e,n);if(!flightLayers(tile)){$('map-description').textContent='Ce secteur ne dispose pas encore de relief utilisable dans ce monde.';return false;}
    camera.e=e;camera.n=n;camera.h=Number.isFinite(h)?Math.max(-100,Math.min(5000,h)):180;camera.pitch=-.55;keys.clear();
    const token=generation+1;updateTarget(true).then(()=>{if(generation===token&&!Number.isFinite(h)){const ground=sampleGround(e,n);if(Number.isFinite(ground))camera.h=ground+160;}});mapDirty=true;return true;
  }
  function teleportCommune(code){
    const commune=communes.find(c=>c.code===code);if(!commune?.anchorWGS84)return false;
    const anchor=commune.anchorL93||G.forward(commune.anchorWGS84);let point=anchor;
    $('map-description').textContent=commune.anchorSource==='osm-place-node'?
      'Destination : localité OSM vérifiée de '+commune.name+'.':
      'Destination : repère dérivé du contour de '+commune.name+' ; aucune localité univoque n’est disponible.';
    if(!flightLayers(cellAt(...point))){
      const candidates=manifest.tiles.filter(t=>flightLayers(t)).map(t=>({tile:t,e:(t.boundsL93[0]+t.boundsL93[2])/2,n:(t.boundsL93[1]+t.boundsL93[3])/2}));
      const nearest=candidates.filter(t=>Math.hypot(t.e-anchor[0],t.n-anchor[1])<2000&&inCommune(t.e,t.n,commune))
        .sort((a,b)=>Math.hypot(a.e-anchor[0],a.n-anchor[1])-Math.hypot(b.e-anchor[0],b.n-anchor[1]))[0];
      if(!nearest){$('map-description').textContent='Le secteur de '+commune.name+' n’est pas encore disponible dans ce monde.';return false;}point=[nearest.e,nearest.n];
    }
    if(teleportMetric(...point)){$('map-dialog').close();return true;}return false;
  }
  function nearestRoad(){
    let best=null,distance=100;
    for(const id of targetIds)for(const f of entries.get(id)?.layers.vector?.featureCollection.features||[]){const p=f.properties||{};if(!p.highway||!p.name)continue;
      const g=p['soma:metricGeometry'],lines=g?.type==='LineString'?[g.coordinates]:g?.type==='MultiLineString'?g.coordinates:[];
      for(const line of lines)for(let i=1;i<line.length;i++){const d=G.segmentDistance([camera.e,camera.n],line[i-1],line[i]);if(d<distance){distance=d;best=p.name;}}
    }return best;
  }
  function hud(now){
    if(now-lastHUD<350)return;lastHUD=now;
    const terrainOnly=cellAt(camera.e,camera.n)?.terrainOnly===true;
    const commune=communeAt(camera.e,camera.n),road=terrainOnly?null:nearestRoad(),ll=G.inverse([camera.e,camera.n]);
    $('place-name').textContent=road?'Au-dessus de '+road:commune?.name||'Survol métropolitain';
    $('place-detail').textContent=(commune?.name||'Secteur géographique')+' · '+ll[1].toFixed(5)+'° N, '+ll[0].toFixed(5)+'° E';
    const ground=sampleGround(camera.e,camera.n);$('altitude').textContent='ALT. '+Math.round(camera.h)+' m NGF'+(Number.isFinite(ground)?' · '+Math.round(camera.h-ground)+' m au-dessus du relief':' · relief absent ici');
    let buildings=0,estimated=0,ign=0,missing=0;for(const item of renderer.registry.meshes.values()){buildings+=item.geometry.counts.buildings;estimated+=item.geometry.counts.estimatedBuildings;ign+=item.geometry.counts.ignHeightBuildings;missing+=item.geometry.counts.missingGroundBuildings;}
    $('stats').textContent=terrainOnly?'Relief seul dans ce secteur\nRoutes et bâtiments non disponibles':buildings.toLocaleString('fr-FR')+' bâtiments affichés\n'+estimated.toLocaleString('fr-FR')+' hauteurs estimées · '+ign.toLocaleString('fr-FR')+' références IGN';
    if($('map-dialog').open){mapDirty=true;drawMap();}
  }
  function drawMap(){
    if(!$('map-dialog').open||!mapDirty)return;mapDirty=false;
    const canvas=$('map'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#061119';ctx.fillRect(0,0,canvas.width,canvas.height);
    const points=communes.flatMap(c=>c.polygons.flatMap(poly=>poly[0]));if(!points.length||!manifest)return;
    let west=Infinity,south=Infinity,east=-Infinity,north=-Infinity;for(const p of points){west=Math.min(west,p[0]);south=Math.min(south,p[1]);east=Math.max(east,p[0]);north=Math.max(north,p[1]);}
    const scale=Math.min((canvas.width-30)/(east-west),(canvas.height-30)/(north-south)),x0=(canvas.width-(east-west)*scale)/2,y0=(canvas.height-(north-south)*scale)/2;
    const xy=p=>[x0+(p[0]-west)*scale,canvas.height-y0-(p[1]-south)*scale];mapProjection={inverse:(x,y)=>[west+(x-x0)/scale,south+(canvas.height-y-y0)/scale]};
    for(const c of communes){ctx.beginPath();for(const poly of c.polygons)for(const ring of poly)ring.forEach((p,i)=>{const[x,y]=xy(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.fillStyle='#112e38';ctx.fill('evenodd');ctx.strokeStyle='#37616b';ctx.lineWidth=.7;ctx.stroke();}
    for(const t of manifest.tiles){if(!flightLayers(t))continue;ctx.fillStyle=t.terrainOnly?'#286c6988':'#39c1abbb';const a=xy([t.boundsL93[0],t.boundsL93[3]]);ctx.fillRect(a[0],a[1],Math.max(1,250*scale),Math.max(1,250*scale));}
    const [x,y]=xy([camera.e,camera.n]);ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fillStyle='#ffcf85';ctx.fill();
  }
  const worldLoader=atomicWorldLoader({
    async prepare({relative,sourceMode},{signal}){
      if(!safeWorldPath(relative))throw new Error('Le chemin du manifeste doit être un fichier JSON relatif sûr.');
      const url=new URL(relative,root.location.href);let raw;
      try{raw=await readJSON(url,128*1024*1024,root.fetch.bind(root),signal);}catch(error){error.stage='manifest';throw error;}
      const nextManifest=S.validateManifest(raw),nextParts=await loadBuildingParts(nextManifest,url.href,
        {signal,embeddedProof:embeddedParts,sha256:S.sha256});
      const available=nextManifest.tiles.filter(t=>flightLayers(t));if(!available.length)throw new Error('Ce monde ne contient pas encore de relief utilisable.');
      const start=available.slice().sort((a,b)=>Math.hypot((a.boundsL93[0]+a.boundsL93[2])/2-892100,(a.boundsL93[1]+a.boundsL93[3])/2-6247000)-Math.hypot((b.boundsL93[0]+b.boundsL93[2])/2-892100,(b.boundsL93[1]+b.boundsL93[3])/2-6247000))[0];
      const nextStore=S.createTileStore({manifest:nextManifest,baseURL:url.href,validators:validators(),maxResidentBytes:192*1024*1024,
        maxInFlight:2,maxPending:64,memoryFactor:4,onAttach(id,entry){entries.set(id,entry);if(targetIds.has(id)){rebuildOptions();jobs.set(id,{entry,generation});}},
        onDetach(id){entries.delete(id);jobs.delete(id);renderer.registry.detach(id);}});
      return {nextManifest,nextParts,nextStore,start,url:url.href,sourceMode};
    },
    commit(next){
      // Everything above is validated before changing the visible world. The
      // synchronous commit shares one source-bound parts proof with its store.
      generation++;store?.cancel();store?.protect([]);for(const id of store?.snapshot().residentIds||[])store.remove(id);
      renderer.registry.clear();entries.clear();jobs.clear();targetIds.clear();lastCell='';options={};
      manifest=next.nextManifest;parts=next.nextParts;store=next.nextStore;manifestURL=next.url;mode=next.sourceMode;
      const centre=mode==='fallback-centre'||manifest.edition==='bundled-centre-0.69';
      $('coverage').textContent=centre?'Centre de Marseille · carte partielle · certaines hauteurs estimées':'Aix-Marseille-Provence · survol libre · certaines hauteurs estimées';
      $('open-map').disabled=false;$('error').hidden=true;
      teleportMetric((next.start.boundsL93[0]+next.start.boundsL93[2])/2,(next.start.boundsL93[1]+next.start.boundsL93[3])/2);mapDirty=true;
      return {request:requestPromise};
    }
  });
  function loadWorld(relative,sourceMode){
    worldPromise=worldLoader.load({relative,sourceMode}).then(committed=>committed.request);
    return worldPromise;
  }
  function animate(now){
    const dt=Math.min(.05,(now-lastUpdate)/1000||0);lastUpdate=now;
    const typing=['INPUT','SELECT','TEXTAREA'].includes(document.activeElement?.tagName),blocked=$('map-dialog').open||$('help-dialog').open||$('error').hidden===false;
    if(!typing&&!blocked){
      const forward=(keys.has('KeyW')||keys.has('KeyZ')||keys.has('ArrowUp')?1:0)-(keys.has('KeyS')||keys.has('ArrowDown')?1:0),
        sideways=(keys.has('KeyD')||keys.has('ArrowRight')?1:0)-(keys.has('KeyA')||keys.has('KeyQ')||keys.has('ArrowLeft')?1:0),
        vertical=(keys.has('Space')?1:0)-(keys.has('KeyC')||keys.has('ControlLeft')||keys.has('ControlRight')?1:0),speed=camera.speed*(keys.has('ShiftLeft')||keys.has('ShiftRight')?3:1)*dt;
      camera.e+=(Math.sin(camera.yaw)*forward+Math.cos(camera.yaw)*sideways)*speed;camera.n+=(Math.cos(camera.yaw)*forward-Math.sin(camera.yaw)*sideways)*speed;camera.h=Math.max(-100,Math.min(5000,camera.h+vertical*speed));
    }
    if(store&&now-lastCellUpdate>180){lastCellUpdate=now;updateTarget();}
    buildOne();renderer.draw();if(store)hud(now);frame=requestAnimationFrame(animate);
  }
  let lastCellUpdate=0;
  function snapshot(){return{camera:{...camera},manifestURL,mode,generation,targetIds:[...targetIds],resident:entries.size,pendingGeometry:jobs.size,
    geometry:renderer.registry.snapshot(),cache:store?.snapshot()||null,renderedFrames,buildFailures,errors:errors.slice(),
    buildings:[...renderer.registry.meshes.values()].reduce((s,x)=>s+x.geometry.counts.buildings,0),
    roadTriangles:[...renderer.registry.meshes.values()].reduce((s,x)=>s+x.geometry.counts.roadTriangles,0),
    estimatedBuildings:[...renderer.registry.meshes.values()].reduce((s,x)=>s+x.geometry.counts.estimatedBuildings,0),
    ignHeightBuildings:[...renderer.registry.meshes.values()].reduce((s,x)=>s+x.geometry.counts.ignHeightBuildings,0),
    terrainOnlySectors:[...renderer.registry.meshes.keys()].filter(id=>entries.get(id)?.tile.terrainOnly===true).length,
    sourceSHA256:manifest?.source.sha256||null,
    buildingParts:{proofSHA256:parts?.proofSHA256||null,sourceSHA256:parts?.sourceSHA256||null,
      parents:Object.keys(parts?.parents||{}).length,matchedParents:options.omitBuildingIds?.size||0},
    navigationRequired:false,campaignPersistenceLoaded:false,webglError:renderer.errorCodes[0]||0,webglErrors:renderer.errorCodes.slice()};}
  async function start(){
    try{
      renderer=createRenderer($('scene'));
      root.__SOMA_METRO_VIEWER__={snapshot,teleportMetric,teleportWGS84(lon,lat,h){return teleportMetric(...G.forward([lon,lat]),h);},
        teleportCommune,refresh:()=>updateTarget(true),ready:()=>worldPromise.then(()=>requestPromise),loadWorld:relative=>loadWorld(relative,'explicit'),
        stop(){worldLoader.cancel();generation++;cancelAnimationFrame(frame);store?.cancel();store?.protect([]);for(const id of store?.snapshot().residentIds||[])store.remove(id);renderer.registry.clear();entries.clear();jobs.clear();targetIds.clear();keys.clear();}};
      root.__SOMA_METROPOLE_VIEWER__=root.__SOMA_METRO_VIEWER__;
      $('return-game').href=metadata.returnToGame;
      for(const c of communes){const option=document.createElement('option');option.value=c.code;option.textContent=c.name+(c.anchorSource==='administrative-contour-fallback'?' (repère de contour)':'');if(!c.anchorWGS84)option.disabled=true;$('commune').appendChild(option);}
      $('commune').onchange=event=>teleportCommune(event.target.value);
      $('open-map').onclick=()=>openDialog('map-dialog');$('close-map').onclick=()=>$('map-dialog').close();
      $('open-help').onclick=()=>openDialog('help-dialog');$('close-help').onclick=()=>$('help-dialog').close();
      $('speed').oninput=event=>{camera.speed=Number(event.target.value);$('speed-label').textContent=camera.speed+' m/s';};
      $('map').onclick=event=>{if(!mapProjection)return;const rect=event.currentTarget.getBoundingClientRect(),p=mapProjection.inverse((event.clientX-rect.left)*event.currentTarget.width/rect.width,(event.clientY-rect.top)*event.currentTarget.height/rect.height);if(teleportMetric(...p))$('map-dialog').close();};
      function lock(){if($('error').hidden!==false){$('scene').focus();const p=$('scene').requestPointerLock?.();p?.catch?.(()=>{$('loading').textContent='Cliquer-glisser dans la vue pour regarder.';});}}
      $('enter').onclick=lock;$('scene').onclick=lock;
      document.addEventListener('pointerlockchange',()=>{$('enter').hidden=document.pointerLockElement===$('scene');});
      let dragging=false;$('scene').addEventListener('mousedown',()=>{dragging=true;});root.addEventListener('mouseup',()=>{dragging=false;});
      root.addEventListener('mousemove',event=>{if(document.pointerLockElement===$('scene')||dragging){camera.yaw+=event.movementX*.002;camera.pitch=Math.max(-1.5,Math.min(1.5,camera.pitch-event.movementY*.002));}});
      root.addEventListener('keydown',event=>{if(event.code==='Escape'){releaseMouse();return;}if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.code)&&!['INPUT','SELECT'].includes(document.activeElement?.tagName))event.preventDefault();keys.add(event.code);});
      root.addEventListener('keyup',event=>keys.delete(event.code));root.addEventListener('blur',()=>keys.clear());
      $('scene').addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frame);fatal(new Error('Le contexte graphique a été interrompu. Recharger la page pour reprendre.'));});
      $('retry-centre').onclick=()=>loadWorld(metadata.fallbackWorld,'fallback-centre').catch(fatal);
      frame=requestAnimationFrame(animate);
      const selected=new URLSearchParams(location.search).get('world');
      if(selected!==null)await loadWorld(selected,'explicit');
      else try{await loadWorld(metadata.defaultWorld,'metropole');}catch(error){if(error.status===404&&error.stage==='manifest')await loadWorld(metadata.fallbackWorld,'fallback-centre');else throw error;}
    }catch(error){fatal(error);}
  }
  start();
})(typeof globalThis!=='undefined'?globalThis:this);
