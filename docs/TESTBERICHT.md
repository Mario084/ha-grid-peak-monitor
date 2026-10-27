# Alpha 6 · lokale Installationsvereinfachung (27.10.2026)

- 90 vorhandene Python-Tests und 9 JavaScript-Modelltests bestanden. Rechenkern, Coordinator, Sensor-/Number-Unique-IDs und Archivformat gegenüber Alpha 5 unverändert.
- Offizielles HA-Image 2026.10.2: bisheriger Laufzeittest, Frische-/Quantisierungsregression und zusätzlicher Installation-/Panel-Lifecycletest in jeweils frischer netzloser Konfiguration bestanden.
- Neue Einrichtung: Quellenfilter, eigene Sensoren ohne Geräteklasse, ungültige/fehlende Quelle, explizite Richtung, eingeklappte erweiterte Optionen und Erhalt bewusster Einstellungen geprüft.
- Panel: zwei Monitore teilen einen Sidebar-Link; Registry-Umbenennung, authentifizierte Admin-/Nutzerabfrage, Entladen/Entfernen/Wiederladen und Archiv-/ID-Erhalt geprüft.
- Echtes HA-Frontend in einer zusätzlichen wegwerfbaren synthetischen Instanz: Sidebar → Seite, echte Zielbedienung 10 → 10,1 → 10 samt Backendwert, Monitorwahl, Browser-/Config-Entry-Reload, Auswahlpersistenz, Mobilmenü und 390/1280px ohne horizontalen Überlauf bestanden. Keine Browserfehler.
- Bisherige Karten-/Zielbedienungstests mit synthetischen Quellen bestanden (auch 320px, Fokus und Servicefehler). Neuer isolierter Browsertest für Panel-Discoveryfehler, Retry und leere Monitorliste bestanden.
- hassfest: **1 Integration, 0 ungültig**. Offline-Paketvalidator prüft HACS-Struktur, Manifest, Branddateien, Sprachdateien, Module, ZIP-Inhalte und Prüfsummen.

Keine produktive HA, vorhandene Previewinstanz oder EVCC-Konfiguration verändert. Keine echten Quellwerte/Geheimnisse in Testcontainern. Keine GitHub-Veröffentlichung, öffentliche HACS-Action oder echte HACS-Installation durchgeführt. HACS-Tauglichkeit ist lokal strukturell vorbereitet; öffentliche Erreichbarkeit und Installation bleiben separate Nachweise. Mehrtägiger Alpha6-Livetest, andere HA-Versionen und andere Zähler sind weiterhin offen.

Die UI-Fixture `tests/ha_panel_ui_server.py` darf ausschließlich mit neuer temporärer Konfiguration und synthetischen Quellen laufen; der Browser prüft ihre Identität vor Schreibtests. Authmaterial und Screens entstehen außerhalb des Release-Allowlists. Die bestehenden Spiegel-/Liveentwicklungswerkzeuge werden dabei nicht gestartet.

## PDF-Handoff

Im Projekt ist kein wiederverwendbarer PDF-Generator vorhanden. Der vollständige neue Erstablauf steht in `docs/SCHNELLSTART.md`, die Zusatztests in `docs/TESTER.md`, die optionale Dashboardkarte in `docs/DASHBOARD-KARTE.md`. Diese geprüften Texte bilden den Inhalt einer späteren Kurz-PDF; die bisherige Alpha5-PDF bleibt unverändert.

---

## Frühere Nachweise (Alpha 5 und älter)

# Testbericht – Alpha 4 und Alpha 5

Stand: 27.10.2026. Aktuelle Testversion: 0.1.0-alpha.5. Die Fassung ist für einen kleinen privaten Testkreis vorbereitet, nicht als stabiles 1.0-Release freigegeben. Produktive HA wurde nicht verändert. Es wurde nichts veröffentlicht.

## Beendeter Praxistest der Alpha 3

Der beauftragte 48-Stunden-Lauf wurde auf Nutzerwunsch nach **47,54 Stunden** beendet. Aufgezeichnet wurden **33.925 Beobachtungen** und **189 vollständige Viertelstunden**, davon **fünf ungültige**. Es gab echten Netzbezug und Phasen mit PV-/Akkudeckung. Die Testinstanz lief ohne Neustart durch den ursprünglichen Test.

Die laufenden Formeln zeigten keine unabhängigen Rechenabweichungen, das Archiv aber einen echten Fehler: Eine bereits verwendete grobe Grenze konnte später einseitig durch Interpolation verändert werden. Der isolierte Gegenbeweis mit konstant 0,60 kW ergab in Alpha 3 fälschlich 0,58 kW. Dieser Live-Lauf gilt deshalb **nicht als bestanden**. Ursprüngliche Daten, Quellcode und Nachweise bleiben privat erhalten.

Zusätzlich wurden kurze nicht verwertbare Quellenzustände und ein Abstand von **124,38 Sekunden** zwischen Leistungsmeldungen beobachtet. Letzterer überschritt die eingestellte harte 120-Sekunden-Grenze, während der Energiezähler weiter meldete. Die beschädigten Intervalle wurden nicht mit null aufgefüllt. Die genaue Ursache der anderen kurzen Quellenunterbrechungen ist aus dem Mitschnitt erfolgreicher Abfragen nicht abschließend ableitbar.

## Korrektur und Nachprüfung der Alpha 4

- Grobe Energiegrenzen bleiben nach ihrer Verwendung unverändert. Beide angrenzenden Viertel verwenden denselben Wert. Die konstanten 0,60 kW werden nun auch mit versetzten 10-Wh-Berichten korrekt auf beide Intervalle verteilt.
- Neue Regressionen prüfen Energieerhaltung, unveränderte abgeschlossene Werte, Neustart an einer groben Grenze und die Kennzeichnung alter Alpha-3-Archive.
- Die Frischegrenze wird nicht automatisch verlängert. Mit ausdrücklich gewählten 180 Sekunden ist ein Abstand von 124 Sekunden erlaubt; 181 Sekunden alte Leistung sperrt weiterhin. Fehlende Quellen und eingefrorene Energiezähler bleiben erkennbar.

| Prüfung | Ergebnis |
| --- | --- |
| Python-Suite, einschließlich Rechenkern, Quellenleser, Audit und lokalem Wächter | **90 Tests bestanden** |
| JavaScript-Anzeigemodell | **5 Tests bestanden** |
| Offline-Replay der 33.925 ursprünglichen Beobachtungen durch den korrigierten Kern | **33.761 gültige Rechenpunkte**, keine Rechenabweichungen |
| Unabhängiger Archivvergleich im Replay | **177 Intervalle bestätigt**, 11 gültige Zeilen ohne vollständigen unabhängigen Grenznachweis; keine als geprüft ausgegebenen Ersatzwerte |
| Nach dem Replay eingespritzter dauerhafter Zählerstillstand bei 3,6 kW | Nach **180 Sekunden erkannt**, Prognose ausgeblendet |
| Echter HA-Laufzeittest mit frischer Konfiguration | Einrichtung, neun Sensoren, Ziel-Entität, Optionen, Speichern, Reload, authentifizierter Verlauf, Kartenressource und Unload bestanden |
| Zusätzlicher HA-Adaptertest mit Testuhr | PV/Akku, kurze Regelausschläge, große Pulse, eingefrorener Zähler, `unavailable`, Originalzeitstempel sowie neue Archiv- und 180-Sekunden-Fälle bestanden |
| Chromium-Kartenprüfung | Überblick, Verlauf, Geräte, 9:16, Datumsauswahl, Portal-Fallback, Editor, 320/390-px-Breite; keine JavaScript-Fehler |
| Offizieller hassfest-Container | **1 Integration, 0 ungültige Integrationen**, ohne Netzwerk gegen den bereinigten Export geprüft |
| Eigene persistente Testinstanz | Alpha 4, Meldealter 180 Sekunden, Speicherversion 2 und Kennzeichnung alter Archivwerte lesend geprüft; produktive HA unverändert |

Der Quellenmitschnitt erfasst erfolgreiche Spiegelabfragen. Kurzzeitig nicht verfügbare Zustände können darin fehlen. Das Replay ist deshalb eine Regressionsprüfung der aufgezeichneten Quellen und **kein Ersatz für den ursprünglichen Live-Test**. Es repariert weder dessen fünf ungültige Intervalle noch sein Archiv.

Die Prüfung der laufenden Karte verwendete authentifiziert gelesene Test-HA-Zustände und Verlauf sowie die von dieser Instanz ausgelieferten Kartendateien. Der komplette HA-Frontend-Login wurde dabei nicht automatisiert durchgespielt. Screenshots echter Messdaten bleiben im privaten `output/`; der Screenshot in der README enthält nur synthetische Werte.

## Reproduzieren

Im Quellprojekt:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_model.mjs
python3 scripts/build_release.py
```

Browser-QA benötigt zusätzlich separat installiertes Playwright und Chromium:

```sh
node tests/browser.mjs
```

HA-Laufzeittest ausschließlich mit neuer Wegwerf-Konfiguration, ohne Netzwerk und ohne bestehendes HA-Volume:

```sh
docker run --rm --network none --cap-drop ALL --pids-limit 128 --memory 1g \
  --mount "type=bind,source=$PWD,target=/work,readonly" \
  --entrypoint python ghcr.io/home-assistant/home-assistant:2026.10.2 \
  /work/tests/ha_runtime.py
```

Für die Frische- und Archivregression denselben Befehl mit `/work/tests/ha_freshness_runtime.py` verwenden. Die GitHub-Workflows enthalten beide Prüfungen. Die Build-Prüfung verwendet eine Dateiliste, schließt private Laufzeitverzeichnisse aus und prüft unter anderem lokale Adressen, Benutzerpfade, private Schlüssel und typische Tokens. Installations- und Quellpaket bekommen SHA-256-Prüfsummen.

## Noch offen

- Neuer mehrtägiger Live-Lauf der korrigierten Fassung und Rückmeldungen der 1–2 Tester.
- Andere Zähler, HA-Versionen, Browser und die Synology DS916.
- Echter Ende-zu-Ende-Abgleich des optionalen Netz-NÖ-Adapters.
- GitHub-Actions-Ausführung im tatsächlichen Repository und öffentliche HACS-Validierung. Lokale Metadatenprüfung und vorbereitete Workflows sind noch kein HACS-Katalogeintrag.

Der alte Wächter und seine Wachhaltefunktion wurden beim Nutzer-Stopp beendet. Die eigene HA-Testinstanz und ihre Konfiguration bleiben für weitere Prüfungen verfügbar; es wurde kein neuer Langzeitwächter gestartet.


## Ergänzung 27.10.2026 – Alpha 5, Ziel direkt in der Karte

Die Karte stellt das persönliche Ziel jetzt mit „Ziel ändern“, Dezimalfeld, Speichern und Abbrechen dar. Sie findet ausschließlich die eindeutig zugeordnete Ziel-Number des ausgewählten Monitors. Der Number-Dienst der Integration speichert das Ziel in den bestehenden Optionen; Restbudget und Warnstatus werden neu berechnet.

- Die Python-Suite bleibt bei **90 bestandenen Tests**. Das JavaScript-Modell hat jetzt **9 bestandene Tests** einschließlich Zielzuordnung, Verfügbarkeit, Mehrdeutigkeit, Dezimalkomma, Wertebereich und Schrittweite.
- Ein eigener Chromium-Test prüft direkte Bedienung, Bestätigung per Enter, Fehler/Rücknahme, unveränderte Eingaben und Fokus trotz Live-Berichten, weiterlaufenden Countdown, doppelte Speicherversuche, Wechsel des Monitors während einer Anfrage, schreibgeschützte Ansichten sowie 320/390-px-Darstellung. Keine JavaScript-Fehler und keine echten Serviceaufrufe in diesem synthetischen Test.
- Der bestehende Browser-Test für Verlauf, Geräte, Editor, Portal-Fallback und Smartphone-Ansichten besteht weiterhin.
- Der echte isolierte HA-Laufzeittest prüft die eindeutige Ziel-Kennzeichnung, Änderung über `number.set_value`, den neuen Zielwert im Snapshot, gespeicherte Optionen und Erhalt über einen Integration-Reload.
- Die Bedienung wurde zusätzlich im Browser gegen die eigene persistente HA-Testinstanz geprüft. Genau deren zugehöriger Zielwert wurde kurz geändert, der neue Wert im Monitor bestätigt und anschließend der ursprüngliche Wert wiederhergestellt. Die produktive HA wurde dabei nicht kontaktiert oder verändert.
- Offizieller hassfest-Lauf gegen den bereinigten Alpha-5-Export: **eine Integration, null ungültige Integrationen**.

Für Alpha 5 sind Integration und Kartenressource gemeinsam zu aktualisieren. Die bisherigen Langzeit-/Portal-/Zählergrenzen gelten weiter. Die Produktivansicht aus Marios Screenshot ist ein separates bestehendes Dashboard und wurde nicht durch diese Entwicklung geändert.
