// Headless smoke test: shim a DOM, run the app + exercises in one scope.
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const appdata = html.match(/<script id="appdata"[^>]*>([\s\S]*?)<\/script>/)[1];
const main = html.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/)[1];

function mkEl(id) {
  return {
    id, _html: '', style: {}, dataset: {}, textContent: '', value: '', firstChild: null,
    classList: { add(){}, remove(){}, toggle(){}, contains(){return false;} },
    get innerHTML(){return this._html;}, set innerHTML(v){this._html=String(v);},
    appendChild(){}, insertBefore(){}, addEventListener(){}, removeAttribute(){},
    setAttribute(){}, focus(){}, remove(){}, querySelectorAll(){return withForEach([]);},
    querySelector(){return mkEl('q');}, onclick:null,
  };
}
function withForEach(a){ a.forEach = Array.prototype.forEach.bind(a); return a; }
const store = {};
const doc = {
  getElementById: id => id === 'appdata' ? { textContent: appdata } : mkEl(id),
  querySelectorAll: () => withForEach([mkEl('a'), mkEl('b')]),
  querySelector: () => mkEl('q'),
  createElement: () => mkEl('c'),
  body: { classList: { add(){}, remove(){}, toggle(){}, contains(){return false;} }, appendChild(){}, insertBefore(){}, firstChild:null },
};
global.document = doc;
global.window = global;
global.scrollTo = () => {};
global.localStorage = { getItem: k => store[k] || null, setItem: (k,v)=>store[k]=v, removeItem: k=>delete store[k] };
global.navigator = { serviceWorker: { register: () => Promise.resolve() } };
global.Audio = class { play(){return Promise.resolve();} pause(){} };
global.confirm = () => false; global.alert = () => {};
global.location = { reload(){} };
global.__errors = [];
global.__T = (label, fn) => { try { fn(); } catch (e) { global.__errors.push(label + ': ' + e.message); } };

const exercise = `
;(function(){
  var T = globalThis.__T;
  ['home','lessons','drill','cards','ref'].forEach(t => T('go '+t, () => go(t)));
  DATA.lessons.forEach(l => T('openLesson '+l.id, () => openLesson(l.id)));
  Object.keys(GEN).forEach(g => T('GEN.'+g, () => {
    for (var i=0;i<50;i++){ var r = g==='vocab'?GEN.vocab(allVocab()):GEN[g]();
      if(!r || r.av==null || r.ru==null) throw new Error('bad result '+JSON.stringify(r)); }
  }));
  DATA.lessons.filter(l=>l.drill).forEach(l => T('drill '+l.id, () => {
    drillMount('main', l.drill, 'L:'+l.id, l.t);
    for(var i=0;i<10;i++){ drillShow('main'); drillGrade('main', Math.random()<0.5?1:0); }
    drillMode('main', true); drillCheck('main'); drillNew('main'); drillMode('main', false);
  }));
  T('translit', () => { ['гӀеч','кӀудияб','цӀар','дун вачӀана'].forEach(w=>{ if(typeof translit(w)!=='string') throw new Error('translit'); }); });
  T('streak/day', () => { recDay(); if(typeof streak()!=='number') throw new Error('streak'); });
  T('onboard', () => { maybeOnboard(); pickGender('f'); pickGender('m'); });
  T('pron', () => { if(!pron('гӀеч').includes('ipa')) throw new Error('pron'); });
  T('cards', () => { renderCards(); buildDeck(); showCard(); flipCard(); gradeCard(1); gradeCard(0); gradeCard(2); });
  ['alpha','phr','voc','gram'].forEach(rt => T('ref '+rt, () => { refTab=rt; renderRef(); }));
  T('vocSearch', () => { refTab='voc'; renderRef(); vocSearch(); });
  T('toggles', () => { toggleIpa(); toggleGender(); toggleGender(); toggleIpa(); });
  T('finishLesson', () => finishLesson(DATA.lessons[0].id));
  T('drillJump', () => drillJump('L:'+DATA.lessons[1].id, DATA.lessons[1].t));
})();
`;

try { eval(main + exercise); }
catch (e) { console.error('BOOT/RUN ERROR:', e.message); process.exit(1); }

if (global.__errors.length) { console.error('RUNTIME ERRORS:\n' + global.__errors.join('\n')); process.exit(1); }
console.log('ALL OK — no runtime errors across views, generators, drills, cards, reference.');
