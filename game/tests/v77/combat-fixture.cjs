'use strict';
const path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const sources=JSON.parse(cp.execFileSync('python3',['-B','-c',String.raw`
import json,sys
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v77_combat import MODULES,patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_76.html').read_text()
out=patch_html(parent,{n:(game/f'src/v77/{n}.js').read_text() for n in MODULES})
def selected(text):
    lines=text.splitlines()
    def line(start):return next(x for x in lines if x.startswith(start))
    a=text.index('const WEAPONS=');end='].map(w=>({...w,c:C.hex(w.col)}));';b=text.index(end,a)+len(end)
    timer='if(reloadLeft>0){reloadLeft-=dt;if(reloadLeft<=0)finishReload()}'
    assert text.count(timer)==1
    return {'weapons':text[a:b], 'reload':line('reload=function(){if(v27IsCyber())'),
      'finish':line('finishReload=function(){const id=v27ReloadWeaponId'),
      'arsenal':line('renderArsenal=function(){const root='),
      'equip':line('function v29EquipWeapon(id)'), 'slot':line('function v29SelectSlot(i)'),
      'cycle':line('const v29OldCycleWeapon='),
      'controls':line('function controls(){'),
      'timer':'function update(dt){'+timer+'}',
      'loop':text[text.index('function loop(t){'):text.index('function controls(){')],
      'runtime':text[text.index('<script id="soma-v77-combat-reload-runtime">')+len('<script id="soma-v77-combat-reload-runtime">'):text.index('</script>',text.index('<script id="soma-v77-combat-reload-runtime">'))] if 'soma-v77-combat-reload-runtime' in text else ''}
print(json.dumps({'before':selected(parent),'after':selected(out)}))
`,game],{encoding:'utf8',maxBuffer:200000}));
function element(){return {children:[],classList:{contains:()=>false},appendChild(x){this.children.push(x);},addEventListener(){},innerHTML:'',dataset:{},style:{}};}
function context(before=false){
 const scripts=sources[before?'before':'after'],els=new Map();
 const c={Math,Number,Object,Set,Map,JSON,paused:false,reloadLeft:0,v27ReloadWeaponId:null,fireCD:0,announcements:[],
  state:{weapon:0,health:100,driving:null,recovery:{pending:false},settings:{},unlocked:['pistol','pacifier','rifle'],ammo:{}},
  zone:{id:'qa-hideout',type:'v28-hideout'},cyber:false,v28VM:{draw:0},events:{},
  WEAPONS:null,C:{hex:x=>x},audio:()=>{},announce:(...args)=>c.announcements.push(args),save:()=>{},exportSave:()=>{},esc:x=>x,
  v27IsCyber:()=>c.cyber,v27Stats:()=>({reloadMult:1}),
  v27Player:()=>({weaponMods:Object.fromEntries(c.WEAPONS.map(w=>[w.id,{}])),weaponTiers:Object.fromEntries(c.WEAPONS.map(w=>[w.id,1]))}),
  v29AtLoadoutStation:()=>true,v29Loadout:()=>c.loadout.weaponLoadout,v29State:()=>c.loadout,
  v29CarryMetrics:()=>({weight:0,volume:0}),v29WeaponWeight:()=>1,v29WeaponVolume:()=>1,v29CarryLimits:()=>({weight:100,volume:100}),
  document:{createElement:element},canvas:element(),keys:new Set(),touches:new Set(),
  $:id=>{if(!els.has(id))els.set(id,element());return els.get(id);},$$:()=>[],
  cycleWeapon:()=>false,enterZone:(id)=>{if(id==='missing')return false;c.zone={...c.zone,id};return true;},
  addEventListener:(event,fn)=>{(c.events[event]??=[]).push(fn);}};
 c.window=c;c.document.addEventListener=()=>{};vm.createContext(c);
 vm.runInContext(scripts.weapons+'\nWEAPONS.forEach(w=>state.ammo[w.id]={mag:w.id===\'pistol\'?1:w.mag,reserve:w.id===\'pistol\'?20:w.reserve});globalThis.WEAPONS=WEAPONS;',c);
 c.loadout={weaponLoadout:['pistol','pacifier','rifle']};
 for(const id of ['reload','finish','arsenal','equip','slot','cycle','controls','timer'])vm.runInContext(scripts[id],c);
 if(!before)vm.runInContext(scripts.runtime,c);
 c.api=c.__SOMA_RELOAD77__;c.scripts=scripts;
 c.arsenalClick=index=>{c.renderArsenal();const cards=c.$('#arsenalGrid').children;cards[cards.length-c.WEAPONS.length+index].children[0].onclick();};
 c.advance=(dt=2)=>{if(!c.paused)c.update(dt);};
 c.start=()=>{c.reload();return c.reloadLeft;};
 return c;
}
module.exports={context,sources};
