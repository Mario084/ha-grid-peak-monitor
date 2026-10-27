# Echte Messdaten ohne Änderung der produktiven HA-Konfiguration

Die Übernahme ist ein **lokales Testwerkzeug** neben der Integration. Sie läuft ausschließlich in der separaten Testinstanz. Auf der produktiven HA-Instanz muss keine Integration, Automation oder Konfigurationsdatei eingerichtet und nichts neu gestartet werden. Es werden keine Geräte gesteuert.

## Ablauf

1. Auf dem Entwicklungs-Mac die lokale Eingabemaske unter `http://127.0.0.1:8125/` öffnen.
2. Produktive HA-Adresse und **vorhandenen** langlebigen Zugriffstoken eingeben. Kein Token im Chat oder als Shell-Argument.
3. „Passende Sensoren suchen“ lädt einmal die Sensorliste lesend und zeigt passende Leistungs-/Energiequellen zur Auswahl. Das für die nächste Version ergänzte Suchfeld filtert beide Listen nach Name und Entity-ID. Gewählte Sensoren bleiben auch bei einem anderen Suchbegriff erhalten.
4. Gesamte Netzleistung, fortlaufenden Bezugsenergiezähler und Bezugsrichtung auswählen. Energie muss kumulierter Netzimport sein; PV-Ertrag, Haushaltsverbrauch und Tages-/Monatszähler passen nicht.
5. „Lesende Übernahme starten“ prüft beide Quellen per GET und speichert die Verbindung nur lokal.
6. Im angemeldeten **Test-HA** die Ansicht **Echte Messdaten** öffnen: `http://<test-ha>:8124/lovelace/echte-messdaten`. Falls nötig zuerst dort einen eigenen Testbenutzer anlegen und die Ersteinrichtung abschließen. Nach der Auswahl die Dashboard-Konfiguration neu laden, falls die Ansicht noch den Einrichtungshinweis zeigt.

Die laufende Testinstanz erkennt die gespeicherte Auswahl automatisch. Die beiden gewählten Zustände werden etwa alle fünf Sekunden kopiert. Dafür werden nur `GET /api/states/<entity_id>` verwendet. Der Leser hat keinen POST-/PUT-/DELETE-Pfad, keinen Serviceaufruf, folgt keinen Weiterleitungen und verwendet keine Umgebungs-Proxys.

Ein vorhandener Token kann technisch mehr Rechte besitzen. **Der Token wird durch dieses Werkzeug nicht auf Lesen beschränkt; der verwendete Client führt ausschließlich GET-Abfragen aus.** Wer keinen vorhandenen Token hat, müsste einen neuen im Benutzerprofil anlegen – das wäre eine separate Änderung am Konto. Normale Zugriffs-/Authentifizierungsprotokolle können durch API-Lesezugriffe aktualisiert werden. „Ohne Änderung“ bedeutet hier: keine Änderung an produktiver Konfiguration, Entitäten, Automationen oder Geräten.

## Trennung und Datenqualität

- Demo und echte Daten verwenden verschiedene Quellsensoren und verschiedene Monitor-Einträge.
- Das echte Archiv startet leer. Es werden weder künstliche Demo-Spitzen übernommen noch frühere Produktionsdaten ungeprüft importiert.
- Der erste angebrochene Zeitraum bleibt unvollständig. Erst ein danach vollständig erfasstes Viertel kann im Archiv erscheinen.
- Ein Quellenwechsel bekommt eigene interne Sensor-IDs, damit Zähler verschiedener Quellen nicht vermischt werden.
- Die Kopien behalten über `grid_peak_source_reported_at` den ursprünglichen HA-Meldezeitpunkt. Regelmäßiges Polling erneuert diesen Zeitstempel nicht.
- Falls die Quelle kein `last_reported` liefert, wird konservativ `last_updated` verwendet. Gleichbleibende Werte können dann als veraltet erscheinen; es wird kein aktueller Bericht erfunden.
- Verbindungsfehler oder fehlende Quellen werden im Test als `unavailable` dargestellt. Veraltete Werte ergeben keine frische Prognose.
- Die öffentliche, anmeldefreie Demo zeigt weiterhin ausschließlich synthetische Werte. Echte Daten erscheinen nur in der normalen authentifizierten HA-Oberfläche.

## Lokale Dateien

`output/live-source.json` enthält URL, Token und gewählte Entity-IDs und bekommt Dateirechte `0600`. Der gesamte Ordner `output/` ist ignoriert und wird vom ZIP-Bauer nicht eingepackt. `output/ha-preview-config/live-status.json` enthält nur einen technischen Zustand und gegebenenfalls einen festen Fehlercode; keine Zugangsdaten oder Messwerte.

Der Einrichtungsserver bindet ausschließlich an Loopback auf dem Mac, prüft Host/Origin und verlangt für Formulare einen zufälligen CSRF-Wert. Er protokolliert keine HTTP-Anfragen. Die Eingabemaske ist deshalb nicht über andere Rechner im Heimnetz erreichbar.

Die Konfiguration, Archive und Benutzer der Testinstanz liegen wie bisher unter `output/ha-preview-config`. Auch dieser Ordner gehört nie in ein öffentliches Repository oder ZIP. Echte Daten sind privat; weitergegebene Screenshots und Logs entsprechend auswählen.

## Betrieb und Abschalten

Die lokale Eingabemaske bei Bedarf im Quellprojekt starten:

```sh
python3 scripts/configure_live_source.py
```

Die HA-Testinstanz liest die gewählte Verbindung über `scripts/live_mirror.py` ein. Sie benötigt dafür keinen zusätzlichen öffentlichen Integrationscode und verändert keine produktiven Zustände. Der Rechenkern verwendet die normalen kopierten Testentitäten.

Zum sicheren Beenden der laufenden Übernahme ausschließlich den eigenen Testcontainer stoppen:

```sh
docker stop grid-peak-monitor-preview
```

Danach kann `output/live-source.json` gezielt entfernt werden; vor einem erneuten Start wird dann keine Verbindung mehr aufgebaut. Keine bestehende produktive Konfiguration und keine fremden Container löschen.

## Bisher geprüft

- GET-Beschränkung, blockierte Endpunkte/Weiterleitungen, private Speicherung, Zeitstempel und Fehlerfälle gegen eine künstliche Loopback-Quelle.
- Vollständige Übernahme in einem echten HA-Container **ohne externes Netzwerk**: eigene Sensoren, separater leerer Archivstart, Minimum 4,8 kW aus Testwerten, veraltete Quellen, Ausfall sowie Erhalt des persönlichen Ziels bei Neustart des Übernahmehelfers.
- Lokale Eingabemaske mit synthetischen Browserantworten: Sensorwahl, verdeckter Token, Löschen des Tokenfelds nach Speichern und Abweisung einer Anfrage ohne CSRF-Wert.

Der reale Praxistest beginnt erst nach lokaler Token-Eingabe und Sensorwahl. Das Einrichten des Helfers allein beweist noch keinen erfolgreichen Abruf echter Messwerte.

Offizielle Grundlage: [Home Assistant REST API](https://contributors.home-assistant.io/core/internals/rest-api/).
