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
