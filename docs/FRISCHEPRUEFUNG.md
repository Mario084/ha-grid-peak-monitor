# Selten meldende Importzähler

Ein Importzähler mit 0,01 kWh Auflösung zählt in 10-Wh-Schritten. Bei 100 W Netzbezug braucht ein Schritt etwa sechs Minuten; bei 11 W etwa 55 Minuten. Versorgt die PV das Haus, kann der Importzähler sehr lange unverändert bleiben. Der PV-Ertrag selbst wird nicht als Netzbezug verwendet: Entscheidend ist die vorzeichenrichtig ausgewertete Netzleistung.

In den Integrationsoptionen kann die **bekannte Zählerauflösung in kWh** eingestellt werden. `0` ist der Standard und behält die strenge Meldefrist bei. `0,01` aktiviert die Prüfung für einen 10-Wh-Zähler. Eine zu groß eingestellte Auflösung verzögert die Fehlererkennung und verschlechtert die Schätzung; die Auflösung wird nicht aus der Anzahl dargestellter Nachkommastellen geraten.

## Was die Prüfung beobachtet

- Die Netzleistung muss weiterhin spätestens innerhalb des eingestellten Meldealters berichten. Die Zeitstempel der Quelle bleiben erhalten; erneutes Abfragen macht alte Werte nicht frisch.
- Für die Plausibilitätsprüfung zählen **unterschiedliche echte Leistungsmeldungen**. Zwischen zwei Berichten wird vorsichtig der kleinere der beiden Bezugswerte angesetzt. Wiederholte Abfragen derselben Meldung sammeln keine weitere Verbrauchsevidenz. Dies ist keine zweite Energiemessung für Prognose oder Archiv.
- Ein Bericht mit null Bezug oder Einspeisung beendet eine noch unbestätigte Bezugsphase. Kleinere, getrennte Regelausschläge können sich dadurch nicht über Stunden zu einem Stillstandsalarm aufsummieren. Bereits vom Energiezähler gezählter Import wird dabei weder gelöscht noch mit Export verrechnet.
- Für einen Stillstandsalarm bei anhaltendem Bezug muss eine durch echte Meldungen bestätigte Bezugsphase mindestens `max_age` Sekunden umfassen. Darin müssen mehr als zwei konfigurierte Zählerschritte Bezug erwartet werden, ohne dass der Zähler danach innerhalb weiterer `max_age` Sekunden steigt. Sind diese Voraussetzungen noch nicht erfüllt, wird ein kurzer Ausschlag nicht als Zählerausfall bewertet.
- Ein zusätzlicher Schutz gilt für **große, durch mehrere Berichte bestätigte Bezugspulse**: Überschreitet die einzelne Phase vier Zählerschritte, muss der Zähler innerhalb `max_age` Sekunden weiterzählen. Diese offene Prüfung bleibt bei anschließendem Export bestehen. So kann ein großer echter Verbrauch nicht allein durch die Rückkehr zu null aus der Fehlerprüfung verschwinden. Die höhere Toleranz berücksichtigt die kürzere Beobachtung; kleine getrennte Pulse werden nicht addiert.
- Wenn solche belastbaren Erwartungen offen sind, genügt ein alter Energiebericht nicht mehr für eine Prognose. Frisch berichtete Energie bleibt innerhalb der normalen Meldefrist verwendbar, bis ein Stillstand bestätigt ist.
- Ein nach diesen Regeln bestätigter Fehler bleibt bei späterem Export, Viertelstundenwechsel und Neustart gesetzt. Ein tatsächlich steigender Zählerstand kann ihn lösen. Beschädigte Intervalle bleiben unvollständig; während einer offenen Bestätigung wird der Archivabschluss kurz zurückgehalten.
- Fehlende/ungültige Quellen, veraltete Netzleistung, Zählerrücksetzungen und unplausible Sprünge sperren weiterhin die Berechnung. Beobachtungslücken verwerfen die kontinuierliche Beweiskette und lassen betroffene Viertel unvollständig.

Beispiel bei 10 Wh Auflösung und 120 Sekunden Meldealter: Gleichbleibender Bezug von 3,6 kW muss durch mehrere echte Berichte über mindestens zwei Minuten bestätigt sein. Bei alle 30 Sekunden neu gemeldeter Leistung wird ein eingefrorener Zähler im Test nach etwa drei Minuten erkannt. Bei sehr kleinem, aber anhaltendem Bezug dauert es entsprechend länger, bis zwei Zählerschritte plausibel erwartet werden. Nur scheinbar neue Energieberichte mit unverändertem Zahlenwert setzen die Prüfung nicht zurück.

Die Frischeprüfung diagnostiziert anhand diskreter Quellen. Sie ersetzt weder eine kontinuierliche Leistungsmessung noch die Fehlerdiagnose des Zählers selbst. Kurze, kleinere Bezugspulse allein beweisen keinen Zählerdefekt; bei deren hoher Wiederholrate lässt sich ein ungemeldeter Energiezählerfehler nicht in jedem Fall sicher von Regelschwankungen unterscheiden. `unavailable` oder fehlende Leistungsmeldungen werden auch dann weiterhin erkannt.

## Grenzen und Darstellung

Nach Start oder einer Lücke kann ein alter Energiebericht erst dann wieder eine aktuelle Viertelstunde tragen, wenn deren Anfang durchgehend beobachtet wurde. Frühere Lücken werden nicht rückwirkend aufgefüllt. Der Nachweis kontinuierlicher Leistung wird nicht gespeichert oder nach einem Neustart vorausgesetzt.

An so beobachteten Intervallgrenzen wird der vorhandene Zählerstand als grobe Energiegrenze verwendet. Solche Archivzeilen tragen `method: quantized_counter`; die Karte kennzeichnet dies im Balkendetail. Während der laufenden Viertelstunde erscheint bei einem alten, plausiblen Zählerstand der Hinweis „Zähler unverändert · Stillstand mit frischer Netzleistung geprüft“. Originale Meldezeitpunkte bleiben erhalten.

Die Ergebnisse bleiben lokale Schätzungen. Ein Zählerschritt von 10 Wh entspricht 0,04 kW im Viertelstundenmittel. Rundung, Meldeverzug, Interpolation und der Abstand der Leistungsmeldungen begrenzen die Genauigkeit von Minimum, Prognose und Restbudget. Ein angezeigtes `0,00 kW` ist kein Nachweis exakt null importierter Energie. Das Archiv ersetzt keine Netzbetreiberdaten.

Ein nicht als `unavailable` gemeldeter Defekt des Energiezählers ist bei tatsächlich ausbleibendem Netzbezug anhand dieser beiden Messwerte allein nicht von normalem Stillstand unterscheidbar. Die Leistung bleibt trotzdem einer harten Altersprüfung unterworfen; bei wieder einsetzendem Bezug prüft der Verbrauchsnachweis den eingefrorenen Zähler weiter.

## Tests

Die Rechenkern- und HA-Laufzeittests prüfen alten Zählerstand bei Export, stundenlange kurze Regelausschläge, große unbestätigte Pulse, kleine dauerhafte Last, normale hohe Last mit minütlichen Energieberichten, eingefrorene Zähler mit alten und fortlaufend neuen Zeitstempeln, zwischengespeicherte Leistung, Last über mehrere Viertel, Neustart, Datenlücken, `unavailable`, Reset, Sprung und Erholung. `tests/ha_freshness_runtime.py` führt diese Fälle mit echtem HA-Adapter, simulierten Quellen und Testuhr in einem isolierten Container aus. Eine produktive HA wird dabei nicht kontaktiert.

## Update von Alpha 2

Der gespeicherte Nachweis der Stillstandsprüfung trägt jetzt eine eigene Version. Ein alter Alpha-2-Alarm, der noch auf der fehleranfälligen Addition getrennter Ausschläge beruhen kann, wird beim Update neu beurteilt. Historische unvollständige Intervalle werden dabei nicht nachträglich gültig gesetzt oder mit Replay-Daten gefüllt. Bereits unter der neuen Regel bestätigte Fehler bleiben über Neustarts erhalten. Der kontinuierliche Leistungsnachweis muss nach jedem Neustart neu aufgebaut werden.


## Alpha 4: unveränderliche Grenzen und Meldetakt

Eine einmal als grobe Energiegrenze verwendete Beobachtung bleibt unverändert. Sonst könnte eine spätere Interpolation nur die nächste Viertelstundenbasis verändern, obwohl der vorherige Archivwert bereits gespeichert ist. Benachbarte Intervalle verwenden ab Alpha 4 dieselbe grobe Grenze. Zeitnahe Interpolation ohne solche bereits verwendeten groben Grenzen bleibt verfügbar.

Das Speicherformat trägt `accounting_version: 2`. Potenziell betroffene gültige `quantized_counter`-Zeilen aus älteren Testversionen werden beim Update als `legacy_boundary` ohne belastbaren kW-Wert übernommen. Sie zählen nicht zur Monatsspitze. Die laufende alte Grenze wird verworfen; Originalnachweise werden nicht nachträglich umgeschrieben.

Im Praxistest lagen zwischen zwei ursprünglichen Leistungsmeldungen einmal 124,38 Sekunden. Bei 120 Sekunden Höchstalter war `power_stale` damit die korrekte Bewertung der eingestellten Grenze, obwohl der Energiezähler weiter meldete. Für diesen Meldetakt kann ausdrücklich 180 Sekunden gewählt werden. Die Vorgabe bleibt 120 Sekunden, alte Zeitstempel werden nicht erneuert, und bei 180 Sekunden stoppt die Berechnung nach Überschreitung dieser Grenze. `unavailable`, Reset und bestätigter Stillstand sperren weiterhin. Es gibt keine automatische Ausdehnung der Frist.
