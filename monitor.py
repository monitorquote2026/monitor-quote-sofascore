import csv, json, os, pathlib, datetime, html
ROOT=pathlib.Path(__file__).parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
HISTORY=DATA/'events.json'; INPUT=DATA/'authorized_feed.csv'
now=datetime.datetime.now(datetime.timezone.utc)
rows=json.loads(HISTORY.read_text(encoding='utf8')) if HISTORY.exists() else {}
# The feed must be populated only from a licensed/authorized source.
if INPUT.exists():
    with INPUT.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            key=(r.get('event_id') or '').strip()
            if not key: continue
            try: initial=float(r['initial_odds']); current=float(r['current_odds'])
            except (ValueError,KeyError): continue
            if initial<=0 or current<=0: continue
            drop=round((initial-current)/initial*100,2)
            start=(r.get('start_utc') or '').strip()
            try: kickoff=datetime.datetime.fromisoformat(start.replace('Z','+00:00'))
            except ValueError: continue
            if kickoff.tzinfo is None: kickoff=kickoff.replace(tzinfo=datetime.timezone.utc)
            cutoff=kickoff-datetime.timedelta(minutes=5)
            item=rows.setdefault(key, {'event_id':key,'sport':r.get('sport',''), 'event':r.get('event',''), 'start_utc':start,'initial_odds':initial,'max_drop':0,'observations':[],'final_score':''})
            if now<=cutoff:
                item['observations'].append({'at_utc':now.isoformat(),'odds':current,'drop_pct':drop})
                item['max_drop']=max(item['max_drop'],drop)
            if (r.get('status') or '').lower() in ('finished','final'):
                item['final_score']=r.get('final_score','')
HISTORY.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
shown=sorted((v for v in rows.values() if v['max_drop']>=30),key=lambda v:v['start_utc'],reverse=True)
trs=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [v['sport'],v['event'],v['start_utc'],v['initial_odds'],str(v['max_drop'])+'%',v['final_score'] or 'In attesa'])+'</tr>' for v in shown)
page='''<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Monitor quote</title><style>body{font:16px system-ui;background:#111827;color:#f9fafb;margin:2rem}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #374151;text-align:left;padding:.7rem}th{color:#93c5fd}.note{color:#d1d5db}</style><h1>Monitor quote · cali ≥30%</h1><p class="note">Fonte autorizzata necessaria. Nessun dato SofaScore viene estratto da questa versione.</p><div style="overflow:auto"><table><thead><tr><th>Sport</th><th>Evento</th><th>Inizio UTC</th><th>Quota iniziale</th><th>Max calo</th><th>Risultato</th></tr></thead><tbody>'''+trs+'''</tbody></table></div><p class="note">Ultimo aggiornamento: '''+now.isoformat()+'''</p></html>'''
(ROOT/'index.html').write_text(page,encoding='utf8')
print(f'Eventi in archivio: {len(rows)}, mostrati: {len(shown)}')
