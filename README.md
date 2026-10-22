# Monitor Quote gratuito — GitHub Actions

**Stato:** pronto per l'esecuzione schedulata, ma **non collegato a SofaScore**. Non vengono inventate quote. Serve una fonte dati autorizzata che aggiorni `data/authorized_feed.csv` secondo l'intestazione fornita. L'inserimento manuale del CSV non è monitoraggio automatico della fonte.

## Installazione
1. Crea un account gratuito su github.com e un repository nuovo (per la pubblicazione con Pages, pubblico se richiesto dal tuo piano).
2. Carica **il contenuto** di questa cartella nella radice del repository, compresa `.github/workflows/monitor.yml` (la cartella `.github` è nascosta in alcuni programmi).
3. Vai in **Settings → Actions → General → Workflow permissions** e abilita **Read and write permissions**. Se il repository ha regole che bloccano push su main, configura le eccezioni o un ramo dedicato.
4. Vai in **Actions → Monitor quote → Run workflow** per la prima esecuzione. Il file `index.html` verrà generato.
5. In **Settings → Pages**, scegli **Deploy from a branch**, `main`, `/ (root)`, poi salva. Il sito sarà disponibile all'URL indicato da GitHub.
6. Le esecuzioni programmate GitHub Actions sono **best effort**, possono essere ritardate o saltate; repository pubblici inattivi possono avere la schedulazione disabilitata. Non è un servizio garantito ogni 5 minuti.

## Dati e regole
- `data/authorized_feed.csv`: `event_id,sport,event,start_utc,initial_odds,current_odds,status,final_score`.
- `start_utc` in ISO 8601 UTC, es. `2026-10-22T19:00:00Z`; `status=finished` quando terminata.
- Il calo è `(quota iniziale - quota attuale) / quota iniziale × 100`. Le quote devono riferirsi **allo stesso mercato e selezione**; il CSV dimostrativo non ha campi mercato/selezione e quindi va esteso prima dell'uso reale.
- Registra osservazioni fino a 5 minuti prima dell'inizio; registra il risultato anche dopo. Mostra eventi con calo massimo >=30%.
- Il CSV qui è un **formato di integrazione**, non un'acquisizione automatica. Per automatizzare servono credenziali e un connettore verso un provider autorizzato. Non usare endpoint interni SofaScore senza permesso.
- `data/events.json` cresce nel tempo e viene salvato tramite commit: non è una soluzione adatta a grandi volumi. Per tutti gli sport in produzione serve un database persistente.
- Il sito Pages è pubblico se configurato su repository pubblico: non inserirvi segreti.

## Costi
GitHub Actions e Pages possono rientrare nei limiti gratuiti del piano e tipo di repository. Fonte dati autorizzata non inclusa; il costo totale zero non è garantito.
