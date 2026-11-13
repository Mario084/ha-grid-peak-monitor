# Grid Peak Monitor installieren

**Testversion 0.1.0-alpha.7 · von Daheim im Detail**

Der Monitor zeigt dir deinen Netzbezug und die voraussichtliche Leistungsspitze der laufenden Viertelstunde. Er schaltet keine Geräte. Geprüft mit Home Assistant 2026.10.2 und 2026.10.4; noch eine Alpha zum Ausprobieren.

## Das brauchst du

Home Assistant mit Administratorzugriff und zwei bereits vorhandene Sensoren:

- **Netzleistung in W oder kW:** die gesamte Leistung am Netzanschluss, nicht PV-Erzeugung oder Hausverbrauch.
- **Netzbezug in Wh, kWh oder MWh:** ein fortlaufender Zähler ausschließlich für bezogene Energie. Kein Tageszähler und kein Zähler, der Einspeisung gegenrechnet. Die Zustandsklasse muss `total` oder `total_increasing` sein.

## 1. Installieren

Erstelle zuerst ein Home-Assistant-Backup.

**Mit HACS:**

1. In HACS über **⋮ → Benutzerdefinierte Repositorys** dieses Repository hinzufügen: `https://github.com/Mario084/ha-grid-peak-monitor` · Kategorie **Integration**.
2. **Grid Peak Monitor** öffnen. Vorabversionen/Beta-Versionen anzeigen lassen und **0.1.0-alpha.7** herunterladen. Je nach HACS-Version liegt die Auswahl unter **Herunterladen** oder **Erneut herunterladen**.
3. Home Assistant neu starten.

[Direkt in HACS hinzufügen](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mario084&repository=ha-grid-peak-monitor&category=integration)

**Ohne HACS:** Das [Installations-ZIP der Alpha 7](https://github.com/Mario084/ha-grid-peak-monitor/releases/download/v0.1.0-alpha.7/grid-peak-monitor-0.1.0-alpha.7-install.zip) entpacken. Den enthaltenen Ordner `custom_components/grid_peak_monitor` in den HA-Konfigurationsordner kopieren, normalerweise `/config`. Am Ende muss dort `custom_components/grid_peak_monitor/manifest.json` liegen. Danach Home Assistant neu starten.

Bei einem Update nur den bisherigen Komponentenordner ersetzen und die bestehende Integration weiterverwenden. Nicht löschen und neu anlegen.

## 2. Einrichten

**Einstellungen → Geräte & Dienste → Integration hinzufügen → Grid Peak Monitor**.

Die beiden Sensoren auswählen. Danach die **Bezugsrichtung** bestätigen: Zeigt dein Leistungssensor bei tatsächlichem Netzbezug einen positiven oder negativen Wert? PV und Akku können einspeisen – deshalb bei eindeutigem Netzbezug prüfen.

Als **persönliches Ziel** deinen gewünschten Viertelstunden-Durchschnitt in kW eintragen. Das ist eine Anzeigegrenze, keine Gerätesteuerung.

Unter **Erweitert** nur bekannte Werte einstellen: Das maximale Meldealter steht zunächst auf **120 Sekunden**. Bei einem Energiezähler, der beispielsweise in **0,01 kWh / 10 Wh** zählt und nur bei Änderung meldet, die bekannte Auflösung **0,01 kWh** eintragen. **0** bedeutet unbekannt und prüft das Energie-Meldealter streng. Auflösung und Meldetakt nicht raten.

## 3. Anschauen

Links in der Seitenleiste **Netzspitzen** öffnen. Falls der Eintrag fehlt, die HA-Seite neu laden. Ein eigenes Dashboard musst du nicht bauen.

Bis zum ersten abgeschlossenen Wert kann es knapp 30 Minuten dauern: zunächst beginnt eine neue Viertelstunde, dann wird sie vollständig gemessen. Striche bedeuten fehlende verlässliche Daten, nicht null Verbrauch. Das Ziel lässt sich direkt unter **Persönliches Ziel → Ziel ändern** anpassen.

## Sensoren später ändern

**Einstellungen → Geräte & Dienste → Grid Peak Monitor → beim gewünschten Integrationseintrag ⋮ → Neu konfigurieren**.

Neue Sensoren auswählen und im nächsten Schritt Bezugsrichtung sowie gegebenenfalls Zählerauflösung prüfen. Erst mit dem abschließenden Speichern wird gewechselt. Die Monitor-Entitäten und dein Ziel bleiben erhalten.

Mit neuen Messquellen beginnen der lokale Verlauf und die Monatsspitze neu. Der bisherige Verlauf wird vorher lokal gesichert und nicht mit den neuen Messwerten vermischt. Eine Wiederherstellung dieser Sicherung über die Oberfläche gibt es noch nicht. Bei unveränderten Sensoren oder Abbrechen bleibt der Verlauf bestehen.

Ziel, Meldealter und Auflösung kannst du weiterhin über **Konfigurieren** ändern.

## Kurze Rückmeldung nach dem Test

Lass ihn ein bis zwei Tage mitlaufen. Interessant sind: War die Einrichtung verständlich? Passen die ausgewählten Sensoren und angezeigten Werte? Funktioniert der Quellenwechsel? Gibt es unerklärliche Striche oder Fehler? Bitte HA-Version und Zählermodell dazuschreiben.

[Ausführliche Testerchecks](TESTER.md) · [Probleme melden](https://github.com/Mario084/ha-grid-peak-monitor/issues/new/choose)
