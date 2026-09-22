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
th:nth-child(4),td.pm{padding-right:22px;border-right:1px solid #EEF1F3}
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
      <td class="l name"><span class="nm">${esc(r.name)}</span><span class="pos">${esc(r.position||'')}</span></td>
      <td class="total">${fmt(r.total)}</td><td class="pm">${fmt(r.per_match)}</td>
      <td>${r.games}</td><td>${z(r.goals)}</td><td>${z(r.assists)}</td><td>${z(r.mvp)}</td>
      <td>${r.yellow?'<span class="card y"></span>'+r.yellow:z(0)}</td>
      <td>${r.red?'<span class="card r"></span>'+r.red:z(0)}</td>
      <td>${r.gk_games?fmt(r.gk_bonus):'<span class="zero">·</span>'}</td></tr>`).join('') +
    '</tbody></table>';
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
  <p>Баллы за матч равны общему баллу, деленному на число игр, и не опускаются ниже нуля.</p>`;
}
function draw(){ renderGroups(); renderBoard(); renderMatches(); }
document.querySelectorAll('.sort').forEach(b => b.onclick = () => {
  sortKey = b.dataset.sort;
  document.querySelectorAll('.sort').forEach(x => x.setAttribute('aria-pressed', x===b));
  renderBoard();
});
renderHow(); draw();
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
