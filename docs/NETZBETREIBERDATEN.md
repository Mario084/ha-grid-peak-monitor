# Netzbetreiberdaten und Live-Werte zusammen nutzen

**Stand: 14. November 2026 · Grid Peak Monitor 0.1.0-alpha.7**

Die Live-Werte zeigen, was gerade passiert und welche Viertelstundenspitze droht. Die später bereitgestellten Netzbetreiberwerte ergänzen den Rückblick und ermöglichen den Vergleich mit der lokalen Schätzung. Für beide Quellen sollte derselbe Netzanschluss und dieselbe Bezugsrichtung betrachtet werden.

## Welche Möglichkeiten gibt es?

| Weg | Wofür geeignet? | Was wird benötigt? |
| --- | --- | --- |
| Portal-Integration des Netzbetreibers | Bereits veröffentlichte Verbrauchsdaten automatisch nach HA übernehmen. | Portalzugang und eine passende HA-Integration. Verzögerung und Datenauflösung hängen vom Anbieter ab. |
| Dateiimport, falls der Betreiber CSV/Excel anbietet | Ältere Messwerte auswerten und vergleichen. | Exportdatei und ein Importer für genau dieses Format; Grid Peak Monitor enthält keinen Dateiimport. |
| Lokale Kundenschnittstelle am Smart Meter | Aktuelle Netzleistung und Zählerstände unmittelbar am Netzanschluss lesen. | Freigeschaltete Schnittstelle und ein zum Zählermodell passender Leser mit HA-Anbindung. |

Auch der vorhandene Anlagenzähler kann die Live-Quellen liefern: Er muss den gesamten **Netzbezug** messen. PV-Ertrag, Akkuentladung und Hausverbrauch sind andere Größen. Die [HA-Dokumentation](https://www.home-assistant.io/docs/energy/electricity-grid/) erklärt die unterschiedlichen Messwege.

## Netz NÖ: zuerst das Portal vorbereiten

1. Das [Smart Meter Portal](https://smartmeter.netz-noe.at/) öffnen und anmelden oder registrieren. Netz-NÖ-Kundennummer und Zählpunktbezeichnung bereithalten; diese stehen auf den Netzunterlagen. Der Zählpunkt ist nicht die Seriennummer auf dem Zähler. [Registrierungsangaben von Netz NÖ](https://netz-noe.at/getContentAsset/09c13cb8-5e9a-42d5-9467-4119a6d5736a/0ee16eb8-9692-4f25-b8a4-d007b35915a4/Nutzungsbedingungen_SmartMeterWebportal_20210930.pdf?language=de).
2. Den richtigen **Bezugszählpunkt** wählen und prüfen, ob Viertelstundenwerte angezeigt werden. Falls nötig, die Viertelstunden-Auslesung/Opt-In im Portal aktivieren. Netz NÖ beschreibt inzwischen auch eine automatische Umstellung; deshalb zuerst den tatsächlichen Status prüfen. [Portal](https://netz-noe.at/services/smart-meter-portal) · [FAQ](https://netz-noe.at/wissen/faq).
3. Einen abgeschlossenen Tag prüfen. Ein 15-Minuten-Messraster bedeutet keine Live-Übertragung. Netz NÖ beschreibt eine tägliche Übermittlung; neueste oder fehlende Werte können später eintreffen. [Zählerbeschreibung](https://netz-noe.at/getContentAsset/e1f4a70e-e7f2-4b8e-a14a-44609a712688/0ee16eb8-9692-4f25-b8a4-d007b35915a4/218_10_SmartMeter_Kaifa-Drehstrom.pdf?language=de).

## Netz NÖ in Home Assistant einbinden

Ein konkreter Einstieg ist die externe Community-Integration **[Netz NÖ Smart Meter von phiilu](https://github.com/phiilu/netz-noe-smartmeter)**. Für diese Anleitung wurden Dokumentation und Statistik-Code von **v0.3.1** geprüft. Eine Installation mit echtem Portalzugang wurde im Rahmen von Grid Peak Monitor noch nicht getestet. Sie ist kein offizielles Netz-NÖ-Produkt.

1. HA-Backup erstellen. In HACS unter **⋮ → Benutzerdefinierte Repositorys** `https://github.com/phiilu/netz-noe-smartmeter` als **Integration** hinzufügen. [HACS-Anleitung](https://www.hacs.xyz/docs/faq/custom_repositories/).
2. **Netz NÖ Smart Meter** herunterladen und Home Assistant neu starten. Das Projekt nennt HA **2025.12.0** als Mindestversion; vor Installation die aktuellen Versionshinweise prüfen.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Netz NÖ Smart Meter**. Portal-Benutzername, Passwort und den 33-stelligen Zählpunkt mit `AT` am Anfang dort eingeben.
4. Den ersten Abruf abwarten und den Datenstand kontrollieren. Die Integration fragt laut Projektdokumentation alle sechs Stunden ab.
5. Unter **Einstellungen → Dashboards → Energie** beim Netzbezug die importierte Statistik des Zählpunkts wählen: `netz_noe_smartmeter:<zählpunkt in kleinbuchstaben>`. Sie ist eine Statistik, keine normale Sensor-Entity-ID. Ältere Installationen können `netz_noe_smartmeter:grid_consumption` verwenden. Die Tagesverbrauchs-Entität ist dafür nicht die vorgesehene Quelle.

Anschließend die Energiemenge eines vollständig vorliegenden Tages mit dem Portal vergleichen. Einspeisung gegebenenfalls separat zuordnen. **Denselben Netzbezug nicht gleichzeitig aus Anlagenzähler und Portal als zwei Netzbezüge im Energie-Dashboard addieren.** Grid Peak Monitor darf parallel seine Live-Sensoren weiterverwenden.

Historische Daten lassen sich über die externe Aktion `netz_noe_smartmeter.backfill_statistics` nachladen. Zuvor deren [Dokumentation](https://github.com/phiilu/netz-noe-smartmeter/tree/v0.3.1#backfill-historical-data) lesen: Der Vorgang baut die betroffene importierte Statistik neu auf; er ist für die erste Funktionsprüfung nicht nötig.

## Was davon erscheint bereits im Grid Peak Monitor?

**Mit Alpha 7 sind die beiden Ansichten zunächst getrennt:** Live-Prognose und lokaler Viertelstundenverlauf im Grid Peak Monitor; importierte Netzbetreiberenergie im HA-Energie-Dashboard.

Die oben beschriebene Integration fasst ihre Viertelstundenwerte zu **Stundenstatistiken** zusammen ([Implementierung v0.3.1](https://github.com/phiilu/netz-noe-smartmeter/blob/v0.3.1/custom_components/netz_noe_smartmeter/statistics.py)). Daraus lässt sich die höchste Viertelstunde nicht zurückrechnen. Beispiel: 1 kWh in einer Stunde kann gleichmäßig verteilt sein oder vollständig in einer Viertelstunde anfallen; die Viertelstundenleistung wäre dann 1 beziehungsweise 4 kW.

Für die gemeinsame Spitzengrafik brauchen wir die **ursprünglichen Viertelstundenwerte** mit eindeutigen Zeitstempeln und Einheiten. Bei Energie je Viertelstunde gilt `kW = kWh × 4`; vorhandene kW-Werte werden nicht nochmals multipliziert. Intervallanfang/-ende, Sommerzeit, Bezug/Einspeisung und fehlende Werte müssen korrekt zugeordnet werden.

Die optionale Dashboard-Karte hat dafür bereits den Anschluss `portal_history` an einen separaten Adapter namens `netznoe_quarter_audit`. Dieser Adapter wird **nicht mitgeliefert**. Die oben genannte Community-Integration stellt diesen Anschluss nicht bereit; ihre Installation allein aktiviert daher keine blauen Portalbalken. Die automatische Netzspitzen-Seite hat in Alpha 7 keine Portal-Konfiguration. Ein öffentlich installierbarer, Ende zu Ende geprüfter Viertelstunden-Import für die gemeinsame Grafik steht noch aus. [Details zur optionalen Karte](DASHBOARD-KARTE.md).

**Verzögerte Portal-Tageswerte nie als Live-Energiequelle des Monitors auswählen.** Dafür bleiben die regelmäßig aktualisierte Netzleistung und der fortlaufende Bezugszähler der Anlage beziehungsweise eines lokalen Zählerlesers zuständig.

## Optional: Live-Werte direkt vom Netz-NÖ-Zähler

Wer noch keine passenden Anlagenwerte hat, kann die [Kundenschnittstelle aktivieren lassen](https://netz-noe.at/services/kundenschnittstelle-aktivieren). Netz NÖ verlangt unter anderem Kundennummer und Vertragskonto und stellt einen Schlüsselcode bereit. Der Leser muss zum konkreten Zählermodell passen: Netz NÖ beschreibt verschlüsseltes DLMS/COSEM über eine verdrahtete M-Bus-Schnittstelle am P1-Port, mit Ausgabe alle fünf Sekunden. Die Bezeichnung „P1“ allein garantiert keine Kompatibilität mit einem beliebigen Leser. [Offizielle Schnittstellenbeschreibung](https://netz-noe.at/getContentAsset/568bef9a-3bd1-4f2e-a710-6ba7e71cb746/0ee16eb8-9692-4f25-b8a4-d007b35915a4/218_20_SM_Kundenschnittstelle_WCAG.pdf?language=de).

Den passenden Leser nach dessen Anleitung in HA einbinden und anschließend seine Netzleistung und kumulierte Bezugsenergie im Monitor auswählen. Bei bereits funktionierenden Live-Sensoren ist zusätzliche Hardware für den Portalimport nicht erforderlich.

[Zurück zum Schnellstart](SCHNELLSTART.md)
