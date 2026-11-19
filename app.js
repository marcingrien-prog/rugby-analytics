(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const titles = {dashboard:'Nadchodzące mecze',predictor:'Prognozator',teams:'Drużyny',worldcup:'Rugby World Cup',methodology:'Metodologia'};
  let liveData = null;
  let currentFilter = 'all';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function showView(name) {
    if (!titles[name]) return;
    document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.id === 'view-' + name));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === name));
    if ($('page-title')) $('page-title').textContent = titles[name];
    window.scrollTo(0, 0);
  }
  function formatDate(match) {
    const value = match.kickoff_utc || match.date;
    if (!value) return 'Termin nieustalony';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return esc(match.date);
    return new Intl.DateTimeFormat('pl-PL',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',hour:match.kickoff_utc?'2-digit':undefined,minute:match.kickoff_utc?'2-digit':undefined,timeZone:'Europe/Warsaw'}).format(date);
  }
  const fixtures = () => Array.isArray(liveData?.fixtures) ? liveData.fixtures : [];
  function updateMetrics() {
    const f=fixtures(), predicted=f.filter(x=>x.prediction).length;
    if($('metric-fixtures')) $('metric-fixtures').textContent=f.length;
    if($('metric-predictions')) $('metric-predictions').textContent=predicted;
    if($('metric-competitions')) $('metric-competitions').textContent=liveData?.competitions_count ?? '—';
    if($('metric-standings')) $('metric-standings').textContent=liveData?.standings_loaded ?? '—';
  }
  function renderFixtures() {
    const list=$('fixtures-list'), status=$('fixtures-status');
    if(!list||!status)return;
    if(!liveData){status.innerHTML='<b>Nie udało się pobrać terminarza.</b><p>Spróbuj ponownie za chwilę.</p>';list.innerHTML='';return;}
    const all=fixtures();
    status.innerHTML='<b>Źródło: rugbyAPI · '+all.length+' spotkań</b><p>Zakres: najbliższe '+esc(liveData.window_days||60)+' dni. Aktualizacja paczki: '+esc(new Date(liveData.generated_at).toLocaleString('pl-PL'))+'. Automatyczne odświeżanie dwa razy dziennie.</p>';
    const visible=currentFilter==='all'?all:all.filter(x=>(x.competition||'')===currentFilter);
    if(!visible.length){list.innerHTML='<div class="panel empty-state"><h3>Brak spotkań</h3><p>Nie znaleziono meczów dla wybranego filtra.</p></div>';return;}
    list.innerHTML=visible.map(m=>{
      const p=m.prediction;
      const analysis=p?'<div class="fixture-prob"><div><b>'+p.home_win+'%</b><span>Wygrana gospodarzy</span></div><div><b>'+p.draw+'%</b><span>Remis</span></div><div><b>'+p.away_win+'%</b><span>Wygrana gości</span></div></div><p class="fixture-basis">Podstawa: '+esc(m.prediction_basis||'dane bieżące')+(p.home_score!==null&&p.away_score!==null?' · wynik orientacyjny: '+p.home_score+'–'+p.away_score:'')+'</p>':'<p class="fixture-basis no-prediction">Brak wystarczających danych dla obu drużyn – prognoza nie jest wyliczana.</p>';
      return '<article class="fixture-card"><div class="fixture-meta"><span>'+esc(m.competition)+'</span><time>'+formatDate(m)+'</time></div><div class="fixture-teams"><div><small>GOSPODARZE</small><strong>'+esc(m.home?.name)+'</strong></div><span class="fixture-vs">VS</span><div class="away"><small>GOŚCIE</small><strong>'+esc(m.away?.name)+'</strong></div></div>'+analysis+'</article>';
    }).join('');
  }
  function populatePredictor() {
    const home=$('home'),away=$('away');
    if(!home||!away)return;
    const names=[...new Set(fixtures().flatMap(m=>[m.home?.name,m.away?.name]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pl'));
    const opts=names.map(n=>'<option value="'+esc(n)+'">'+esc(n)+'</option>').join('');
    home.innerHTML='<option value="">Wybierz drużynę</option>'+opts;
    away.innerHTML='<option value="">Wybierz drużynę</option>'+opts;
    if(names.length>1)away.value=names[1];
  }
  function runPrediction() {
    const h=$('home')?.value,a=$('away')?.value,result=$('prediction-result');
    if(!result)return;
    if(!h||!a||h===a){result.innerHTML='<div class="empty-state"><h3>Wybierz dwie różne drużyny</h3><p>Wskaż gospodarza i gościa.</p></div>';return;}
    const m=fixtures().find(x=>x.home?.name===h&&x.away?.name===a);
    if(!m){result.innerHTML='<div class="empty-state"><h3>Brak takiego meczu w terminarzu</h3><p>Prognozator analizuje pary gospodarze–goście dostępne w aktualnym terminarzu.</p></div>';return;}
    const p=m.prediction;
    if(!p){result.innerHTML='<div class="empty-state"><h3>Brak wystarczających danych</h3><p>'+esc(h)+' – '+esc(a)+': nie ma aktualnych danych tabelarycznych lub rankingowych dla obu drużyn. Nie generujemy fikcyjnych procentów.</p></div>';return;}
    result.innerHTML='<div class="result-head"><h3>'+esc(h)+' – '+esc(a)+'</h3><span class="pill">'+esc(m.competition)+'</span></div><p class="fine">'+formatDate(m)+' · Podstawa: '+esc(m.prediction_basis)+'</p><div class="win-grid"><div class="win-box"><b>'+p.home_win+'%</b><span>Wygrana gospodarzy</span></div><div class="win-box"><b>'+p.draw+'%</b><span>Remis</span></div><div class="win-box"><b>'+p.away_win+'%</b><span>Wygrana gości</span></div></div><div class="scoreline"><strong>'+(p.home_score??'—')+' : '+(p.away_score??'—')+'</strong><span>orientacyjny wynik</span></div><div class="notice"><b>Poziom prognozy: '+esc(p.confidence||'wstępna')+'</b><p>Wynik jest szacunkiem modelu opartego na danych bieżącego sezonu, a nie prognozą zweryfikowaną historycznym backtestingiem.</p></div>';
  }
  function renderTeams() {
    const table=$('teams-table');if(!table)return;
    const map=new Map();
    fixtures().forEach(m=>[m.home,m.away].forEach(t=>{if(!t?.id)return;const v=map.get(t.id)||{name:t.name,matches:0,comps:new Set(),predicted:0};v.matches++;v.comps.add(m.competition);if(m.prediction)v.predicted++;map.set(t.id,v);}));
    table.innerHTML=[...map.values()].sort((a,b)=>a.name.localeCompare(b.name,'pl')).map(t=>'<tr><td>'+esc(t.name)+'</td><td>'+t.matches+'</td><td>'+esc([...t.comps].join(', '))+'</td><td><span class="tag">'+(t.predicted?'część meczów z prognozą':'brak prognozy')+'</span></td></tr>').join('');
  }
  function renderAll(){updateMetrics();renderFixtures();populatePredictor();renderTeams();const box=$('competition-filter');if(box){const selected=box.value;const comps=[...new Set(fixtures().map(x=>x.competition).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pl'));box.innerHTML='<option value="all">Wszystkie dostępne</option>'+comps.map(c=>'<option value="'+esc(c)+'">'+esc(c)+'</option>').join('');box.value=comps.includes(selected)?selected:'all';currentFilter=box.value;renderFixtures();}}
  async function loadFixtures() {
    const status=$('fixtures-status');if(status)status.innerHTML='<b>Aktualizuję widok…</b><p>Wczytuję ostatnią paczkę danych.</p>';
    try{const response=await fetch('./data/live-data.json?v='+Date.now(),{cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);liveData=await response.json();renderAll();}
    catch(e){liveData=null;renderFixtures();console.error('Rugby Analytics data load failed:',e);}
  }
  function init(){
    document.addEventListener('click',e=>{
      const nav=e.target.closest('[data-view]'),go=e.target.closest('[data-go]');
      if(nav)showView(nav.dataset.view);else if(go)showView(go.dataset.go);
      if(e.target.closest('#refresh-fixtures'))loadFixtures();
      if(e.target.closest('#run-prediction'))runPrediction();
    });
    $('home')?.addEventListener('change',runPrediction);
    $('away')?.addEventListener('change',runPrediction);
    fillCompetitionFilter();
    loadFixtures();
  }
  function fillCompetitionFilter(){
    const box=$('competition-filter');if(!box)return;
    box.addEventListener('change',()=>{currentFilter=box.value;renderFixtures();});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
  window.RugbyAnalytics={version:'0.4.0',dataMode:'live-static-feed'};
})();