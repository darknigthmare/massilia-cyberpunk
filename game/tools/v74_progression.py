"""Repair Act III through the existing v45, v32 and v37 owners."""
from build_v68 import replace_once, rewrite_script

MODULES = ('progression-runtime',)
MARKER = '/* SOMA v74 progression: physical objectives and encounter continuity. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v74 progression: ' + label)


def patch_city(body, runtime):
    body = once(body, "{zone:'corniche-route',kind:'drive',label:'Poursuivre le relais jusqu’à la Corniche'}",
                "{zone:'corniche-exterior',kind:'drive',label:'Poursuivre le relais jusqu’à la Corniche'}", 'reachable authored street destination')
    body = once(body, "{zone:'corniche-route',kind:'combat',count:4,label:'Neutraliser l’escorte de la balise'}",
                "{zone:'corniche-exterior',kind:'combat',count:4,label:'Neutraliser l’escorte de la balise'}", 'encounter at the existing street arrival')
    body = once(body, 'function v45Setup(){', MARKER + '\n' + runtime + '\nfunction v45Setup(){', 'helpers in real owner')
    body = once(body, 'function v45CompleteOperationStep(id,choice=null){',
                'function v45CompleteOperationStep(id,choice=null,proof=null){', 'step proof argument')
    body = once(body, 'const step=op.steps[s.step];if(!step)return false;s.choice=choice??s.choice;',
                'const step=op.steps[s.step];if(!step||!v74AuthorizeStep(op,s,step,choice,proof))return false;window.__SOMA_V32__?.snapshotCombat?.();s.choice=choice??s.choice;', 'validate before progress')
    body = once(body, 'function v45CloseOperation(id){',
                'function v45CloseOperation(id,proof=v74CommandProof()){', 'physical hand-in argument')
    body = once(body, "if(!op||!s||s.status!=='return'||s.paid)return false;s.status='done';",
                "if(!op||!s||s.status!=='return'||s.paid||!v74ValidCommand(proof))return false;s.status='done';", 'physical hand-in owner')
    body = once(body, 'v45ClearDestination();v45Save(true);v45RebuildCurrent();announce(`${op.title}',
                'v45ClearDestination();v45Save(true);v74Checkpoint();v45RebuildCurrent();announce(`${op.title}', 'reward checkpoint in existing campaign saver')
    body = once(body, 'z.robots.push(q);out.push(q)}return out}',
                'v74RestoreEnemy(q,z);z.robots.push(q);out.push(q)}return out}', 'restore existing v32 combat records')
    body = once(body, "const roles=boss?['heavy']:['rifle','melee','sniper','netrunner']",
                "const roles=boss?['heavy']:['rifle','blade','sniper','netrunner']", 'existing v32 blade role and loot validator')
    body = once(body, 'maxHealth:isBoss?560:150', 'maxHealth:isBoss?560:Math.max(150,115+(i%3)*18)', 'authored health never exceeds its own maximum')
    body = once(body, 'v45Channel={kind,id,o,duration,elapsed:0,startX:camera.x,startZ:camera.z,onComplete};',
                'v45Channel={kind,id,o,duration,elapsed:0,startX:camera.x,startZ:camera.z,onComplete,core:state,zone};', 'transient channel provenance')
    body = once(body, 'if(paused||state.driving||zone.interactables?.indexOf(c.o)<0',
                'if(c.core!==state||c.zone!==zone||!v74PlayerReady()||paused||state.driving||zone.interactables?.indexOf(c.o)<0', 'channel restore/death cancellation')
    body = once(body, 'const op=V45_OPERATION_BY_ID[o.operationId],s=op&&v45OperationState(op.id),step=op?.steps[o.step];if(!op||!s||!step)return false;',
                'const op=V45_OPERATION_BY_ID[o.operationId],s=op&&v45OperationState(op.id),step=op?.steps[o.step],proof=v74StepProof(o);if(!op||!s||!step||!proof)return false;', 'real objective and callback token')
    body = once(body, '()=>v45CompleteOperationStep(op.id));',
                '()=>{proof.channelReady=true;return v45CompleteOperationStep(op.id,null,proof)});', 'completed channel proof')
    body = once(body, "if(step.kind==='drive'){if(state.driving)return v45CompleteOperationStep(op.id);",
                "if(step.kind==='drive'){", 'drive requires actual sector transfer')
    body = once(body, 'return v45CompleteOperationStep(op.id)}',
                'return v45CompleteOperationStep(op.id,null,proof)}', 'combat proof')
    body = once(body, 'action:()=>v45CompleteOperationStep(op.id,id)',
                'action:()=>v45CompleteOperationStep(op.id,id,proof)', 'choice checks captured source')
    body = once(body, "step.zone===to&&state.driving)v45CompleteOperationStep(op.id)",
                "step.zone===to&&state.driving)v45CompleteOperationStep(op.id,null,v74DriveProof(op.id,from))", 'actual drive transition proof')
    body = once(body, "function v45RebuildCurrent(){if(!zone||typeof buildZone!=='function')return false;const pose=",
                "function v45RebuildCurrent(){if(!zone||typeof buildZone!=='function')return false;const carried=v45CurrentVehicle();const pose=", 'retain driven native vehicle before objective rebuild')
    body = once(body, 'zone.static=null;buildZone(zone);renderer?.uploadStatic?.(zone.static);',
                'zone.static=null;buildZone(zone);if(carried&&state.driving===carried.id){zone.vehicles=zone.vehicles.filter(v=>v.id!==carried.id);zone.vehicles.push(carried);}renderer?.uploadStatic?.(zone.static);', 'restore driven native object after objective rebuild')
    body = once(body, 'function v45CommandDialogue(){const active=',
                'function v45CommandDialogue(){const proof=v74CommandProof();if(!proof)return false;const active=', 'real command console')
    body = once(body, 'action:()=>v45CloseOperation(active.id)',
                'action:()=>v45CloseOperation(active.id,proof)', 'stale command callback protection')
    body = once(body, 'if(!root)return;V45.uiTab=tab;',
                'if(!root)return;v74MigrateRoute();const proof=v74CommandProof();V45.uiTab=tab;', 'menu source for hand-in')
    body = once(body, 'v45RefreshOperationUnlocks();v45LastZoneId=zone.id;',
                'v45RefreshOperationUnlocks();v74MigrateRoute();v45LastZoneId=zone.id;', 'migrate only the owned legacy objective route at startup')
    body = once(body, "s.status==='return'?'Dossier prêt pour remise'",
                "s.status==='return'?'Preuves prêtes · remise au centre des opérations de Station Zéro'", 'return destination in dossier')
    body = once(body, "${s.status==='return'?`<button data-v45-close-op=\"${op.id}\">Remettre</button>`:''}",
                "${s.status==='return'?`<button data-v45-return-op=\"${op.id}\">Tracer la remise</button>${proof?`<button data-v45-close-op=\"${op.id}\">Remettre · ${op.reward} CR</button>`:''}`:''}", 'remote menu guides physical hand-in')
    body = once(body, "for(const b of root.querySelectorAll?.('[data-v45-close-op]')||[])b.onclick=()=>{v45CloseOperation(b.dataset.v45CloseOp);",
                "for(const b of root.querySelectorAll?.('[data-v45-return-op]')||[])b.onclick=()=>v74ReturnGuide(b.dataset.v45ReturnOp);for(const b of root.querySelectorAll?.('[data-v45-close-op]')||[])b.onclick=()=>{v45CloseOperation(b.dataset.v45CloseOp,proof);", 'menu hand-in bindings')
    return body


def patch_html(html, scripts):
    if MARKER in html:
        raise ValueError('Progression v74 déjà appliquée.')
    if html.count('id="soma-v73-edition"') != 1:
        raise ValueError('Parent v73 requis pour la progression v74.')
    runtime = scripts.get('progression-runtime')
    if not isinstance(runtime, str) or not runtime.strip() or '</script' in runtime.lower():
        raise ValueError('Module progression v74 invalide.')
    html = rewrite_script(html, 'soma-v45-city', lambda body: patch_city(body, runtime))
    html = rewrite_script(html, 'soma-v37-persistence', patch_saver)
    return rewrite_script(html, 'soma-v64-group-runtime', lambda body: once(body,
        '  // Force a validated final campaign checkpoint after module roots are settled.',
        '  window.__SOMA_PROGRESSION74__?.sync?.();\n  // Force a validated final campaign checkpoint after module roots are settled.',
        'reconcile the existing route after grouped module roots settle'))


def patch_saver(body):
    body = once(body,
        "function enemyIdKnown(id,k){if(typeof id==='string'&&id.startsWith('v36-'))",
        "function enemyIdKnown(id,k,zoneId=null){if(typeof id==='string'&&id.startsWith('v45-'))return k.edition>=37&&window.__SOMA_PROGRESSION74__?.knownEnemy(id,zoneId)===true;if(typeof id==='string'&&id.startsWith('v36-'))",
        'strict content45 enemy and loot identities')
    body = once(body, "if(!enemyIdKnown(id,k))fail('Adversaire'", "if(!enemyIdKnown(id,k,z))fail('Adversaire'", 'enemy zone ownership')
    body = once(body, 'enemyIdKnown(id.slice(5),k)', 'enemyIdKnown(id.slice(5),k,l.zone)', 'loot zone ownership')
    body = once(body, "member(l.role,k.roles,'Butin')",
                "member(window.__SOMA_PROGRESSION74__?.legacyLootRole(id,l.zone,l.role)||l.role,k.roles,'Butin')", 'exact historical asphalte blade loot role')
    body = once(body, 'for(const partMap of Object.values(q.enemyParts))',
                'for(const [partZone,partMap] of Object.entries(q.enemyParts))', 'localized damage zone ownership')
    return once(body, "if(!enemyIdKnown(id,k))fail('Partie ennemie'", "if(!enemyIdKnown(id,k,partZone))fail('Partie ennemie'", 'localized damage identities')


def patch_viewer(html, scripts):
    return html
