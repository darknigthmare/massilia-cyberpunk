/* Marseille augmentée: reversible cyberpunk atmosphere, shared geographic sources. */
(function () {
  'use strict';
  const VERSION = '0.68.0', KEY = 'soma-massilia-v68-visual';
  let ambience = 'cyberpunk', installed = false;
  try {
    const previous = localStorage.getItem(KEY);
    if (previous === 'neutral') ambience = 'neutral';
    if (previous === 'wasteland') localStorage.setItem(KEY, 'cyberpunk');
  } catch {}

  function applyAmbience() {
    document.body.classList.remove('soma-wasteland68');
    document.body.classList.toggle('soma-cyberpunk68', ambience === 'cyberpunk');
  }

  function options() {
    const panel = document.querySelector('#options .panel');
    if (!panel || panel.querySelector('[data-v68-ambience]')) return;
    const group = document.createElement('fieldset');
    group.className = 'v68-options';
    const legend = document.createElement('legend'); legend.textContent = 'Marseille augmentée';
    const label = document.createElement('label'); label.textContent = 'Ambiance visuelle ';
    const select = document.createElement('select'); select.dataset.v68Ambience = '1';
    for (const [value, text] of [['cyberpunk','Néons & nuit méditerranéenne'], ['neutral','Sans filtre']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = text;
      select.append(option);
    }
    select.value = ambience;
    select.onchange = () => {
      ambience = select.value; applyAmbience();
      try { localStorage.setItem(KEY, ambience); } catch {}
    };
    label.append(select); group.append(legend, label);
    const note = document.createElement('p');
    note.textContent = 'Des lumières cyan, magenta et ambre dans la ville méditerranéenne. Le filtre colore le rendu ; les éclairages de façade restent présents en mode sans filtre.';
    group.append(note); panel.append(group);
  }

  function snapshot() {
    const cells = [...(window.__SOMA_V52__?.zones().values() || [])]
      .filter(z => z.v68Architecture).map(z => ({id:z.v52CellId, ...z.v68Architecture}));
    return {version:VERSION, ambience, referenceCount:window.__SOMA_ARCH68__.referenceCount(), cells,
      sourceGeometryUnchanged:true, newGeographicCells:0, completeMarseille:false,
      note:'Matériaux sans tag et éclairages cyberpunk interprétés ; géographie inchangée et toits incomplets conservés à plat.'};
  }

  function css() {
    const style = document.createElement('style'); style.id = 'soma-v68-style';
    style.textContent = '.soma-cyberpunk68 #gl{filter:saturate(1.12) contrast(1.045)}' +
      '.v68-options{margin:14px 0;padding:14px;border:1px solid #285462;background:#081820}' +
      '.v68-options legend{color:#84e0e8}.v68-options label{display:flex;gap:12px;align-items:center;flex-wrap:wrap}' +
      '.v68-options p{color:#a0babf;line-height:1.5;margin-bottom:0}';
    document.head.append(style);
  }

  function setup() {
    if (!window.__SOMA_V67__ || !window.__SOMA_ARCH68__) {setTimeout(setup, 120); return;}
    if (installed) return; installed = true;
    css(); applyAmbience(); options();
    const baseOpen = openModal;
    openModal = function (id, ...args) {
      const result = baseOpen(id, ...args); if (id === 'options') options(); return result;
    };
    window.__SOMA_V68__ = {version:VERSION, snapshot, ambience:() => ambience};
    window.__SOMA__.version = VERSION;
    document.title = 'SOMA//MASSILIA 0.68 — Marseille augmentée';
    const edition = document.querySelector('.v34-edition span'); if (edition) edition.textContent = '0.68';
    const hudEdition = document.querySelector('.topbar .brand small'); if (hudEdition) hudEdition.textContent = '0.68';
    const lead = document.querySelector('.v34-lead');
    if (lead) lead.textContent = 'La ville réelle, les vies augmentées. Explorez les rues et les reliefs de Marseille, entre façades méditerranéennes, fenêtres éclairées et néons de quartier.';
    const diagnostic = window.__SOMA_UI66__?.diagnostic;
    if (diagnostic) window.__SOMA_UI66__.diagnostic = () => ({...diagnostic(), architecture:snapshot()});
  }
  setup();
})();
