# 0.1.0-alpha.6 · Einfacher einrichten

- Eigene Netzspitzen-Seite erscheint nach erfolgreicher Einrichtung automatisch in der Seitenleiste. Offizielle Custom-Panel-API, gemeinsamer Renderer mit der bisherigen Karte; keine manuelle Ressourcen- oder Dashboardkonfiguration für den ersten Einsatz.
- Mehrere Monitore über eine Auswahl öffnen. Tatsächliche Prognose-Entity-ID wird über die Registry aufgelöst, auch nach Umbenennung. Laden/Entladen/Entfernen verwaltet den gemeinsamen Sidebar-Link.
- Geführter Dialog: zuerst zwei Messquellen, dann ausdrücklich Bezugsrichtung und persönliches Ziel. Passende Einheiten, Geräte-/Zustandsklassen grenzen Kandidaten ein; eigene Sensoren ohne Geräteklasse bleiben unterstützt. Keine automatische semantische Quellen- oder Vorzeichenannahme.
- Meldealter und bekannte Zählerauflösung unter „Erweitert“. Unbekannte Auflösung bleibt 0 mit strenger Meldefrist. Bestehende bewusste Optionen bleiben beim Bearbeiten und Update erhalten.
- Vier-Schritte-Schnellstart, optionale Dashboardkarte und zusätzliche Testerchecks getrennt dokumentiert. Bereinigter GitHub-Export und reproduzierbare Pakete unter versionsbezogenen Pfaden.

**Update:** Backup erstellen, Komponentenordner bzw. HACS-Paket aktualisieren, HA regulär neu starten und Browser neu laden. Bestehende Integration nicht löschen. IDs, Archivformat, Datenqualitäts-/Quantisierungsregeln und persönliche Ziele bleiben erhalten. Nur eine zusätzlich verwendete Dashboardkarte braucht den aktualisierten Ressourceneintrag.

**Bereitstellung:** Eigenständiges Repository `Mario084/ha-grid-peak-monitor`. HACS erfordert dessen öffentliche Erreichbarkeit, passende Struktur und vorhandenes HACS. Standardkatalogaufnahme ist nicht Voraussetzung. Eine echte HACS-Installation steht als Nachweis noch aus; der ZIP-Fallback bleibt verfügbar.

---

# 0.1.0-alpha.5 – persönliches Ziel direkt in der Karte

Das persönliche kW-Ziel lässt sich jetzt unter **Persönliches Ziel → Ziel ändern** direkt im Dashboard eingeben und speichern. Freie Werte in 0,1-kW-Schritten sowie Dezimalkomma werden unterstützt. Die Karte findet die passende Ziel-Entität automatisch.

Die Eingabe bleibt bei Live-Aktualisierungen erhalten. Speichern ändert ausschließlich den Zielwert des ausgewählten Monitors. Doppelte Aufrufe während des Speicherns werden verhindert; bei Verbindungs- oder Berechtigungsfehlern bleibt die Eingabe erhalten und es wird keine erfolgreiche Änderung vorgetäuscht. Der bestätigte HA-Zustand bestimmt die Anzeige.

Das bestehende Ziel bleibt über Neustarts erhalten. Restbudget und Warnstatus werden neu berechnet. Geräte-Messwerte, Gerätesteuerung und das Archiv werden durch die Bedienung nicht geändert. Browser-Demos ohne Schreibzugriff bleiben bei der reinen Anzeige.

**Update:** Integration auf Alpha 5 aktualisieren, HA neu starten und die Kartenressource auf `/grid_peak_monitor_static/grid-peak-card.js?v=0.1.0-alpha.5` umstellen. Die Anleitung steht im [Schnellstart](docs/SCHNELLSTART.md).

Die grundlegenden Einschränkungen der privaten Alpha bleiben bestehen. Noch keine stabile 1.0 und keine HACS-Standardaufnahme. 

---

# 0.1.0-alpha.4 – Testversion für einen kleinen Testkreis

Diese Fassung ist für 1–2 Tester vorbereitet. Noch kein stabiles 1.0-Release und kein Eintrag im HACS-Standardkatalog.

## Änderungen

- Grob geschätzte Energiegrenzen bleiben nach ihrer Verwendung unverändert. Benachbarte Viertel verwenden denselben Grenzwert; später eintreffende Berichte verändern nicht einseitig die nächste Basis. Der reproduzierte Fall mit konstant 0,60 kW wird damit mit 0,60 kW statt 0,58 kW archiviert.
- Beim Update werden potenziell betroffene Alpha-3-Archivwerte als nicht verlässlich markiert. Sie fließen nicht mehr in die lokale Monatsspitze ein. Originale Testnachweise bleiben separat erhalten.
- Frischegrenzen bleiben ausdrücklich konfigurierbar. Ein tatsächlicher Abstand von 124 Sekunden überschreitet eine 120-Sekunden-Grenze; 180 Sekunden können für einen solchen Meldetakt passend sein. Ausfälle werden weiterhin anhand dieser gewählten Frist und fehlender/ungültiger Quellen erkannt.
- Anleitung für Installation, Sensorwahl, Kartenressource, Vergleich und Rückmeldung ergänzt. GitHub-Metadaten, Prüfläufe und Rückmeldeformular vorbereitet.

## Validierung und offene Punkte

Der vorige Live-Test wurde auf Nutzerwunsch nach rund 47½ Stunden beendet. Dabei entstanden 189 vollständige Viertelstunden, davon fünf ungültige. Er deckte Netzbezug und PV-/Akkubetrieb ab, fand aber den Archivfehler und gilt als **nicht bestanden**.

Die Korrektur wird separat mit den aufgezeichneten Quellen, neuen Regressionen und einer isolierten HA geprüft. Ein Offline-Replay ersetzt keine fehlenden Live-Intervalle. Den aktuellen Nachweis liefert [der Testbericht](docs/TESTBERICHT.md).

Geprüft ist HA 2026.10.2. Ein neuer Langzeitlauf der korrigierten Version, andere Zähler und die DS916 stehen aus. Der optionale Portalabgleich ist experimentell.

## Installation

[Tester-Anleitung](docs/TESTER.md). Installationsdatei: `grid-peak-monitor-0.1.0-alpha.4-install.zip`.

Das private Repository dient zunächst dem Testkreis. HACS unterstützt keine privaten Repositorys. Eine spätere öffentliche Veröffentlichung und HACS-Aufnahme werden getrennt vorbereitet.
