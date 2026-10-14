# Moonshot Radar

Automatischer Forschungs-Eingang für Originalmeldungen und Marktbeobachtungen. **Keine automatischen Orders, keine validierten Kaufalarme, keine belegte Trefferquote.**

## Ergebnis ansehen

[Aktueller Bericht](REPORT.md) · [Ausführungen](https://github.com/Justy-gtr/Moonshot-Radar/actions) · [Rohdaten](data/latest.json)

## Eingebaut

- GitHub Actions alle 15 Minuten rund um die Uhr; tatsächliche Ausführungen können verspätet sein oder ausfallen.
- FDA-Pressemitteilungen sowie SEC 8-K, 6-K und 424B-Feed-Ausschnitte. Eine Einreichung ist kein positiver Katalysator. Inhalte müssen im Original geprüft werden.
- Yahoo-Tagesgewinner als ergänzende, begrenzte Stichprobe. Keine vollständige Markt- oder Trade-Republic-Abdeckung.
- Quellenfehler, begrenzte Feed-Abdeckung, Abrufzeit und Feedzeit explizit erfasst. Atom-Updated ist nicht zwingend Erstveröffentlichung.
- Neue Meldungs-URLs nur einmal im Journal. Änderungen unter gleicher URL werden derzeit nicht erneut erkannt.
- Vergleich frischer Kurse zwischen Scans nur bei gleicher Währung und Abstand höchstens einer Stunde. Kurssplits werden noch nicht automatisch erkannt; Differenzen sind Prüfhinweise.
- Momentum-Prüfliste bei Tagesplus zwischen 0 und 5 %, höchstens fünf Minuten alten Kursen und Tagesvolumen mindestens 1,5-fachem durchschnittlichen GANZTAGESvolumen. Das ist keine zeitbereinigte relative Volumenrate, keine Vorhersage und kein Kaufsignal.
- Dauerhafte tägliche JSONL-Journale für neue Meldungen, alle beobachteten Kurse und Quellenzustände; keine nachträgliche Gewinnerauswahl.
- Bericht zeigt Meldungen der letzten 24 Stunden auch nach einem Scan ohne neue Meldung.
- Keine privaten Depotdaten, Zugangsdaten oder persönlichen Ziele im Repository.

## Grenzen und Erfolgsmessung

Die Quote verifizierter Handelssignale bleibt ausdrücklich **unbekannt**. Diese Software erzeugt nur Recherchehinweise. Ein getrenntes ChatGPT-Radar muss Firmenidentität, Originalmeldung, wirtschaftliche Bedeutung, Verwässerung, handelbare Kurse und TR-Verfügbarkeit prüfen. Die ursprünglichen Auswahlregeln gelten weiter.

Für eine belastbare +5%-Zielberührungsquote fehlen ein dauerhaftes Journal der tatsächlich ausgegebenen Handelssignale, verifizierte Referenzkurse, Börsenkalender und vollständige Folgekursverläufe. Ein Kandidat, der aus der Yahoo-Gewinnerliste verschwindet, darf nicht als Verlust oder Erfolg gewertet werden. Rohbeobachtungen sind keine ausgegebenen Handelssignale. Gebühren, Spread und Knock-outs sind nicht simuliert.

Kein direkter Push aus GitHub eingerichtet. Bestehende ChatGPT-Aufgaben können den Bericht lesen; die Verbindung muss in deren Auftrag stehen. Ausfälle sind in GitHub Actions und REPORT.md sichtbar. Falls GitHub gar keinen Lauf startet, kann der Bericht veralten: immer Zeitstempel prüfen.

TR-Instrumentenliste ist eine separat bereitgestellte Bestandsliste, kein Live-Zugang. Kein automatischer ISIN-Abgleich im Scanner vorhanden. Keine Aussage über aktuellen Spread, Derivate oder sofortige Handelbarkeit.

## Betrieb

Python 3.12, nur Standardbibliothek. `python -m unittest -v test_scanner.py`, dann `python scanner.py`.

Optionales GitHub-Secret `SEC_USER_AGENT` für eine korrekt identifizierende SEC-Kennung mit eigenem Kontakt. Ohne Secret verwendet der Bot seinen Projektnamen und die öffentliche Projekt-URL; SEC kann diesen Zugriff blockieren. Kein Umgehen von Sperren. Quellenfehler werden offen protokolliert. Dokumentation: https://www.sec.gov/about/developer-resources

Ein völlig fehlgeschlagener Abruf beendet sich mit Fehlercode; Teilausfälle ergeben `partial`. Beide werden protokolliert. Fehlerhaftes bestehendes Journal wird nicht stillschweigend zurückgesetzt. Workflow benötigt `contents: write` zum Speichern der Journale. Daten-Commits starten keinen weiteren Scan.
