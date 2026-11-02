/* Execute the transformed historical owners. Geometry used by these tests is
 * explicitly synthetic; browser QA separately exercises installed source cells. */
'use strict';
const path=require('node:path'),cp=require('node:child_process');
const game=path.resolve(__dirname,'../..');
module.exports=JSON.parse(cp.execFileSync('python3',['-c',String.raw`
import json,re,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v74_mobility import patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_73.html').read_text()
html=patch_html(parent,{'mobility-runtime':(game/'src/v74/mobility-runtime.js').read_text()})
def script(name):return re.search(r'<script\b[^>]*id="'+name+r'"[^>]*>([\s\S]*?)</script>',html)[1]
def span(text,a,b):return text[text.index(a):text.index(b,text.index(a))]
terrain=script('soma-v56-terrain-runtime');v42=script('soma-v42-recovery')
originalTerrain=re.search(r'<script id="soma-v56-terrain-runtime">([\s\S]*?)</script>',parent)[1]
seams=script('soma-v55-runtime')
print(json.dumps({'runtime':script('soma-v74-mobility-runtime'),'terrainCore':script('soma-v56-terrain-core'),'collisionCore':script('soma-v57-core'),'seamCore':script('soma-v55-core'),
 'neighbor55':span(seams,'function neighbor(z,side){','function saveStats('),
 'collision55':span(seams,'function collision(','function roadGate('),
 'parentMove20':span(parent,'const v20BaseMove=move;','const v20BaseUpdate=update;'),
 'parentMove56':span(originalTerrain,' const oldMove=move;',' const oldEnter=enterZone;'),
 'parentSafeExit':span(parent,'function safeExitPoint(','function aabb('),
 'parentEnterExit':span(parent,'function enterVehicle(v){','function vehicleDialogue('),
 'move20':span(html,'const v20BaseMove=move;','const v20BaseUpdate=update;'),
 'move42':span(v42,'const baseMove=move;move=function(dt){','\n // Camera-locked'),
 'move56':span(terrain,' const oldMove=move;',' const oldEnter=enterZone;'),
 'pose56':span(terrain,'function poseCamera(){','function footprintValid('),
 'blocked':span(html,'function blocked(zone,x,z,r=.38){','function buildZone('),
 'pedestrian':span(html,'function pedestrianVehicleClear(','function safeExitPoint('),
 'safeExit':span(html,'function safeExitPoint(','function aabb('),
 'enterExit':span(html,'function enterVehicle(v){','function vehicleDialogue(')}))
`,game],{encoding:'utf8',maxBuffer:8*1024*1024}));
