'use strict';
// Execute the real27 ammunition,29 selectors and30 chamber owner in source order.
const path=require('node:path'),cp=require('node:child_process'),vm=require('node:vm');
const game=path.resolve(__dirname,'../..');
const sources=JSON.parse(cp.execFileSync('python3',['-B','-c',String.raw`
import json,sys,re
from pathlib import Path
game=Path(sys.argv[1]);sys.path.insert(0,str(game))
from tools.v78_combat import MODULES,patch_html
parent=(game/'SOMA_MASSILIA_URBAIN_v0_77.html').read_text()
output=patch_html(parent,{n:(game/f'src/v78/{n}.js').read_text() for n in MODULES})
def selected(text):
    lines=text.splitlines()
    def line(prefix):return next(x for x in lines if x.startswith(prefix))
    a=text.index('const WEAPONS=');end='].map(w=>({...w,c:C.hex(w.col)}));';b=text.index(end,a)+len(end)
    a30=text.index('function clearJam(){');b30=text.index('function drop(id,qty=1){',a30)
    active=text.index('function activeWeapon(){');owned=text.index('function materialOwnedWeapon(',active)
    s77=text.index('<script id="soma-v77-combat-reload-runtime">')
    reload77=text[s77+len('<script id="soma-v77-combat-reload-runtime">'):text.index('</script>',s77)]
    timer='if(reloadLeft>0){reloadLeft-=dt;if(reloadLeft<=0)finishReload()}'
    assert text.count(timer)==1
    return {'weapons':text[a:b], 'names':line('const MATERIAL_WEAPON_NAMES='), 'refusal64':line('function refusal(){'),
      'active':text[active:owned], 'chamber':text[a30:b30], 'reload77':reload77,
      'reload':line('reload=function(){if(v27IsCyber())'),
      'finish':line('finishReload=function(){const id=v27ReloadWeaponId'),
      'arsenal':line('renderArsenal=function(){const root='),
      'equip':line('function v29EquipWeapon(id)'), 'slot':line('function v29SelectSlot(i)'),
      'cycle':line('const v29OldCycleWeapon='), 'timer':'function update(dt){'+timer+'}'}
print(json.dumps({'before':selected(parent),'after':selected(output)}))
`,game],{encoding:'utf8',maxBuffer:200000}));
function element(){return {children:[],classList:{contains:()=>false},appendChild(x){this.children.push(x);},addEventListener(){},innerHTML:'',dataset:{},style:{}};}
function context(before=false){
 const scripts=sources[before?'before':'after'],els=new Map();
 const c={Math,Number,Object,Set,Map,JSON,paused:false,reloadLeft:0,v27ReloadWeaponId:null,fireCD:0,
  state:{weapon:0,health:100,driving:null,recovery:{pending:false},settings:{},unlocked:['pistol','pacifier','rifle'],ammo:{}},
  zone:{id:'qa-hideout',type:'v28-hideout'},cyber:false,v28VM:{draw:0},toasts:[],saveCalls:0,
  S:{activeWeapon:'',durability:{}},WEAPONS:null,C:{hex:x=>x},audio:()=>{},announce:()=>{},
  toast:message=>c.toasts.push(message),save:()=>{c.saveCalls++;},esc:x=>x,
  v27IsCyber:()=>c.cyber,v27Stats:()=>({reloadMult:1}),
  v27Player:()=>({weaponMods:Object.fromEntries(c.WEAPONS.map(w=>[w.id,{}])),weaponTiers:Object.fromEntries(c.WEAPONS.map(w=>[w.id,1]))}),
  v29AtLoadoutStation:()=>true,v29Loadout:()=>c.loadout.weaponLoadout,v29State:()=>c.loadout,
  v29CarryMetrics:()=>({weight:0,volume:0}),v29WeaponWeight:()=>1,v29WeaponVolume:()=>1,v29CarryLimits:()=>({weight:100,volume:100}),
  document:{createElement:element},$:id=>{if(!els.has(id))els.set(id,element());return els.get(id);},
  cycleWeapon:()=>false,enterZone:id=>{if(id==='missing')return false;c.zone={...c.zone,id};return true;}};
 c.window=c;vm.createContext(c);
 vm.runInContext(scripts.weapons+'\nWEAPONS.forEach(w=>state.ammo[w.id]={mag:w.id===\'pistol\'?1:w.mag,reserve:w.id===\'pistol\'?20:w.reserve});globalThis.WEAPONS=WEAPONS;',c);
 for(const w of c.WEAPONS)c.S.durability[w.name]={jammed:false,condition:80};
 c.loadout={weaponLoadout:['pistol','pacifier','rifle']};
 for(const name of ['names','active','reload','finish','arsenal','equip','slot','cycle','timer','chamber','reload77'])vm.runInContext(scripts[name],c);
 c.api=c.__SOMA_CHAMBER78__;
 c.record=()=>c.S.durability[c.WEAPONS.find(w=>w.id==='pistol').name];
 c.start=()=>{c.record().jammed=true;c.paused=false;c.reload();return c.api?.snapshot();};
 c.advance=(count=10)=>{for(let i=0;i<count;i++)if(!c.paused)c.update(.1);};
 c.arsenalClick=index=>{c.renderArsenal();const cards=c.$('#arsenalGrid').children;cards[cards.length-c.WEAPONS.length+index].children[0].onclick();};
 return c;
}
module.exports={context,sources};
