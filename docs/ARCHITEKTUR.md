# Aufbau und Daten

`custom_components/grid_peak_monitor` ist die komplette installierbare Integration. Es gibt keinen separaten npm-Build, Python-Generator oder zweiten Karten-Download.

| Datei | Aufgabe |
| --- | --- |
| `core.py` | Unabhängiger Rechenkern, Intervallarchiv, Datenqualität, Sommerzeit, Speicherformat. Nur Python-Standardbibliothek. |
| `coordinator.py` | HA-Sensoren lesen, Einheiten umrechnen, Zustands-/Berichtsereignisse und 10-Sekunden-Takt, Speichern. |
| `config_flow.py` | Einrichten und Optionen über HA. |
| `sensor.py`, `number.py` | Eigene Ergebnis- und Ziel-Entitäten. |
| `__init__.py` | Laden/Entladen, statische Karten-Dateien und authentifizierter Verlauf. |
| `frontend/` | Karte, visueller Editor und reine Anzeigehelfer. |

## Berechnung

Für das aktuelle Fenster wird eine Energie-Basis an dessen UTC-Anfang benötigt. Treffen zeitnahe Energieberichte auf beiden Seiten einer Grenze ein, wird die Grenze linear interpoliert. Der Abstand darf höchstens dem konfigurierten Meldealter entsprechen. Zählerrücksetzungen, ungültige Zustände und größere Lücken machen betroffene Intervalle unvollständig. Aus einer mehrteiligen Lücke wird kein einzelner Peak gebildet.

Optional berücksichtigt `energy_resolution_kwh` die bekannte Auflösung eines nur bei Änderungen meldenden Zählers. Kontinuierlich frische Netzleistung kann dabei unveränderte Energie plausibilisieren und beobachtete Grenzen als `quantized_counter` kennzeichnen. Ein durch echte Leistungsmeldungen bestätigter Verbrauchsnachweis erkennt eingefrorene Zahlenwerte auch bei frischen Zeitstempeln. Getrennte kleinere Regelausschläge werden nicht zu einem stundenlangen Fehlernachweis addiert; große bestätigte Bezugspulse bleiben zusätzlich geprüft. [Regeln, Genauigkeit und Grenzen](FRISCHEPRUEFUNG.md).

Für `E` bereits importierte kWh, `P` aktuelle Importleistung in kW und `r` verbleibende Sekunden:

- Minimum: `E × 4`.
- Prognose: `(E + P × r / 3600) × 4`.
- Erlaubter Restbezug: `max(0, (Ziel / 4 − E) × 3600 / r)`.
- Zusätzliche Leistung: erlaubter Restbezug minus `P`.

Die Prognose kann nie unter das bereits erreichte Minimum sinken. Negative Importleistung wird nach der konfigurierten Vorzeichenumkehr auf null begrenzt; der separate Energiezähler muss trotzdem ausschließlich Netzimport zählen.

Warnstatus sind `no_data`, `below`, `near`, `checking`, `risk`, `reached`, `exceeded`. Die Karte übersetzt diese in deutsche Texte. Eine drohende Überschreitung braucht 20 Sekunden Bestätigung; das physikalisch erreichte Minimum wirkt sofort. Die Bestätigung wird bei einer neuen Viertelstunde zurückgesetzt.

## Archiv und Neustarts

Die Store-Datei heißt `.storage/grid_peak_monitor.<entry_id>`. Sie enthält Version, zugeordnete Quellsensor-IDs, letzte Energie, gültige Energiegrenzen, Qualitätsmarkierungen und maximal etwa 93 Tage abgeschlossene Intervalle. Es werden keine Zugangsdaten gelesen oder gespeichert. Häufige Berichte verschieben die geplante Speicherung nicht endlos; ein Schreibvorgang wird mit 15 Sekunden Verzögerung gebündelt. Bei regulärem Entladen wird zusätzlich gespeichert. Bei einem Absturz können die letzten noch nicht geschriebenen Beobachtungen fehlen.

Beim Neustart wird nur zum selben Sensorpaar passender Zustand übernommen. Eine Nullleistungs-Beweiskette wird bewusst nicht über einen Neustart hinweg fortgeführt. Lange Ausfälle werden als Lücken markiert. Ein laufendes Fenster mit bekanntem, frischem Energieanker kann weitergerechnet werden. Es erfolgt kein Import aus Recorder oder fremden Integrationsspeichern.

Auch der kontinuierliche Leistungsnachweis der Auflösungsprüfung wird nach einem Neustart neu aufgebaut. Ein bereits erkannter Zählerstillstand bleibt gespeichert, bis der Zähler tatsächlich weiterzählt. Die Qualitätsmethode beobachteter Energiegrenzen und Archivzeilen bleibt ebenfalls erhalten.

Die eigene Store-Datei kann nach dem Entfernen der Integration zurückbleiben. Für vollständiges Löschen: Entry-ID vorher aus dem Prognosesensor-Attribut `monitor_id` notieren, Test-HA stoppen und ausschließlich `.storage/grid_peak_monitor.<diese_id>` löschen. Keine anderen `.storage`-Dateien verändern.

## Optionale Quellzeitstempel bei lesenden Kopien

Der HA-Adapter respektiert ein optionales Attribut `grid_peak_source_reported_at` mit zeitzonenbehaftetem ISO-Zeitstempel. Der lokale Testhelfer setzt es auf den ursprünglichen Meldezeitpunkt der produktiven Entität. Ungültige Zeitstempel werden als fehlende Probe behandelt. Ohne dieses Attribut gilt wie bisher der lokale HA-Meldezeitpunkt. Dadurch können regelmäßige Kopierabfragen einen alten Quellwert nicht künstlich frisch halten.

Die Testübernahme liegt außerhalb des installierten Komponentenordners unter `scripts/`. Sie ist keine Verbindung, die bei normaler Installation der Integration automatisch aktiviert wird. [Echte Messdaten](ECHTE-MESSDATEN.md).

## Eigene Seite und geführte Einrichtung

`panel.py` registriert nach erfolgreichem Laden den gemeinsamen Pfad `/grid-peak-monitor` über `panel_custom.async_register_panel`. Der letzte entladene Monitor entfernt den Panel-Link; weitere Einträge erzeugen keine Duplikate. Das Panel lädt sein eigenes versioniertes Modul und benötigt keine Lovelace-Ressourcenmutation. `grid_peak_monitor/monitors` liefert authentifiziert nur geladene Einträge und löst Prognose-Entitäten über die Entity Registry auf. Die browserseitige Auswahl betrifft nur die Darstellung, nicht die Messquellen. Panel und optionale Dashboardkarte verwenden `grid-peak-card.js` und `model.js` gemeinsam.

Der Zwei-Schritt-Configflow speichert weiterhin das ursprüngliche flache Datenformat, `VERSION = 1`. Daher ist keine Migration und keine Neuanlage bestehender Einträge erforderlich. Optionen werden zusammengeführt, nicht auf neue Standardwerte zurückgesetzt. Rechenkern, Archivformat und Entity-Unique-IDs bleiben unverändert.

## Frontend und optionales Portal

Ein kleiner aktueller Snapshot hängt am Prognose-Sensor. Das Archiv wird separat über die authentifizierte HA-WebSocket-Verbindung mit `grid_peak_monitor/history` angefordert. Das hält große Verlaufslisten aus den Sensorattributen heraus. Abfragen sind auf den aufbewahrten Zeitraum begrenzt.

Die Karte ruft ausschließlich bei explizitem `portal_history: true` zusätzlich den bestehenden Befehl `netznoe_quarter_audit/history` auf. Sie benötigt keine Portal-Zugangsdaten. Das Projekt enthält keinen Netz-NÖ-Importer. Portalzeilen werden nach UTC-Zeit und ausgewähltem Tag geprüft, ungültige Werte verworfen und passende lokale Slots ohne Verdoppelung ersetzt.

Der gesamte hier enthaltene Code wurde eigenständig geschrieben. Code von PeakShavr oder Peak Power Forecast wurde nicht übernommen. Dieses Projekt hat keine automatische Gerätesteuerung oder Verbindung zur produktiven HA-Installation.
