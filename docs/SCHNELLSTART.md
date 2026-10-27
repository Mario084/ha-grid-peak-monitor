# Netzspitzen in vier Schritten

**Grid Peak Monitor 0.1.0-alpha.6 · Home Assistant 2026.10.2**

Du brauchst Administratorzugriff und zwei vorhandene Sensoren: gesamte Netzleistung sowie fortlaufenden Netzimport. Die Integration beobachtet und berechnet; sie steuert keine Geräte. Möglichst zuerst in einer eigenen HA-Testinstanz ausprobieren.

## 1 · Sichern und installieren

Erstelle vor Installation oder Update ein HA-Backup und bewahre eine Kopie samt eventuell benötigtem Notfallpaket außerhalb von HA auf.

**Mit bereits eingerichtetem HACS:** HACS → ⋮ → Benutzerdefinierte Repositorys → `https://github.com/Mario084/ha-grid-peak-monitor` → Kategorie **Integration**. Hinzufügen, Grid Peak Monitor öffnen und die gewünschte Alpha-Version herunterladen. Eine Aufnahme in den Standardkatalog ist dafür nicht nötig. Die Struktur ist lokal geprüft; ein echter HACS-Installationsnachweis steht noch aus. Private Repositorys funktionieren in HACS nicht.

**Ohne HACS / privater Test:** Das **[grid-peak-monitor-0.1.0-alpha.6-install.zip](https://github.com/Mario084/ha-grid-peak-monitor/releases/download/v0.1.0-alpha.6/grid-peak-monitor-0.1.0-alpha.6-install.zip)** aus dem Prerelease entpacken. Nur `custom_components/grid_peak_monitor` in den HA-Konfigurationsordner kopieren; vorhandenen Dateizugriff verwenden. Bei HA OS liegt er üblicherweise unter `/config`. Prüfen:

```text
<HA-Konfigurationsordner>/custom_components/grid_peak_monitor/manifest.json
```

Andere Komponenten bleiben erhalten. Kein zusätzlicher ZIP-/Projektordner im Pfad. Bei einem Update den bisherigen Komponentenordner vollständig durch den neuen ersetzen; eigene Archive liegen außerhalb dieses Ordners.

## 2 · HA neu starten und Integration hinzufügen

Home Assistant regulär neu starten. Danach **Einstellungen → Geräte & Dienste → Integration hinzufügen → Grid Peak Monitor**. Bei einem Update einer bereits eingerichteten Integration diese weiterverwenden; nicht löschen und neu anlegen.

## 3 · Messquellen, Richtung und Ziel bestätigen

Der Assistent fragt zuerst nach zwei Quellen:

- **Gesamte Netzleistung:** W oder kW am gesamten Netzanschluss. Nicht PV-Erzeugung, Hauslast oder nur eine Phase.
- **Fortlaufender Netzimport:** Wh/kWh/MWh, ausschließlich Netzbezug, `total` oder `total_increasing`. Kein regelmäßig zurückgesetzter Tageszähler und keine saldierte Import-/Exportsumme.

Die Vorauswahl grenzt passende Einheiten und Klassen ein; die Bedeutung bestätigst du selbst. Eigene Sensoren ohne Geräteklasse sind mit passenden Metadaten möglich. Fehlende/ungültige Werte werden nicht als null übernommen.

Im zweiten Dialog **Bezugsrichtung bewusst wählen**: bei unabhängig bekanntem tatsächlichem Netzbezug prüfen, ob die Quelle positiv oder negativ meldet. Nicht nur den momentanen Wert betrachten; PV und Akku können einspeisen. **Persönliches Ziel** ist der gewünschte Viertelstunden-Durchschnitt, keine Sicherungs-/Tarifgrenze und kein EVCC-Limit.

**Erweitert** bleibt zunächst eingeklappt: maximales Meldealter standardmäßig **120 Sekunden**; nur passend zum nachgewiesenen Meldetakt ändern. Zählerauflösung **0** bedeutet unbekannt / strenge Energie-Meldefrist, keine geschätzte Auflösung. Nur bekannte Schritte eintragen, etwa **0,01 kWh = 10 Wh**. Bei nur bei Änderung meldenden Importzählern kann die bekannte Auflösung auch bei PV-/Akkubetrieb nötig sein. Nicht raten; im Zweifel vor dem Speichern klären.

## 4 · Netzspitzen öffnen

Nach erfolgreicher Einrichtung erscheint **Netzspitzen** in der HA-Seitenleiste. Falls noch nicht sichtbar, die HA-Seite neu laden. Bei mehreren geladenen Monitoren oben den gewünschten Monitor wählen. Es ist kein manueller Ressourceneintrag und keine Dashboardbearbeitung für diese Seite nötig.

Die erste vollständige Viertelstunde abwarten. Striche bedeuten fehlende belastbare Daten, nicht null Netzbezug. Unter **Persönliches Ziel → Ziel ändern** lässt sich das eigene Ziel speichern. Die Seite schreibt dabei ausschließlich den zugehörigen Number-Wert dieser Integration.

[Optionale Karte fürs eigene Dashboard](DASHBOARD-KARTE.md) · [Testerchecks, Hilfe, Update und Rückbau](TESTER.md)
