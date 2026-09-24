"""Сборка статической страницы рейтинга (docs/index.html)."""
import html
import json

TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚽</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;700&family=Unbounded:wght@500;800&display=swap" rel="stylesheet">
<style>
:root{
  --wall:#E8ECEF; --paper:#FFFFFF; --ink:#13212C; --muted:#5E6E7B;
  --court:#1B5B84; --court-deep:#144766; --line:#F2A33A; --rule:#D3DAE0;
  --yellow:#E8C23A; --red:#C8423B;
  --display:"Unbounded","Arial Black",system-ui,sans-serif;
  --text:"Onest",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--wall);color:var(--ink);font:16px/1.5 var(--text);
  padding-bottom:env(safe-area-inset-bottom,0px)}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}

/* Площадка: единственный яркий элемент страницы */
.court{position:relative;background:var(--court);color:#fff;overflow:hidden;
  padding:calc(40px + env(safe-area-inset-top,0px)) 0 44px}
.court::before,.court::after{content:"";position:absolute;pointer-events:none}
.court::before{left:50%;top:-1px;bottom:-1px;border-left:2px solid rgba(255,255,255,.35)}
.court::after{left:50%;top:50%;width:220px;height:220px;margin:-110px 0 0 -110px;
  border:2px solid rgba(255,255,255,.35);border-radius:50%}
.court .arc{position:absolute;top:50%;width:170px;height:260px;margin-top:-130px;
  border:2px solid rgba(255,255,255,.35);border-radius:50%}
.court .arc.l{left:-95px}.court .arc.r{right:-95px}
.court .wrap{position:relative;z-index:1}
.court h1{font:800 clamp(40px,9vw,88px)/1 var(--display);margin:0;letter-spacing:-.01em}
.court p{margin:14px 0 0;font-size:18px;color:rgba(255,255,255,.85);max-width:32em}
.court .upd{font-size:14px;color:rgba(255,255,255,.7);margin-top:6px}

.controls{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between;
  margin:28px 0 16px}
.seg{display:inline-flex;background:var(--paper);border:1px solid var(--rule);border-radius:10px;padding:3px}
.seg button{font:500 15px var(--text);color:var(--muted);background:none;border:0;border-radius:7px;
  padding:8px 14px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
.seg button:focus-visible,.sort:focus-visible{outline:3px solid var(--line);outline-offset:2px}
.sortbox{font-size:15px;color:var(--muted)}
.sort{font:500 15px var(--text);background:none;border:0;border-bottom:2px solid transparent;
  color:var(--muted);padding:4px 2px;margin-left:10px;cursor:pointer}
.sort[aria-pressed="true"]{color:var(--ink);border-color:var(--line)}

.board{background:var(--paper);border:1px solid var(--rule);border-radius:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:760px;font-variant-numeric:tabular-nums}
th,td{padding:11px 10px;text-align:right;white-space:nowrap}
th{font-size:13px;font-weight:500;color:var(--muted);border-bottom:1px solid var(--rule)}
th.l,td.l{text-align:left}
tbody tr+tr td{border-top:1px solid #EEF1F3}
td.place{width:44px;color:var(--muted);text-align:center}
td.name{position:sticky;left:0;background:var(--paper)}
.nm{font-weight:500}
.pos{display:block;font-size:13px;color:var(--muted)}
td.total{font:800 18px var(--display)}
#board th:nth-child(4),#board td.pm{padding-right:22px;border-right:1px solid #EEF1F3}
td.pm{font-weight:700}
tr.leader td.place{box-shadow:inset 4px 0 0 var(--line);color:var(--ink);font-weight:700}
.card{display:inline-block;width:9px;height:13px;border-radius:2px;vertical-align:-1px;margin-right:4px}
.card.y{background:var(--yellow)}.card.r{background:var(--red)}
.zero{color:#B4BEC6}
.empty{padding:40px 20px;text-align:center;color:var(--muted)}

h2{font:500 22px/1.2 var(--display);margin:48px 0 14px}
.matches{list-style:none;margin:0;padding:0;background:var(--paper);border:1px solid var(--rule);border-radius:12px}
.matches li{display:grid;grid-template-columns:150px 1fr;gap:4px 16px;padding:12px 16px;align-items:baseline}
.matches li+li{border-top:1px solid #EEF1F3}
.matches .d{color:var(--muted);font-size:14px}
.matches .sc{font-weight:700;font-variant-numeric:tabular-nums}
.matches .mvp{grid-column:2/3;font-size:14px;color:var(--muted)}
.matches a{color:inherit}
.how{margin:48px 0 56px;max-width:68ch;color:var(--muted);font-size:15px}
.how p{margin:.4em 0}
@media (max-width:560px){
  .matches li{grid-template-columns:1fr}.matches .d,.matches .mvp{grid-column:1/2}
}
/* кнопка-фамилия */
.pl{font:500 16px var(--text);color:var(--ink);background:none;border:0;padding:0;cursor:pointer;text-align:left;
  border-bottom:1px dashed #9FB0BD}
.pl:hover{color:var(--court);border-color:var(--court)}
.pl:focus-visible{outline:3px solid var(--line);outline-offset:2px}

/* карточка игрока */
.sheet{position:fixed;inset:0;z-index:50;display:flex;justify-content:flex-end;background:rgba(19,33,44,.45)}
.sheet[hidden]{display:none}
.panel{background:var(--wall);width:min(640px,100%);height:100%;overflow-y:auto;
  padding:0 0 calc(32px + env(safe-area-inset-bottom,0px));box-shadow:-12px 0 32px rgba(0,0,0,.18)}
.ph{background:var(--court);color:#fff;padding:calc(20px + env(safe-area-inset-top,0px)) 24px 22px;position:relative}
.ph h3{font:800 clamp(24px,5vw,34px)/1.1 var(--display);margin:0 44px 6px 0}
.ph .sub{color:rgba(255,255,255,.82);font-size:15px}
.ph .sub a{color:#fff}
.x{position:absolute;right:14px;top:calc(14px + env(safe-area-inset-top,0px));width:40px;height:40px;border-radius:50%;
  border:0;background:rgba(255,255,255,.15);color:#fff;font-size:24px;line-height:1;cursor:pointer}
.x:focus-visible{outline:3px solid var(--line)}
.pb{padding:0 20px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:20px 0}
.tile{background:var(--paper);border:1px solid var(--rule);border-radius:10px;padding:12px}
.tile b{display:block;font:800 22px/1.2 var(--display);font-variant-numeric:tabular-nums}
.tile span{font-size:13px;color:var(--muted)}
.tile.hl{border-color:var(--line);box-shadow:inset 0 3px 0 var(--line)}
.blk{background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:14px 16px;margin:12px 0}
.blk h4{font:500 16px var(--display);margin:0 0 10px}
.kv{display:grid;grid-template-columns:1fr auto;gap:6px 16px;font-size:15px}
.kv dt{color:var(--muted)}.kv dd{margin:0;font-weight:500;text-align:right;font-variant-numeric:tabular-nums}
.chart svg{width:100%;height:auto;display:block}
.lg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--muted);margin-top:8px}
.lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:0}
.log{overflow-x:auto}
.log table{min-width:520px}
.log td,.log th{padding:8px 6px;font-size:14px}
.res{display:inline-block;min-width:22px;text-align:center;border-radius:4px;font-weight:700;font-size:12px;padding:1px 4px}
.res.w{background:#DCEBF5;color:var(--court-deep)}.res.d{background:#ECEFF2;color:var(--muted)}.res.l{background:#F8E1DF;color:#9A322C}
.star{color:var(--line)}
.note{font-size:14px;color:var(--muted);margin:14px 0}
.linkbtn{font:500 14px var(--text);background:none;border:0;color:var(--court);cursor:pointer;padding:0;text-decoration:underline}
@media (max-width:560px){ .tiles{grid-template-columns:repeat(2,1fr)} .pb{padding:0 14px} }
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<header class="court">
  <span class="arc l"></span><span class="arc r"></span>
  <div class="wrap">
    <h1>__TEAM__</h1>
    <p>Рейтинг игроков по протоколам РФЛ и опросу команды</p>
    <div class="upd">Обновлено __UPDATED__</div>
  </div>
</header>
<main class="wrap">
  <div class="controls">
    <div class="seg" id="groups" role="group" aria-label="Турнир"></div>
    <div class="sortbox">Сортировать:
      <button class="sort" data-sort="total" aria-pressed="true">по общему баллу</button>
      <button class="sort" data-sort="per_match" aria-pressed="false">по баллам за матч</button>
    </div>
  </div>
  <div class="board" id="board"></div>
  <h2>Матчи</h2>
  <ul class="matches" id="matches"></ul>
  <section class="how" id="how"></section>
</main>
<div class="sheet" id="sheet" hidden><div class="panel" id="panel" role="dialog" aria-modal="true" aria-labelledby="pname"></div></div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const order = ['championship','cup','all'];
let group = order.find(k => D.groups[k] && D.groups[k].matches.length) || 'all';
let sortKey = 'total';
const fmt = n => (Math.round(n*100)/100).toLocaleString('ru-RU');
const z = n => n ? n : '<span class="zero">0</span>';
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function renderGroups(){
  const box = document.getElementById('groups');
  box.innerHTML = order.filter(k => D.groups[k]).map(k =>
    `<button data-g="${k}" aria-pressed="${k===group}">${esc(D.groups[k].title)}</button>`).join('');
  box.querySelectorAll('button').forEach(b => b.onclick = () => { group = b.dataset.g; draw(); });
}
function renderBoard(){
  const g = D.groups[group];
  const rows = [...g.players].sort((a,b) => b[sortKey]-a[sortKey] || b.total-a.total);
  const el = document.getElementById('board');
  if (!rows.length){ el.innerHTML = '<div class="empty">В этом турнире пока нет сыгранных матчей. Рейтинг появится после первого протокола на сайте лиги.</div>'; return; }
  el.innerHTML = `<table><thead><tr>
    <th>Место</th><th class="l">Игрок</th><th>Балл</th><th>За матч</th><th title="Игры">И</th><th title="Голы">Г</th>
    <th title="Голевые передачи">П</th><th title="Лучший игрок матча">ЛИ</th>
    <th title="Желтые карточки">ЖК</th><th title="Красные карточки">КК</th>
    <th title="Бонус вратаря">Бонус вр.</th></tr></thead><tbody>` +
    rows.map((r,i) => `<tr class="${i===0?'leader':''}">
      <td class="place">${i+1}</td>
      <td class="l name"><button class="pl" data-id="${r.player_id}">${esc(r.name)}</button><span class="pos">${esc(r.position||'')}</span></td>
      <td class="total">${fmt(r.total)}</td><td class="pm">${fmt(r.per_match)}</td>
      <td>${r.games}</td><td>${z(r.goals)}</td><td>${z(r.assists)}</td><td>${z(r.mvp)}</td>
      <td>${r.yellow?'<span class="card y"></span>'+r.yellow:z(0)}</td>
      <td>${r.red?'<span class="card r"></span>'+r.red:z(0)}</td>
      <td>${r.gk_games?fmt(r.gk_bonus):'<span class="zero">·</span>'}</td></tr>`).join('') +
    '</tbody></table>';
  el.querySelectorAll('.pl').forEach(b => b.onclick = () => openCard(+b.dataset.id));
}
function renderMatches(){
  const ms = D.groups[group].matches;
  const el = document.getElementById('matches');
  if (!ms.length){ el.innerHTML = '<li><span class="d"></span><span>Сыгранных матчей пока нет</span></li>'; return; }
  el.innerHTML = [...ms].reverse().map(m => {
    const line = m.home ? `${esc(D.team)} <span class="sc">${m.scored}:${m.conceded}</span> ${esc(m.opponent)}`
                        : `${esc(m.opponent)} <span class="sc">${m.conceded}:${m.scored}</span> ${esc(D.team)}`;
    const mvp = m.mvp_names.length ? 'Лучший игрок: ' + m.mvp_names.map(esc).join(', ') : 'Лучший игрок не указан';
    return `<li><span class="d">${esc(m.date||'')}</span>
      <a href="https://rfll.ru/match/${m.match_id}">${line}</a>
      <span class="mvp">${mvp}. Ожидалось пропущенных: ${fmt(m.expected)} (${m.expected_basis==='соперник'?'по сопернику':'по лиге'})</span></li>`;
  }).join('');
}
function renderHow(){
  const w = D.weights;
  document.getElementById('how').innerHTML = `<h2>Как считаются баллы</h2>
  <p>Игра ${fmt(w.game)}, гол ${fmt(w.goal)}, голевая передача ${fmt(w.assist)}, лучший игрок матча ${fmt(w.mvp)}, желтая карточка ${fmt(w.yellow)}, красная ${fmt(w.red)}.</p>
  <p>Вратарь дополнительно получает (ожидаемые голы соперника минус пропущенные) × ${fmt(D.gk_factor)}, но не меньше нуля. Ожидаемые голы равны средней результативности соперника в турнире; если соперник сыграл меньше трех матчей, берется среднее по лиге.</p>
  <p>Баллы за матч равны общему баллу, деленному на число игр, и не опускаются ниже нуля.</p>
  <p>Нажмите на фамилию игрока в таблице, чтобы открыть его подробную статистику.</p>`;
}
function draw(){ renderGroups(); renderBoard(); renderMatches(); }
document.querySelectorAll('.sort').forEach(b => b.onclick = () => {
  sortKey = b.dataset.sort;
  document.querySelectorAll('.sort').forEach(x => x.setAttribute('aria-pressed', x===b));
  renderBoard();
});

/* ---------- карточка игрока ---------- */
const MON = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
function mkey(s){ s=(s||'').toLowerCase(); let m=s.match(/(\d{1,2})\s+([а-я]+)/);
  if(m && MON.includes(m[2])) return (MON.indexOf(m[2])+1)*100 + +m[1];
  m=s.match(/(\d{1,2})\.(\d{1,2})/); return m ? +m[2]*100 + +m[1] : 0; }
function sdate(s){ const k=mkey(s); return k ? String(k%100).padStart(2,'0')+'.'+String(Math.floor(k/100)).padStart(2,'0') : ''; }
const chrono = ms => [...ms].sort((a,b) => (mkey(a.date)-mkey(b.date)) || (a.match_id-b.match_id));
function ptsOf(e,m){ const w=D.weights;
  let p = w.game + w.goal*e.g + w.assist*e.a + w.mvp*e.mvp + w.yellow*e.y + w.red*e.r;
  if(e.gk) p += Math.max(0,(m.expected-m.conceded)*D.gk_factor); return p; }
const resOf = m => m.scored>m.conceded ? 'w' : m.scored<m.conceded ? 'l' : 'd';
const RES = {w:'В', d:'Н', l:'П'};
const pct = x => Math.round(x*100) + '%';
function plural(n, a, b, c){ const t=n%10, h=n%100; return (t===1&&h!==11)?a:(t>=2&&t<=4&&(h<12||h>14))?b:c; }
function scoreLine(m){ return `${m.scored}:${m.conceded}`; }  // всегда счет команды первым

function findPlayer(id){
  for(const k of order){ const p=(D.groups[k]||{players:[]}).players.find(x=>x.player_id===id); if(p) return p; }
  return null;
}
function collect(id, grp){
  const g = D.groups[grp], ms = chrono(g.matches), apps = [];
  for(const m of ms){ const e = m.lineup && m.lineup.find(x=>x.id===id);
    if(e) apps.push({m, e, pts: ptsOf(e,m), res: resOf(m)}); }
  return {g, ms, apps};
}
function chartSVG(apps){
  const n = apps.length, bw = 22, gap = 6, H = 120, top = 16;
  const max = Math.max(...apps.map(a=>a.pts), 1);
  const W = Math.max(n*(bw+gap)+gap, 10*(bw+gap));
  const col = {w:'var(--court)', d:'#9FB0BD', l:'#D98F89'};
  let bars = apps.map((a,i) => { const h = Math.max(2, (a.pts/max)*(H-top-4)); const x = gap+i*(bw+gap);
    return `<rect x="${x}" y="${H-h}" width="${bw}" height="${h}" rx="3" fill="${col[a.res]}"><title>${sdate(a.m.date)}, ${esc(a.m.opponent)} ${scoreLine(a.m)}: ${fmt(a.pts)}</title></rect>` +
      (a.e.mvp ? `<circle cx="${x+bw/2}" cy="${H-h-7}" r="4" fill="var(--line)"/>` : ''); }).join('');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Баллы по матчам">${bars}</svg>`;
}
function streaks(apps){ let best=0, cur=0; for(const a of apps){ if(a.e.g+a.e.a>0){ cur++; best=Math.max(best,cur); } else cur=0; } return {best, cur}; }

function openCard(id){
  const p = findPlayer(id); if(!p) return;
  const {g, ms, apps} = collect(id, group);
  const panel = document.getElementById('panel');
  const posLine = [p.position, `турнир: ${g.title}`].filter(Boolean).join(' · ');
  let html = `<div class="ph"><button class="x" id="xclose" aria-label="Закрыть">×</button>
    <h3 id="pname">${esc(p.name)}</h3><div class="sub">${esc(posLine)} · <a href="https://rfll.ru/player/${id}" target="_blank" rel="noopener">профиль на сайте лиги</a></div></div><div class="pb">`;
  if(!apps.length){
    html += `<p class="note">В турнире «${esc(g.title)}» этот игрок пока не играл.</p>
      <button class="linkbtn" id="toall">Показать статистику по всем турнирам</button></div>`;
    panel.innerHTML = html; bindCard(id); return;
  }
  const row = g.players.find(x=>x.player_id===id) || {};
  const byTotal = [...g.players].sort((a,b)=>b.total-a.total), byPm = [...g.players].sort((a,b)=>b.per_match-a.per_match);
  const rankT = byTotal.findIndex(x=>x.player_id===id)+1, rankP = byPm.findIndex(x=>x.player_id===id)+1;
  const G = apps.reduce((s,a)=>s+a.e.g,0), A = apps.reduce((s,a)=>s+a.e.a,0), MV = apps.reduce((s,a)=>s+a.e.mvp,0);
  const Y = apps.reduce((s,a)=>s+a.e.y,0), R = apps.reduce((s,a)=>s+a.e.r,0), n = apps.length;
  const rec = {w:0,d:0,l:0}; apps.forEach(a=>rec[a.res]++);
  const teamRec = {w:0,d:0,l:0}; ms.forEach(m=>teamRec[resOf(m)]++);
  const teamGoals = apps.reduce((s,a)=>s+a.m.scored,0), conc = apps.reduce((s,a)=>s+a.m.conceded,0);
  const best = apps.reduce((b,a)=> a.pts>b.pts ? a : b, apps[0]);
  const st = streaks(apps);
  const last5 = apps.slice(-5);
  html += `<div class="tiles">
    <div class="tile hl"><b>${fmt(row.total ?? 0)}</b><span>общий балл · ${rankT} место</span></div>
    <div class="tile"><b>${fmt(row.per_match ?? 0)}</b><span>за матч · ${rankP} место</span></div>
    <div class="tile"><b>${n}</b><span>${plural(n,'игра','игры','игр')} из ${ms.length}</span></div>
    <div class="tile"><b>${G}+${A}</b><span>голы + передачи</span></div>
    <div class="tile"><b>${G}</b><span>${plural(G,'гол','гола','голов')}</span></div>
    <div class="tile"><b>${A}</b><span>${plural(A,'передача','передачи','передач')}</span></div>
    <div class="tile"><b>${MV}</b><span>лучший игрок матча</span></div>
    <div class="tile"><b>${Y}/${R}</b><span>желтые / красные</span></div></div>`;
  const gkApps = apps.filter(a=>a.e.gk); let gkHtml = '';
  if(gkApps.length){
    const gc = gkApps.reduce((s,a)=>s+a.m.conceded,0), ge = gkApps.reduce((s,a)=>s+a.m.expected,0);
    const bonus = gkApps.reduce((s,a)=>s+Math.max(0,(a.m.expected-a.m.conceded)*D.gk_factor),0);
    gkHtml = `<div class="blk"><h4>В воротах</h4><dl class="kv">
      <dt>Матчей в воротах</dt><dd>${gkApps.length}</dd>
      <dt>Пропущено всего</dt><dd>${gc}</dd>
      <dt>Пропущено за матч</dt><dd>${fmt(gc/gkApps.length)}</dd>
      <dt>Ожидалось за матч</dt><dd>${fmt(ge/gkApps.length)}</dd>
      <dt>Матчей лучше ожидания</dt><dd>${gkApps.filter(a=>a.m.conceded<a.m.expected).length}</dd>
      <dt>Бонус вратаря всего</dt><dd>${fmt(bonus)}</dd></dl></div>`;
  }
  if(gkApps.length*2 >= n) html += gkHtml;
  html += `<div class="blk"><h4>Результативность</h4><dl class="kv">
    <dt>Голов за игру</dt><dd>${fmt(G/n)}</dd>
    <dt>Передач за игру</dt><dd>${fmt(A/n)}</dd>
    <dt>Участие в голах команды (в его матчах)</dt><dd>${teamGoals ? pct((G+A)/teamGoals) : 'нет голов'}</dd>
    <dt>Матчей с голом или передачей</dt><dd>${apps.filter(a=>a.e.g+a.e.a>0).length} из ${n}</dd>
    <dt>Лучшая серия результативных матчей</dt><dd>${st.best}</dd>
    <dt>Текущая серия</dt><dd>${st.cur}</dd></dl></div>`;
  html += `<div class="blk"><h4>Команда с ним на поле</h4><dl class="kv">
    <dt>Победы, ничьи, поражения</dt><dd>${rec.w}, ${rec.d}, ${rec.l}</dd>
    <dt>Процент побед с ним</dt><dd>${pct(rec.w/n)}</dd>
    <dt>Процент побед команды в турнире</dt><dd>${ms.length ? pct(teamRec.w/ms.length) : '0%'}</dd>
    <dt>Забито и пропущено за матч</dt><dd>${fmt(teamGoals/n)} : ${fmt(conc/n)}</dd></dl></div>`;
  if(gkApps.length*2 < n) html += gkHtml;
  html += `<div class="blk"><h4>Лучший матч</h4><dl class="kv">
    <dt>${sdate(best.m.date)}, соперник ${esc(best.m.opponent)}, счет ${scoreLine(best.m)}</dt><dd>${fmt(best.pts)}</dd>
    <dt>Голы и передачи</dt><dd>${best.e.g} и ${best.e.a}</dd></dl></div>`;
  html += `<div class="blk chart"><h4>Баллы по матчам</h4>${chartSVG(apps)}
    <div class="lg"><span><i style="background:var(--court)"></i>победа</span><span><i style="background:#9FB0BD"></i>ничья</span>
    <span><i style="background:#D98F89"></i>поражение</span><span><i style="background:var(--line);border-radius:50%"></i>лучший игрок</span></div>
    <p class="note" style="margin-bottom:0">Последние ${last5.length}: ${last5.map(a=>fmt(a.pts)).join(', ')} (в среднем ${fmt(last5.reduce((s,a)=>s+a.pts,0)/last5.length)} за матч)</p></div>`;
  html += `<div class="blk log"><h4>Все матчи</h4><table><thead><tr><th class="l">Дата</th><th class="l">Соперник</th><th title="Счет: команда : соперник">Счет</th>
    <th>Г</th><th>П</th><th>ЖК</th><th>КК</th><th>ЛИ</th><th>Балл</th></tr></thead><tbody>` +
    [...apps].reverse().map(a => `<tr><td class="l">${sdate(a.m.date)}</td><td class="l">${esc(a.m.opponent)}${a.e.gk?' (вр.)':''}</td>
      <td><span class="res ${a.res}" title="${RES[a.res]}">${scoreLine(a.m)}</span></td>
      <td>${z(a.e.g)}</td><td>${z(a.e.a)}</td><td>${z(a.e.y)}</td><td>${z(a.e.r)}</td>
      <td>${a.e.mvp?'<span class="star">★</span>':''}</td><td><b>${fmt(a.pts)}</b></td></tr>`).join('') +
    `</tbody></table></div></div>`;
  panel.innerHTML = html; bindCard(id);
}
function bindCard(id){
  const sheet = document.getElementById('sheet');
  sheet.hidden = false; document.body.style.overflow = 'hidden';
  history.replaceState(null, '', '#p' + id);
  document.getElementById('xclose').onclick = closeCard;
  const all = document.getElementById('toall');
  if(all) all.onclick = () => { group = 'all'; draw(); openCard(id); };
  document.getElementById('xclose').focus();
}
function closeCard(){
  document.getElementById('sheet').hidden = true; document.body.style.overflow = '';
  history.replaceState(null, '', location.pathname + location.search);
}
document.getElementById('sheet').addEventListener('click', e => { if(e.target.id === 'sheet') closeCard(); });
document.addEventListener('keydown', e => { if(e.key === 'Escape' && !document.getElementById('sheet').hidden) closeCard(); });
renderHow(); draw();
{ const m = location.hash.match(/^#p(\d+)$/); if(m) openCard(+m[1]); }
</script>
</body>
</html>
"""


def render(data):
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("__TITLE__", html.escape(data["title"]))
                    .replace("__TEAM__", html.escape(data["team"]))
                    .replace("__UPDATED__", html.escape(data["updated"]))
                    .replace("__DATA__", payload))
