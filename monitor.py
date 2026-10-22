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

    HISTORY.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
    matches = sorted((e for e in events.values() if e.get('max_drop', 0) >= 30),
                     key=lambda e: e.get('start_utc', ''), reverse=True)
    rows = []
    for e in matches[:500]:
        cells = [e.get('sport', ''), e.get('event', ''), e.get('bookmaker', ''),
                 e.get('selection', ''), e.get('initial_odds', ''), e.get('min_odds', ''),
                 f"{e.get('max_drop', 0):.2f}%", e.get('start_utc', ''),
                 e.get('final_score', '')]
        rows.append('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>' for v in cells) + '</tr>')
    doc = '''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Monitor Quote</title><style>body{font:16px system-ui,sans-serif;margin:30px;background:#f8fafc;color:#111827}table{border-collapse:collapse;width:100%;background:white}th,td{padding:10px;border:1px solid #e5e7eb;text-align:left}th{background:#e2e8f0}.wrap{overflow-x:auto}</style></head><body><h1>Monitor Quote</h1><p>Quote con calo rilevato almeno del 30%. Fonte: The Odds API. Quote iniziale = prima osservazione registrata, non necessariamente quota di apertura.</p><p>Ultimo aggiornamento: ''' + html.escape(now.isoformat()) + ''' UTC · Selezioni monitorate: ''' + str(len(events)) + ''' · Calo ≥30%: ''' + str(len(matches)) + '''</p><div class="wrap"><table><thead><tr><th>Sport</th><th>Evento</th><th>Bookmaker</th><th>Esito</th><th>Prima quota</th><th>Minima</th><th>Max calo</th><th>Inizio (UTC)</th><th>Risultato</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div><p>Risultati finali non ancora integrati. Aggiornamenti programmati soggetti ai limiti di GitHub Actions e dei crediti API.</p></body></html>'''
    (ROOT / 'index.html').write_text(doc, encoding='utf-8')


if __name__ == '__main__':
    main()
