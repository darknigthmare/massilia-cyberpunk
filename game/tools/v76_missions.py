"""Repair the authored production43 campaign without a new save owner."""
import json

from build_v68 import replace_once, rewrite_script

MODULES = ('missions-runtime',)
MARKER = '/* SOMA v76 missions: native production continuity. */'
# Each invalid location was a content ID owned by these earlier authored definitions.
LOCATION_REPAIRS = (
    ('port-ferry', 'port-garage', 'V28_DATA.incidents.port-ferry.steps[0].zone'),
    ('forge-memorydust', 'forge-low', 'V28_DATA.incidents.forge-memorydust.steps[0].zone'),
    ('forge-thirdshift', 'forge-garage', 'V28_DATA.incidents.forge-thirdshift.steps[1].zone'),
    ('velours-skins', 'velours-interiorB', 'V23_DATA.facilities.velours-skins.zone'),
    ('if-hidden', 'if-interiorB', 'V29_DATA.events.if-hidden.zone'),
    ('if-cellzero', 'if-low', 'V28_DATA.incidents.if-cellzero.steps[1].zone'),
    ('couronne-predict', 'couronne-high', 'V29_DATA.events.couronne-predict.zone'),
    ('couronne-venus', 'couronne-interiorC', 'V23_DATA.facilities.couronne-venus.zone'),
    ('station-substation', 'station-low', 'V23_DATA.facilities.station-substation.zone'),
    ('station-network', 'station-low', 'V22_DATA.consequences.station-network.zone'),
    ('port-network', 'port-low', 'V22_DATA.consequences.port-network.zone'),
    ('corniche-gardens', 'corniche-annex', 'V23_DATA.facilities.corniche-gardens.zone'),
    ('corniche-network', 'corniche-service', 'V22_DATA.consequences.corniche-network.zone'),
    ('velours-lastloge', 'velours-courtyard', 'V28_DATA.incidents.velours-lastloge.steps[1].zone'),
    ('forge-press', 'forge-interiorA', 'V29_DATA.events.forge-press.zone'),
    ('calanques-beacons', 'calanques-high', 'V28_DATA.incidents.calanques-beacons.steps[0].zone'),
    ('calanques-bodywater', 'calanques-service', 'V28_DATA.incidents.calanques-bodywater.steps[0].zone'),
    ('relais-prayer', 'relais-high', 'V28_DATA.incidents.relais-prayer.steps[0].zone'),
    ('relais-name', 'relais-low', 'V28_DATA.incidents.relais-name.steps[0].zone'),
    ('if-visit', 'if-courtyard', 'V28_DATA.incidents.if-visit.steps[0].zone'),
    ('if-ledger', 'if-interiorA', 'V23_DATA.facilities.if-ledger.zone'),
    ('couronne-clause', 'couronne-social', 'V28_DATA.incidents.couronne-clause.steps[0].zone'),
    ('couronne-prediction', 'couronne-high', 'V28_DATA.incidents.couronne-prediction.steps[1].zone'),
)


def once(text, old, new, label):
    return replace_once(text, old, new, 'v76 missions: ' + label)


def patch_production(body, runtime):
    for alias, target, _ in LOCATION_REPAIRS:
        old = "'" + alias + "'"
        count = 2 if alias == 'forge-memorydust' else 1
        if body.count(old) != count:
            raise ValueError('v76 missions: authored location drift: ' + alias)
        body = body.replace(old, "'" + target + "'")
    locations = [{'alias': a, 'zone': z, 'source': source} for a, z, source in LOCATION_REPAIRS]
    contract = 'const v76LocationRepairs=Object.freeze(' + json.dumps(locations, ensure_ascii=False) + '.map(Object.freeze));\n'
    body = once(body, 'function v43Setup(){', MARKER + '\n' + contract + runtime + '\nfunction v43Setup(){', 'source contract before setup43 and deferred saver37')
    body = once(body, '    window.__SOMA_MISSIONS75__?.restoreHotspotEnemy(q,z);z.robots.push(q);out.push(q);',
                '    v76RestoreEnemy(q,z);window.__SOMA_MISSIONS75__?.restoreHotspotEnemy(q,z);z.robots.push(q);out.push(q);', 'restore source story and gig combat records')
    body = once(body, 'function v43GigObject(z,g){const p=v43OpenPoint(z,`v43-gig-${g.id}`,.5);',
                "function v43GigObject(z,g){const p=v76GigPoint(z,g);if(!p){if(zone===z)announce('Borne de preuve inaccessible : aucun emplacement libre dans le passage existant.',3.5);return null;}", 'only proven parked-car gig marker uses reachable native candidates')
    body = once(body, 'function v43CompleteStoryStep(id,choice=null){', 'function v43CompleteStoryStep(id,choice=null,proof=null){', 'story transition proof')
    body = once(body, "const step=m.steps[s.step]; if(step.kind==='choice'&&choice)s.choice=choice;",
                "const step=m.steps[s.step];if(!v76AuthorizeStory(m,s,step,choice,proof))return false;window.__SOMA_V32__?.snapshotCombat?.();if(step.kind==='choice'&&choice)s.choice=choice;", 'prove stage before advancing')
    body = once(body, 'V43.tracked={kind:\'story\',id};v43Save(true);return true;', 'V43.tracked={kind:\'story\',id};v43Save(true);v43EnsureZone(zone);v76Checkpoint();return true;', 'checkpoint authored progress')
    body = once(body, 'function v43AcceptStory(id){', 'function v43AcceptStory(id,proof=v76CommandProof()){', 'physical story acceptance')
    body = once(body, "s.status!=='available'||v43ActiveStory())return false;", "s.status!=='available'||v43ActiveStory()||!v76ValidCommand(proof)||!v43StoryUnlocked(id))return false;", 'existing sequential unlock and console')
    body = once(body, 'function v43CloseStory(id){', 'function v43CloseStory(id,proof=v76CommandProof()){', 'physical story hand-in')
    body = once(body, "s.status!=='return'||s.paid)return false;\n  s.status='done';", "s.status!=='return'||s.paid||!v76ValidCommand(proof))return false;\n  s.status='done';", 'valid command callback')
    body = once(body, 'function v43AcceptGig(id){', 'function v43AcceptGig(id,proof=v76BoardProof(V43_GIG_BY_ID[id]?.district)){', 'physical gig acceptance')
    body = once(body, "s.status!=='available'||v43ActiveGigs().length>=3)return false;", "s.status!=='available'||v43ActiveGigs().length>=3||!v76ValidBoard(proof,g.district))return false;", 'existing district board')
    body = once(body, 'function v43MarkGigReturn(id){', 'function v43MarkGigReturn(id,proof=null){', 'gig objective proof')
    body = once(body, "s.status!=='active')return false;s.status='return';", "s.status!=='active'||!v76AuthorizeGig(g,s,proof))return false;window.__SOMA_V32__?.snapshotCombat?.();s.status='return';", 'no bare gig completion')
    body = once(body, 'function v43CloseGig(id){', 'function v43CloseGig(id,proof=v76BoardProof(V43_GIG_BY_ID[id]?.district)){', 'physical gig hand-in')
    body = once(body, "s.status!=='return'||s.paid)return false;s.status='done';", "s.status!=='return'||s.paid||!v76ValidBoard(proof,g.district))return false;s.status='done';", 'valid board callback')
    body = once(body, 'v43Channel={kind,id:o.id,zone:zone.id,', 'v43Channel={kind,id:o.id,core:state,root:V43,stories:V43.story,gigs:V43.gigs,zone:zone.id,', 'transient channel provenance')
    body = once(body, 'if(!c)return;if(paused||zone.id!==c.zone', 'if(!c)return;if(c.core!==state||c.root!==V43||c.stories!==V43.story||c.gigs!==V43.gigs||!v76Ready()||paused||zone.id!==c.zone', 'cancel imported dead or driven channel')
    body = once(body, '  const owner=`story-${m.id}-${s.step}`;', "  const proof=v76StoryProof(o);if(!proof)return false;const owner=`story-${m.id}-${s.step}`;", 'native current story point')
    body = once(body, 'v43CompleteStoryStep(m.id);return true;', 'v43CompleteStoryStep(m.id,null,proof);return true;', 'authored encounter proof')
    body = once(body, 'action:()=>v43CompleteStoryStep(m.id,id)', 'action:()=>v43CompleteStoryStep(m.id,id,proof)', 'choice source token')
    body = once(body, "()=>v43CompleteStoryStep(m.id));", "()=>{proof.channelReady=true;return v43CompleteStoryStep(m.id,null,proof)});", 'completed native channel proof')
    body = once(body, "  if(g.type==='combat'){const alive=", "  const proof=v76GigProof(o);if(!proof)return false;\n  if(g.type==='combat'){const alive=", 'native current gig point')
    body = once(body, 'return v43MarkGigReturn(g.id)}', 'return v43MarkGigReturn(g.id,proof)}', 'combat gig proof')
    body = once(body, '()=>v43MarkGigReturn(g.id));', '()=>{proof.channelReady=true;return v43MarkGigReturn(g.id,proof)});', 'completed gig channel proof')
    body = once(body, "  const lines=[`Mandats locaux", "  const proof=v76Proof(o,'v43FixerBoard');if(!v76ValidBoard(proof,district))return false;\n  const lines=[`Mandats locaux", 'native district board source')
    body = once(body, 'action:()=>v43CloseGig(g.id)', 'action:()=>v43CloseGig(g.id,proof)', 'stale gig hand-in')
    body = once(body, 'action:()=>v43AcceptGig(g.id)', 'action:()=>v43AcceptGig(g.id,proof)', 'stale gig acceptance')
    body = once(body, 'v43RefreshUnlocks();const active=v43ActiveStory(),returns=', 'const proof=v76Proof(o,\'v43CampaignConsole\');if(!v76ValidCommand(proof))return false;v43RefreshUnlocks();const active=v43ActiveStory(),returns=', 'native command source')
    body = once(body, 'action:()=>v43CloseStory(m.id)', 'action:()=>v43CloseStory(m.id,proof)', 'stale story hand-in')
    body = once(body, 'action:()=>v43AcceptStory(m.id)', 'action:()=>v43AcceptStory(m.id,proof)', 'stale story acceptance')
    body = once(body, 'v43Save(true);announce(`${g.title} · contrat accepté`', 'v43Save(true);v43EnsureZone(zone);announce(`${g.title} · contrat accepté`', 'spawn same-zone gig objective immediately')
    return body


def patch_saver(body):
    body = once(body, "window.__SOMA_MISSIONS75__?.knownHotspotEnemy(id,zoneId)===true;", "(window.__SOMA_MISSIONS75__?.knownHotspotEnemy(id,zoneId)===true||window.__SOMA_MISSIONS76__?.knownEnemy(id,zoneId)===true);", 'bounded authored43 identities with exact zones')
    return once(body, "window.__SOMA_MISSIONS75__?.legacyLootRole(id,l.zone,l.role)||", "window.__SOMA_MISSIONS76__?.legacyLootRole(id,l.zone,l.role)||window.__SOMA_MISSIONS75__?.legacyLootRole(id,l.zone,l.role)||", 'only source blade legacy loot')


def patch_city(body):
    body = once(body, "schema:'soma-city/45',revision:1,", "schema:'soma-city/45',revision:1,uiTab:'operations',", 'native optional UI field exists in fresh owner45')
    return once(body, 'const next={...fresh,...raw};',
                "const next={...fresh,...raw};next.uiTab=['operations','calls','fleet','runs','city'].includes(raw.uiTab)?raw.uiTab:fresh.uiTab;", 'normalize old local owner45 UI preference')


def patch_group(body):
    return once(body, 'for(const[v,m]of Object.entries(p.modules))C.shape(m.value,api(v).state());',
                "for(const[v,m]of Object.entries(p.modules)){if(v==='45'){if(!Object.hasOwn(m.value,'uiTab'))m.value.uiTab='operations';if(!['operations','calls','fleet','runs','city'].includes(m.value.uiTab))throw Error('Onglet du dossier45 invalide.');}C.shape(m.value,api(v).state());}", 'only known optional45 field defaults before strict grouped shape validation')


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Missions v76 déjà appliquées.')
    if html.count('id="soma-v75-edition"') != 1:
        raise ValueError('Parent v75 requis pour les missions v76.')
    runtime = scripts.get('missions-runtime')
    if not isinstance(runtime, str) or not runtime.strip() or '</script' in runtime.lower():
        raise ValueError('Module missions v76 invalide.')
    html = rewrite_script(html, 'soma-v43-production', lambda body: patch_production(body, runtime))
    html = rewrite_script(html, 'soma-v37-persistence', patch_saver)
    html = rewrite_script(html, 'soma-v45-city', patch_city)
    return rewrite_script(html, 'soma-v64-group-runtime', patch_group)


def patch_viewer(html, scripts):
    return html
