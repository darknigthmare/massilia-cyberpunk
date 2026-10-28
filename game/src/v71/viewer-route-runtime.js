/* Read-only itinerary and source-axis markers for the independent flyover. */
(function(root){
  'use strict';
  if(!root.document)return;
  const P=root.__SOMA_ROUTE71_PRESENTATION__,viewer=root.__SOMA_METROPOLE_VIEWER__||root.__SOMA_METRO_VIEWER__,context=viewer?.narrowContext?.(),
    $=id=>root.document.getElementById(id);
  if(!P||!context?.setRoutePresentation||!$('route71-steps'))throw new Error('Présentation d’itinéraire absente.');
  let last=null;
  function clear(){last=null;context.setRoutePresentation(null);$('route71-steps').replaceChildren();$('route71-clear').disabled=true;}
  function render(result){
    clear();if(result?.status!=='route')return;
    const plan=P.itinerary(result);last=result;
    for(const group of plan.groups){const li=root.document.createElement('li');
      li.textContent=group.name+' · '+Math.round(group.lengthMeters)+' m'+(group.steps?' · escaliers':'');$('route71-steps').append(li);}
    if(plan.truncatedMeters){const li=root.document.createElement('li');li.textContent=Math.round(plan.truncatedMeters)+' m supplémentaires sur les axes source.';$('route71-steps').append(li);}
    if($('route71-show3d').checked)context.setRoutePresentation(result);
    $('route71-clear').disabled=false;
  }
  $('route71-show3d').onchange=()=>{if(last&&$('route71-show3d').checked)context.setRoutePresentation(last);else context.setRoutePresentation(null);};
  $('route71-clear').onclick=clear;context.onWorldChange(clear);
  root.__SOMA_ROUTE71_RUNTIME__=Object.freeze({render,clear});
  const previous=root.__SOMA_ROUTE70_VIEWER__;
  root.__SOMA_ROUTE71_VIEWER__=Object.freeze({...previous,clearPresentation:clear,
    presentation:()=>context.routePresentationSnapshot()});
})(typeof globalThis!=='undefined'?globalThis:this);
