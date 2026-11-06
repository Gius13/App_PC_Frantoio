# App PC Frantoio — evoluzione interfaccia e modifica record

Queste modifiche sono nel branch \`feature/modern-ui-record-editing\`, **non** nel branch di produzione \`main\`.

## Funzionalità aggiunte

- Tema Qt chiaro e moderno (tabelle, controlli, scheda e finestre).
- Ricerca immediata nella lista del giorno e ordinamento della tabella.
- Finestra dedicata **Modifica record** (pulsante o doppio clic) con:
  nome cliente, peso, abbuono, pagamento, data e ora.
- Validazione dei valori e aggiornamento dei soli campi effettivamente cambiati.
- Scrittura Firebase con PATCH parziale; scrittura SQLite in transazione.
- Le modifiche fatte direttamente su record d'archivio SQLite vengono protette
  dalle successive operazioni di mirroring; le cancellazioni locali sono protette
  da una tabella di tombstone.
- Modifica rapida pagamento e cancellazione eseguite in thread, per evitare blocchi UI.
- Test di regressione per validazione e persistenza SQLite.

## Esecuzione e verifica

Usare una **copia dei dati**, non il database operativo, per il collaudo.
Installare nell'ambiente Python le dipendenze già utilizzate dall'app:
\`PyQt6\`, \`requests\`, \`pandas\`, \`openpyxl\`.
Avviare dalla directory padre della cartella \`app_frantoio\`:

\`\`\`bash
python -m unittest discover -s app_frantoio/tests -v
python -m app_frantoio.app
\`\`\`

Il progetto non contiene ancora un file di dipendenze bloccate; l'installazione
dell'ambiente e il funzionamento dell'interfaccia vanno verificati sul PC target.

## Note di sicurezza e sincronizzazione

- Fare prima il backup di \`frantoio_archive.db\` e della configurazione locale.
- I record recenti provengono da Firebase; i record meno recenti sono aperti da SQLite.
- Se un record storico viene modificato **solo in SQLite**, la modifica viene
  protetta localmente ma non viene inviata a Firebase. Questo comportamento
  evita correzioni impreviste sui dati online; va valutato prima dell'uso multi-PC.
- La protezione per record dei local override è conservativa: un record modificato
  localmente non verrà più sovrascritto dal mirror fino a una futura procedura
  di riconciliazione.
- Per record recenti, un PATCH riuscito su Firebase potrebbe non essere immediatamente
  riflesso in SQLite se il record non è ancora stato copiato dal mirror.
- Non è stata implementata una gestione dei conflitti multiutente o un registro
  storico delle modifiche. Sono evoluzioni da fare prima di considerare completo
  il rilascio in produzione.

## Prossimi miglioramenti proposti

1. Test end-to-end con database di prova e integrazione Firebase.
2. Registro modifiche e risoluzione dei conflitti tra dispositivi.
3. Report con KPI, filtri data, grafici e ricerca globale d'archivio.
4. Backup guidato, ripristino controllato e verifica database.
5. Ottimizzazione delle letture Firebase e gestione della scadenza dei token.


## Correzioni calendario e aggiornamento lista (6 novembre 2026)

- Il calendario ha un proprio stile, separato da quello della tabella delle moliture.
  Impostati lunedì come primo giorno, dimensione minima del popup, colori
  delle celle e del giorno selezionato.
- La scelta della data non disabilita più immediatamente il selettore durante
  la chiusura del popup.
- Il modello Qt aggiorna solo righe inserite, rimosse o cambiate: se la risposta
  del polling è identica, non emette nemmeno un reset.
- La riga selezionata resta selezionata per ID, senza `scrollTo`, e non
  si forza più lo scorrimento al centro a ogni aggiornamento.
- La posizione delle scrollbar viene rilevata al momento in cui arrivano
  i nuovi dati, non all'avvio della richiesta, così uno scroll effettuato
  durante il polling non viene sovrascritto.
- Il proxy ordina di default per `dataOra` numerico crescente (colonna "Ora"),
  ma consente ancora il riordino manuale delle altre colonne.
- Una richiesta per una data ormai cambiata viene scartata e ripetuta per
  la nuova data, evitando la comparsa temporanea di record del giorno precedente.

### Prova su macOS

```bash
cd ~/Frantoio-Test/app_frantoio
git pull --ff-only origin feature/modern-ui-record-editing
cd ..
source .venv/bin/activate
python -m unittest discover -s app_frantoio/tests -v
python -m app_frantoio.app
```

Per il collaudo manuale: selezionare una riga in fondo, scorrere, aspettare
due o tre cicli di aggiornamento, inserire un nuovo record da un'altra postazione
e verificare che selezione, focus e posizione restino invariati.
Provare anche i calendari di Lista, Report e Modifica record.

Il test automatizzato dell'interfaccia usa il plugin Qt `offscreen`: non
sostituisce la verifica visiva su macOS.


## Temi chiaro e scuro (nero, antracite e rosso)

- L'app supporta due palette coordinate: **Chiaro** (fondo grigio chiarissimo,
  pannelli bianchi, testi quasi neri e rosso carminio) e **Scuro** (fondo quasi
  nero, pannelli antracite, testo bianco e rosso più luminoso).
- Il selettore **Aspetto: Chiaro / Scuro** si trova in alto a destra nella
  barra principale ed è accessibile anche mentre si visualizzano i Report.
- Il cambio avviene subito, senza riavvio, su tutta l'applicazione.
- La preferenza viene salvata nel campo \`theme\` del file
  \`config.json\` dell'utente; al successivo avvio viene recuperata e
  applicata prima del login.
- Anche calendari e dialog di modifica vengono aggiornati, e le tabelle
  rispettano il contrasto del tema selezionato.
- I pulsanti principali e la barra superiore hanno sfumature rosse, non blu.
- La preferenza iniziale per installazioni esistenti è \`light\`, in modo da
  non alterare inaspettatamente l'aspetto dell'applicazione.

### Aggiornamento sul Mac

\`\`\`bash
cd ~/Frantoio-Test/app_frantoio
git pull --ff-only origin feature/modern-ui-record-editing
cd ..
source .venv/bin/activate
python -m unittest discover -s app_frantoio/tests -v
python -m app_frantoio.app
\`\`\`

Per verificare: alternare tra Chiaro e Scuro mentre si osservano la lista
moliture, i report, i calendari e la finestra di modifica; chiudere e riaprire
l'app e confermare che il tema selezionato venga mantenuto.


## Nuova ricerca e interfaccia (6 novembre 2026)

### Design

- Riquadro di ricerca più ordinato, pulsanti compatti e spaziatura maggiore.
- Combo box non native in stile Fusion, con angoli arrotondati e menu
  di selezione coerenti nel tema scuro e nel tema chiaro.
- Colori nero, antracite, grigi neutri e rosso come accento.
- Calendario con **disegno diretto delle celle** (invece della sola
  formattazione Qt): giorno selezionato rosso, oggi evidenziato,
  altre date meno marcate, settimana da lunedì e mesi in italiano.

### Ricerca per più giorni

1. In **Moliture**, scegli **Periodo → Più giorni**.
2. Seleziona **Dal** e **Al** nei nuovi calendari.
3. Premi **Cerca nel periodo** per caricare il periodo.
4. Scrivi un nome o altro testo, scegli il metodo di pagamento e,
   facoltativamente, imposta il peso minimo e massimo. Questi filtri
   agiscono immediatamente sui record già caricati.
5. **Esporta Excel** esporta solo i record filtrati, con data e ora complete.
6. **Azzera filtri** riporta alla vista giornaliera odierna.

Intervallo supportato: massimo **367 giorni inclusivi**. Il caricamento
periodico ogni 3 secondi rimane attivo in modalità **Un giorno**; per periodi
ampi, la ricerca avviene invece su richiesta (pulsante Cerca/Aggiorna) per
non sovraccaricare l'archivio.

La ricerca combina una singola query SQLite indicizzata per le date
storiche e una sola lettura Firebase per la finestra dei record recenti,
mantenendo le rispettive sorgenti per la modifica dei record.

### Collaudo Mac

\`\`\`bash
cd ~/Frantoio-Test/app_frantoio
git pull --ff-only origin feature/modern-ui-record-editing
cd ..
source .venv/bin/activate
python -m unittest discover -s app_frantoio/tests -v
python -m app_frantoio.app
\`\`\`

Verificare in particolare: navigazione del calendario col mouse e da tastiera,
scelta di un intervallo che attraversa il cambio di mese, filtri combinati,
export e ritorno alla modalità giornaliera. Le fonti dati operative non sono
modificate dalla sola ricerca; testare i salvataggi con dati di prova.


## Selettore data sempre visibile

Il calendario **Giorno** è nella barra della lista moliture, accanto ai
pulsanti **Ricerca e filtri**, **Aggiorna** ed **Esporta Excel**.

- Il pannello dei filtri avanzati rimane chiuso per impostazione predefinita.
- Il calendario del giorno è visibile e utilizzabile anche a filtri chiusi.
- La selezione del giorno cambia immediatamente la giornata mostrata.
- Se è attiva una ricerca per **Più giorni**, selezionare una nuova data
  dal calendario superiore riporta alla vista **Un giorno**.
- I campi per selezionare **Dal / Al**, pagamento e intervallo di peso
  restano nel pannello espandibile.
- Il calendario non viene disabilitato durante i caricamenti manuali;
  un cambio data durante il fetch viene elaborato al suo termine.

**Test manuale:** tenere i filtri chiusi, cambiare data dalla barra superiore,
verificare i record; riaprire i filtri, impostare Più giorni, richiudere e
scegliere una nuova data dalla barra.
