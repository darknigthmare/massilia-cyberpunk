/* Source-axis presentation only: no routing, network, campaign or movement. */
(function(root){
  'use strict';
  const VERSION='0.71.0',MAX_SEGMENTS=16000,MAX_SPANS=4096,MAX_GROUPS=120;
  const finite=n=>typeof n==='number'&&Number.isFinite(n),point=p=>p&&finite(p.e)&&finite(p.n)&&Math.abs(p.e)<=1e8&&Math.abs(p.n)<=1e8;
  const clean=s=>typeof s==='string'?s.replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,240):'';
  const length=s=>Math.hypot(s.b.e-s.a.e,s.b.n-s.a.n);
  function validate(result){
    if(result?.schema!=='soma-metropole/route-preview/1'||result.status!=='route'||result.code!=='source_axis_route'||
      !Array.isArray(result.route?.segments)||result.route.segments.length>MAX_SEGMENTS||
      !finite(result.route.lengthMeters)||result.route.lengthMeters<0||result.physicalAccessibilityVerified!==false||
      result.campaignRoutingActivated!==false||result.route.completeBetweenAnchors!==true)throw new TypeError('Un itinéraire d’axes source validé est requis.');
    let sum=0,previous=null;
    for(const s of result.route.segments){
      if(!point(s.a)||!point(s.b)||!/^[1-9]\d*$/.test(s.wayId)||!Number.isSafeInteger(s.segmentIndex)||s.segmentIndex<1||
        !finite(s.sourceT0)||!finite(s.sourceT1)||s.sourceT0<0||s.sourceT0>1||s.sourceT1<0||s.sourceT1>1||
        !Array.isArray(s.cellIds)||!s.cellIds.length||s.cellIds.some(id=>typeof id!=='string')||
        previous&&Math.hypot(previous.e-s.a.e,previous.n-s.a.n)>1e-5)throw new TypeError('Segments source invalides ou disjoints.');
      sum+=length(s);previous=s.b;
    }
    if(Math.abs(sum-result.route.lengthMeters)>Math.max(1e-4,sum*1e-8))throw new TypeError('Longueur des axes incohérente.');
    return result;
  }
  function record(result,world){
    validate(result);
    for(const [a,b]of [['sourcePbfSHA256',world?.source?.sha256],['sourcePackSHA256',world?.sourcePackSHA256],
      ['nativeTopologySHA256',world?.nativeTopologySHA256],['routingCoreSHA256',world?.navigationCore?.sha256]])
      if(!/^[a-f0-9]{64}$/.test(b||'')||result[a]!==b)throw new TypeError('Le tracé appartient à une autre édition.');
    return {sourcePbfSHA256:result.sourcePbfSHA256,segments:result.route.segments.map(s=>({a:{...s.a},b:{...s.b},wayId:s.wayId,
      name:clean(s.name)||null,steps:s.steps===true,segmentIndex:s.segmentIndex,cellIds:s.cellIds.slice()})),lengthMeters:result.route.lengthMeters};
  }
  function itinerary(result){
    validate(result);const groups=[];let truncatedMeters=0,truncated=false;
    for(const s of result.route.segments){
      const name=clean(s.name)||'Voie OSM '+s.wayId,key=s.wayId+'|'+(s.steps===true),d=length(s),last=groups.at(-1);
      if(truncated)truncatedMeters+=d;
      else if(last?.key===key){last.lengthMeters+=d;last.segments++;}
      else if(groups.length<MAX_GROUPS)groups.push({key,wayId:s.wayId,name,steps:s.steps===true,lengthMeters:d,segments:1});
      else{truncated=true;truncatedMeters+=d;}
    }
    return {groups,totalMeters:result.route.lengthMeters,truncatedMeters,physicalAccessibilityVerified:false};
  }
  function choiceLabel(q){
    const name=clean(q?.name),id=/^[1-9]\d*$/.test(q?.wayId)?q.wayId:'?',distance=finite(q?.distanceMeters)?q.distanceMeters.toFixed(2):'?';
    return (name?name+' · OSM '+id:'Voie OSM '+id)+(q?.steps?' · escaliers':'')+' · '+distance+' m du point';
  }
  const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
  function clipPolygon(subject,triangle){
    let poly=subject.map(p=>p.slice());const sign=Math.sign(cross(...triangle));
    if(!sign)return [];
    for(let edge=0;edge<3&&poly.length;edge++){
      const a=triangle[edge],b=triangle[(edge+1)%3],out=[];
      for(let i=0;i<poly.length;i++){
        const p=poly[i],q=poly[(i+1)%poly.length],dp=sign*cross(a,b,p),dq=sign*cross(a,b,q),insideP=dp>=-1e-8,insideQ=dq>=-1e-8;
        if(insideP)out.push(p);
        if(insideP!==insideQ){const t=dp/(dp-dq);out.push([p[0]+(q[0]-p[0])*t,p[1]+(q[1]-p[1])*t]);}
      }
      poly=out;
    }
    return poly;
  }
  function buildOverlay(route,{terrainTriangles,spanAvailable,spacing=5,maxSpans=MAX_SPANS,width=1.3,lift=.25}={}){
    if(!Array.isArray(route?.segments)||route.segments.length>MAX_SEGMENTS||typeof terrainTriangles!=='function'||typeof spanAvailable!=='function'||
      !finite(spacing)||spacing<1||spacing>10||!Number.isSafeInteger(maxSpans)||maxSpans<1||maxSpans>MAX_SPANS||
      !finite(width)||width<=0||width>2||!finite(lift)||lift<0||lift>.5)throw new TypeError('Contexte de repères borné requis.');
    const first=route.segments[0]?.a;if(first&&!point(first))throw new TypeError('Point source invalide.');
    const center=first?[Math.floor(first.e/1000)*1000,Math.floor(first.n/1000)*1000]:[0,0];
    const data=[],maxFloats=MAX_SPANS*6*9;let considered=0,rendered=0,omitted=0,truncated=false,renderedMeters=0;
    outer:for(const s of route.segments){
      if(!point(s.a)||!point(s.b))throw new TypeError('Point source invalide.');
      const d=length(s);if(d<1e-8)continue;
      const count=Math.ceil(d/spacing),nx=-(s.b.n-s.a.n)/d*width/2,ny=(s.b.e-s.a.e)/d*width/2;
      for(let i=0;i<count;i++){
        if(considered>=maxSpans){truncated=true;break outer;}considered++;
        const at=t=>({e:s.a.e+(s.b.e-s.a.e)*t,n:s.a.n+(s.b.n-s.a.n)*t}),a=at(i/count),b=at((i+1)/count);
        const quad=[{e:a.e+nx,n:a.n+ny},{e:a.e-nx,n:a.n-ny},{e:b.e-nx,n:b.n-ny},{e:b.e+nx,n:b.n+ny}];
        const bounds={minE:Math.min(...quad.map(p=>p.e)),maxE:Math.max(...quad.map(p=>p.e)),minN:Math.min(...quad.map(p=>p.n)),maxN:Math.max(...quad.map(p=>p.n))};
        // Every cell touched by the ribbon's bounding box must have complete,
        // validated terrain already drawn. Missing or partial cells make a gap.
        if(spanAvailable(bounds)!==true){omitted++;continue;}
        const terrain=terrainTriangles(bounds);
        if(!Array.isArray(terrain)||terrain.length>64){omitted++;continue;}
        const source=quad.map(p=>[p.e-center[0],p.n-center[1]]),pieces=[];let area=0,invalid=false;
        for(const native of terrain){
          if(!Array.isArray(native)||native.length!==3||native.some(p=>!Array.isArray(p)||p.length!==3||!p.every(finite))){invalid=true;break;}
          const cell=native.map(p=>[p[0]-center[0],p[1]-center[1]]),det=cross(...cell);if(Math.abs(det)<1e-10)continue;
          const poly=clipPolygon(source,cell);
          for(let j=1;j+1<poly.length;j++){
            let t=[poly[0],poly[j],poly[j+1]],size=cross(...t)/2;if(Math.abs(size)<1e-9)continue;
            if(size<0)t=[t[0],t[2],t[1]];area+=Math.abs(size);
            for(const p of t){const wb=cross(cell[0],p,cell[2])/det,wc=cross(cell[0],cell[1],p)/det,
              h=native[0][2]+wb*(native[1][2]-native[0][2])+wc*(native[2][2]-native[0][2]);
              pieces.push(p[0],h+lift,-p[1],0,1,0,.12,1.4,1.4);}
          }
        }
        // Partial or overlapping triangle coverage cannot claim a full marked
        // span. This also rejects incomplete readers instead of bridging gaps.
        const expected=d/count*width;
        if(invalid||Math.abs(area-expected)>Math.max(1e-6,expected*1e-6)){omitted++;continue;}
        if(data.length+pieces.length>maxFloats){truncated=true;break outer;}
        for(const value of pieces)data.push(value);rendered++;renderedMeters+=d/count;
      }
    }
    const vertices=new Float32Array(data);
    return {vertices,centerL93:center,geometryBytes:vertices.byteLength,consideredSpans:considered,renderedSpans:rendered,
      omittedSpans:omitted,truncated,renderedMeters,maxBytes:MAX_SPANS*6*9*4,
      meaning:'Repères visuels sur le relief complet déjà affiché ; aucune chaussée ni accessibilité physique ajoutée.'};
  }
  const API=Object.freeze({VERSION,MAX_SEGMENTS,MAX_SPANS,MAX_GROUPS,validate,record,itinerary,choiceLabel,buildOverlay});
  root.__SOMA_ROUTE71_PRESENTATION__=API;if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof globalThis!=='undefined'?globalThis:this);
