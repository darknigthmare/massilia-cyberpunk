"""Bounded, observed radio evidence in derived v72 scripts; parents stay frozen."""
from build_v68 import replace_once, rewrite_script

MODULES = ('contact-sharing-runtime',)
MARKER = '/* SOMA v72 observed contact radio. */'


def once(text, old, new, label):
    return replace_once(text, old, new, 'v72 contact sharing: ' + label)


def patch_perception(body):
    if body.count('root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();') != 1:
        raise ValueError('Ancre différente : v72 reset partagé')
    body = once(body, 'activeZone=null,previousPose=null', 'activeZone=null,activeZoneId=null,previousPose=null', 'identité de zone')
    body = once(body,
        'if(current!==activeZone){reset();activeZone=current;}',
        'if(current!==activeZone||(current?.id??null)!==activeZoneId){reset();activeZone=current;activeZoneId=current?.id??null;}',
        'transfert même objet')
    body = once(body, 'let pending=[],contacts=[],output=', 'let pending=[],output=', 'retrait ancien bus caméra')
    body = once(body, 'pending=[];contacts=[];output=', 'pending=[];output=', 'reset ancien bus')
    body = once(body, '    contacts=contacts.filter(row=>memory.clock-row.at<K.CONFIG.memorySeconds);\n', '', 'retrait ancienne file de contacts')
    body = once(body, 'const previousOutput=output,trackMap=', 'const trackMap=', 'mémoire sans retransmission implicite')
    body = once(body, '    const groups=new Map(robots.map((q,i)=>[q.id,q.v33Squad||`${current.id}:${Math.floor(i/4)}`]));\n', '', 'ancien regroupement sans portée')
    body = once(body, 'const eligible=robots.filter(q=>!q.v26BossId&&!root.__SOMA_BOSSES36__?.suspended(q));',
        'const eligible=robots.filter(q=>!q.v26BossId&&!root.__SOMA_BOSSES36__?.suspended(q)).slice(0,K.CONFIG.maxObservers);', 'budget observateurs')
    start = "        const shared=contacts.at(-1)||[...previousOutput.values()].find(row=>row.confirmed&&row.lastKnown&&groups.get(row.id)===groups.get(q.id));"
    end = "        }else foreign.set(q.id,{left:5,phase:q.state==='combat'?'combat':'search',detect:clamp(q.detect||0,0,1.2)});"
    a = body.find(start)
    b = body.find(end, a)
    if a < 0 or b < 0 or body.count(start) != 1 or body.count(end) != 1:
        raise ValueError('Ancre différente : v72 anciens partages implicites')
    body = body[:a] + "        foreign.set(q.id,{left:5,phase:q.state==='combat'?'combat':'search',detect:clamp(q.detect||0,0,1.2)});" + body[b+len(end):]
    body = once(body, 'memory=next.state;hud=next.hud;',
        "root.__SOMA_CONTACT_SHARING72__?.exchange('tactical',next,entities);memory=next.state;hud=next.hud;", 'évidence tactique')
    body = once(body, 'reset();activeZone=zoneNow();root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();',
        'reset();activeZone=zoneNow();activeZoneId=activeZone?.id??null;root.__SOMA_LEGACY_PERCEPTION71__?.reset?.();root.__SOMA_CONTACT_SHARING72__?.reset?.();', 'import et reset explicites')
    # The obsolete public camera hook remains a compatibility entry point, but
    # resolves a live object and delegates to the same checked radio service.
    start = "  function reportContact(sourceId,position,kind='camera'){"
    end = '  function isMachine(q){'
    if body.count(start) != 1 or body.count(end) != 1:
        raise ValueError('Ancre différente : v72 contact caméra public')
    a = body.index(start)
    b = body.index(end, a)
    body = body[:a] + "  function reportContact(sourceId,position,kind='camera'){const q=zoneNow()?.robots?.find(q=>q.id===sourceId);return kind==='camera'&&!!root.__SOMA_CONTACT_SHARING72__?.cameraContact(q,position);}\n" + body[b:]
    return body


def patch_legacy(body):
    body = once(body, 'memory=next.state;output=new Map(next.observers.map(row=>[row.id,row]));',
        "root.__SOMA_CONTACT_SHARING72__?.exchange('legacy',next,entities);memory=next.state;output=new Map(next.observers.map(row=>[row.id,row]));", 'évidence police et sécurité')
    return once(body, 'beginFrame,observer,reportNoise,reset,snapshot',
        'beginFrame,observer,reportNoise,reset:()=>{reset();root.__SOMA_CONTACT_SHARING72__?.reset?.();},snapshot', 'reset legacy public')


def patch_camera(body):
    if body.count("window.__SOMA_PERCEPTION70__?.reportContact(q.id,{x:camera.x,z:camera.z},'camera');for") != 1:
        raise ValueError('Ancre différente : v72 contact caméra')
    return once(body,
        "window.__SOMA_PERCEPTION70__?.reportContact(q.id,{x:camera.x,z:camera.z},'camera');for(const g of zone.robots||[])if(g.v32Enemy&&g.health>0){g.state='combat';g.detect=1;g.hostile=true}",
        'window.__SOMA_CONTACT_SHARING72__?.cameraContact(q,{x:camera.x,z:camera.z});', 'caméra sans alerte globale')


def patch_html(html, scripts):
    if MARKER in html or 'id="soma-v72-contact-sharing-runtime"' in html:
        raise ValueError('Relais de contacts v72 déjà appliqué.')
    html = rewrite_script(html, 'soma-v70-perception-runtime', patch_perception)
    html = rewrite_script(html, 'soma-v71-legacy-perception-runtime', patch_legacy)
    html = rewrite_script(html, 'soma-v42-recovery', patch_camera)
    text = scripts['contact-sharing-runtime']
    if not isinstance(text, str) or '</script' in text.lower():
        raise ValueError('Module radio v72 invalide.')
    return once(html, '</body>', '\n<script id="soma-v72-contact-sharing-runtime">\n' + MARKER + '\n' + text + '\n</script>\n</body>', 'module après noyaux et adaptateurs')
