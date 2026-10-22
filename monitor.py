import csv
import datetime as dt
import html
import json
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
HISTORY = DATA / 'events.json'
KEY = os.getenv('ODDS_API_KEY', '').strip()
SPORT = os.getenv('ODDS_SPORT', 'soccer_italy_serie_a')
REGIONS = os.getenv('ODDS_REGIONS', 'eu')
MARKETS = 'h2h'


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def fetch(path, params):
    url = 'https://api.the-odds-api.com/v4/' + path + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent': 'PersonalOddsMonitor/1.0'})
    with urllib.request.urlopen(request, timeout=25) as response:
        body = json.load(response)
        remaining = response.headers.get('x-requests-remaining', 'unknown')
        used = response.headers.get('x-requests-used', 'unknown')
        print(f'API credits: used={used}; remaining={remaining}')
        return body


def load():
    if HISTORY.exists():
        try:
            obj = json.loads(HISTORY.read_text(encoding='utf-8'))
            return obj if isinstance(obj, dict) else {}
        except (ValueError, OSError):
            pass
    return {}


def main():
    events = load()
    now = utcnow()
    if KEY:
        try:
            games = fetch(f'sports/{urllib.parse.quote(SPORT, safe="")}/odds/', {
                'apiKey': KEY, 'regions': REGIONS, 'markets': MARKETS, 'oddsFormat': 'decimal'
            })
            for game in games:
                start = dt.datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                if now > start - dt.timedelta(minutes=5):
                    continue
                for book in game.get('bookmakers', []):
                    for market in book.get('markets', []):
                        if market.get('key') != 'h2h':
                            continue
                        for outcome in market.get('outcomes', []):
                            price = outcome.get('price')
                            if not isinstance(price, (int, float)) or price <= 1:
                                continue
                            event_id = '|'.join([game['id'], book['key'], outcome['name']])
                            record = events.setdefault(event_id, {
                                'event_id': game['id'], 'sport': SPORT,
                                'event': f"{game.get('home_team', '')} - {game.get('away_team', '')}",
                                'bookmaker': book['title'], 'selection': outcome['name'],
                                'start_utc': game['commence_time'], 'initial_odds': price,
                                'min_odds': price, 'max_drop': 0, 'observations': [],
                                'status': 'scheduled', 'final_score': ''
                            })
                            record['min_odds'] = min(record['min_odds'], price)
                            drop = round((record['initial_odds'] - price) / record['initial_odds'] * 100, 2)
                            record['max_drop'] = max(record['max_drop'], drop)
                            record['observations'].append({'at': now.isoformat(), 'odds': price, 'drop': drop})
            print(f'Fetched {len(games)} games; tracked {len(events)} bookmaker selections')
        except Exception as exc:
            print(f'API fetch failed: {type(exc).__name__}: {exc}')
            raise
    else:
        print('ODDS_API_KEY missing: no API request made')

    # Manteniamo lo storico completo; la dashboard visualizza solo i cali.
    HISTORY.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')

    selections = []
    for e in events.values():
        observations = e.get('observations') or []
        if not observations:
            continue
        first = e.get('initial_odds')
        latest = observations[-1].get('odds')
        if not isinstance(first, (int, float)) or first <= 0:
            continue
        if not isinstance(latest, (int, float)) or latest <= 0:
            continue
        current_drop = round((first - latest) / first * 100, 2)
        if current_drop <= 0:
            continue
        item = {
            'sport': e.get('sport', ''),
            'event': e.get('event', ''),
            'bookmaker': e.get('bookmaker', ''),
            'selection': e.get('selection', ''),
            'initial': first,
            'current': latest,
            'drop': current_drop,
            'max_drop': e.get('max_drop', 0),
            'last_seen': observations[-1].get('at', ''),
            'start': e.get('start_utc', ''),
        }
        selections.append(item)

    selections.sort(key=lambda item: item['drop'], reverse=True)
    # Inseriamo i dati JSON in modo sicuro, evitando l'iniezione di tag HTML.
    payload = json.dumps(selections, ensure_ascii=False).replace('<', r'\\u003c')
    summary = {
        'tracked': len(events),
        'descending': len(selections),
        'significant': sum(e['drop'] >= 30 for e in selections),
        'updated': now.isoformat(),
    }
    summary_json = json.dumps(summary, ensure_ascii=False).replace('<', r'\\u003c')

    page = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor Quote | Quote in discesa</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#172033;background:#f4f7fb}
*{box-sizing:border-box}body{margin:0}.container{max-width:1250px;margin:auto;padding:26px 18px 60px}
h1{margin:0 0 6px;font-size:clamp(25px,4vw,36px)}h2{font-size:20px;margin:0}
.muted{color:#64748b}.sub{margin:0 0 24px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}
.card,.panel{background:white;border:1px solid #e1e7ef;border-radius:14px;padding:18px}
.card .num{font-size:29px;font-weight:750;margin-top:6px}.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:18px 0}
label{display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:650}
select,input{border:1px solid #cbd5e1;border-radius:8px;padding:10px;font:inherit;background:white;min-width:145px}
input{min-width:210px}button{border:0;border-radius:8px;padding:11px 14px;background:#1e40af;color:white;cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid #edf1f6}
th{color:#475569;font-size:12px;background:#f8fafc;white-space:nowrap}
.scroll{overflow-x:auto}.drop{font-weight:750;color:#b45309}.big{color:#b91c1c}
.small{font-size:12px}.empty{padding:32px;text-align:center;color:#64748b}
footer{margin-top:18px;font-size:13px;color:#64748b}
@media(max-width:650px){.cards{grid-template-columns:1fr}.card{padding:13px}.container{padding:16px 10px}}
</style></head><body><main class="container">
<h1>📉 Monitor Quote</h1>
<p class="sub muted">Solo quote attualmente in discesa · Fonte: The Odds API · Prima quota = prima rilevazione, non quota di apertura.</p>
<section class="cards">
<div class="card"><div class="muted">Selezioni monitorate</div><div class="num" id="tracked">—</div></div>
<div class="card"><div class="muted">Quote attualmente in discesa</div><div class="num" id="descending">—</div></div>
<div class="card"><div class="muted">Cali attuali ≥30%</div><div class="num" id="significant">—</div></div>
</section>
<section class="panel">
<h2>Quote in discesa</h2>
<div class="toolbar">
<label>Calo minimo
<select id="threshold"><option value="1">1%</option><option value="5" selected>5%</option><option value="10">10%</option><option value="30">30%</option></select></label>
<label>Bookmaker<select id="bookmaker"><option value="">Tutti</option></select></label>
<label>Cerca partita o esito<input id="search" placeholder="Es. Inter, Napoli..."></label>
<button id="reset" type="button">Azzera filtri</button>
</div>
<p class="muted small" id="count"></p>
<div class="scroll"><table><thead><tr><th>Evento / sport</th><th>Esito</th><th>Bookmaker</th><th>Prima quota → attuale</th><th>Calo attuale</th><th>Calo massimo</th><th>Ultima rilevazione (UTC)</th></tr></thead>
<tbody id="rows"></tbody></table></div>
<p class="empty" id="empty" hidden>Nessuna quota in discesa corrisponde ai filtri selezionati.</p>
</section>
<footer><span id="updated"></span><p>Il calo attuale è calcolato rispetto alla prima quota osservata presso lo stesso bookmaker. Il calo massimo è storico e può non essere più disponibile. Gli eventi passati restano nello storico; non sono necessariamente quote giocabili. I risultati finali non sono ancora integrati. Gli aggiornamenti dipendono da GitHub Actions e dai crediti API.</p></footer>
</main>
<script id="odds-data" type="application/json">__ODDS_JSON__</script>
<script id="summary-data" type="application/json">__SUMMARY_JSON__</script>
<script>
const odds=JSON.parse(document.getElementById('odds-data').textContent);
const summary=JSON.parse(document.getElementById('summary-data').textContent);
const $=id=>document.getElementById(id);
$('tracked').textContent=summary.tracked.toLocaleString('it-IT');
$('descending').textContent=summary.descending.toLocaleString('it-IT');
$('significant').textContent=summary.significant.toLocaleString('it-IT');
$('updated').textContent='Ultimo aggiornamento: '+summary.updated+' (UTC)';
const bookmakers=[...new Set(odds.map(x=>x.bookmaker))].sort();
for(const b of bookmakers){const o=document.createElement('option');o.value=b;o.textContent=b;$('bookmaker').append(o)}
function cell(tr,text,className){const td=document.createElement('td');td.textContent=text;if(className)td.className=className;tr.append(td)}
function render(){
 const min=Number($('threshold').value),book=$('bookmaker').value,q=$('search').value.trim().toLowerCase();
 const selected=odds.filter(x=>x.drop>=min&&(!book||x.bookmaker===book)&&(!q||(x.event+' '+x.selection+' '+x.sport).toLowerCase().includes(q)));
 const body=$('rows');body.replaceChildren();
 for(const x of selected.slice(0,500)){
   const tr=document.createElement('tr');
   cell(tr,x.event+' · '+x.sport);cell(tr,x.selection);cell(tr,x.bookmaker);
   cell(tr,x.initial.toFixed(2)+' → '+x.current.toFixed(2));
   cell(tr,'−'+x.drop.toFixed(2)+'%',x.drop>=30?'drop big':'drop');
   cell(tr,'−'+Number(x.max_drop).toFixed(2)+'%');
   cell(tr,x.last_seen);
   body.append(tr);
 }
 $('count').textContent=selected.length+' selezioni trovate'+(selected.length>500?' (prime 500 visualizzate)':'');
 $('empty').hidden=selected.length!==0;
}
for(const id of ['threshold','bookmaker','search'])$(id).addEventListener(id==='search'?'input':'change',render);
$('reset').addEventListener('click',()=>{$('threshold').value='5';$('bookmaker').value='';$('search').value='';render()});
render();
</script></body></html>"""
    page = page.replace('__ODDS_JSON__', payload).replace('__SUMMARY_JSON__', summary_json)
    (ROOT / 'index.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
