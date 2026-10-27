# Grid Peak Monitor ausprobieren

Danke fürs Testen. Diese Version ist eine **Alpha für einen kleinen Testkreis**. Wir wollen herausfinden, ob Einrichtung, Sensorwahl und Viertelstundenwerte auch mit anderen Zählern verständlich und verlässlich funktionieren.

## Einrichtung

Zuerst den [Schnellstart mit vier Schritten](SCHNELLSTART.md) verwenden. Die folgenden Punkte sind zusätzliche Alphatests nach der Einrichtung, keine weiteren Installationsschritte.

## Anhang A · Zusätzliche Testerchecks

- Die erste vollständige Viertelstunde abwarten. Ein Strich bedeutet fehlende belastbare Daten, nicht null Netzbezug.
- Bei bekanntem Netzbezug das Vorzeichen prüfen: Der Bezug in der Karte muss positiv sein. Bei Einspeisung ist der Bezug null; negative Leistung wird nicht als negative Bezugsenergie verrechnet.
- Bei PV/Hausakku kann der Energiezähler lange unverändert sein. Mit passender Zählerauflösung und frischer Netzleistung muss das plausibel bleiben.
- Zwei bis drei vollständige Intervalle vergleichen. kWh-Differenz zwischen zwei passenden Viertelstundengrenzen × 4 ergibt den Durchschnitt in kW. Werte ohne Messpunkte genau auf der Grenze sind Schätzungen, keine exakten Referenzmessungen.
- Verlauf öffnen: vorhandene Viertel anklicken, Datum wechseln und die Darstellung am Handy ausprobieren. Bei einer echten Datenunterbrechung bleiben betroffene Intervalle unvollständig.
- HA einmal regulär neu starten. Vorhandene verlässliche Intervalle sollen erhalten bleiben. Nach einer Unterbrechung muss die Beobachtung neu anlaufen; alte Lücken werden nicht aufgefüllt.

Bitte keine Hardwareverbindungen für einen Ausfalltest trennen. Solche Fehler werden zusätzlich mit künstlichen Quellen geprüft. Wer einen eigenen simulierten Sensor hat, kann `unavailable` und einen eingefrorenen Importzähler dort testen.

## Anhang B · Rückmeldung

Bitte nach ein bis zwei Tagen zurückmelden:

- HA-Version, Grid-Peak-Version, Installationsart und Browser.
- Zählermodell, Einheiten, Vorzeichen, bekannte Auflösung, gewähltes Meldealter und ungefährer Meldetakt.
- War die Einrichtung ohne Hilfe verständlich? Waren die richtigen Quellen leicht zu finden?
- Passen aktuelle Werte und zwei bis drei abgeschlossene Viertel? Bitte Uhrzeit und Zeitzone angeben.
- Gab es unerklärliche Striche, Stillstandsalarme, fehlende Intervalle oder Darstellungsfehler?

Dafür die Issue-Vorlage im privaten Repository verwenden, sofern du Zugriff hast, oder die Rückmeldung direkt an Daheim im Detail geben. Screenshots und Logausschnitte vorher bereinigen. Keine Tokens, Passwörter oder kompletten Konfigurationen weitergeben.

## Anhang C · Update und Rückbau

Vor einem Update sichern. Mit HACS die gewünschte geprüfte Version herunterladen oder den Komponentenordner manuell ersetzen; HA neu starten. Bestehende Integration weiterverwenden, nicht neu anlegen. Die eigene Netzspitzen-Seite lädt ihr Modul mit der neuen Version. Nur bei einer zusätzlich verwendeten Dashboardkarte die Versionskennung der Kartenressource aktualisieren und den Browser neu laden. Vor einem Rückwechsel auch den zugehörigen eigenen Archivspeicher sichern; das neue Speicherformat lässt sich nicht durch einen bloßen Datei-Rollback fachlich zurücksetzen.

**Update von Alpha 3:** Deren grob geschätzte Archivwerte konnten inkonsistente Grenzen enthalten. Sie werden als nicht verlässlich markiert und nicht für die Monatsspitze verwendet. Der alte Praxistest wird dadurch nicht nachträglich als bestanden bewertet. Neue saubere Beobachtungen beginnen nach dem Update.

Zum Entfernen Integration über Geräte & Dienste löschen. Nach Entfernen des letzten geladenen Monitors verschwindet der Sidebar-Link automatisch; bei mehreren Monitoren bleibt er erhalten. Optionale Dashboardkarten und deren Ressource separat entfernen, danach Komponentenordner entfernen und HA neu starten. Hinweise zum eigenen zurückbleibenden Archiv stehen in [Architektur](ARCHITEKTUR.md).

## Bekannte Grenzen

Geprüfte HA-Version: **2026.10.2**. Andere Versionen, die DS916 und der optionale Netz-NÖ-Abgleich sind noch nicht freigegeben. Die korrigierte Fassung wurde mit einem Replay und isolierten Laufzeittests geprüft; ein neuer mehrtägiger Live-Test dieser Fassung steht noch aus. Es gibt keine automatische Gerätesteuerung. Die Ergebnisse ersetzen weder Netzbetreiberwerte noch eine Abrechnung.

Privates Testen erfolgt per ZIP. Private GitHub-Repositorys lassen sich [laut HACS](https://www.hacs.xyz/docs/faq/private_repositories/) nicht über HACS installieren.


## Ziel direkt in der Karte ändern

Unter **Persönliches Ziel → Ziel ändern** den gewünschten Wert in kW eingeben, beispielsweise `9,5`, und **Speichern** wählen. Abbrechen verwirft die Eingabe. Die Karte speichert den bestehenden Integrationswert dauerhaft; Budget und Warnstatus werden neu berechnet. Bei Updates Karte und Integration gemeinsam aktualisieren und die neue Versionskennung der Kartenressource verwenden.

## Hilfe zur eigenen Seite

- **Sidebar-Link fehlt:** Installation, regulären Neustart und Status der Integration unter Geräte & Dienste prüfen. HA-Seite neu laden. Bei deaktivierten/entladenen Monitoren wird kein Link angeboten.
- **Falscher Monitor:** Oben den passenden Monitor wählen. Die Auswahl bleibt beim Neuladen in derselben Browsersitzung erhalten.
- **Monitore nicht ladbar:** Verbindung und HA-Berechtigung prüfen; „Erneut versuchen“ wählen. Keine Tokens eintragen.
- **Werte fehlen:** Erste volle Viertelstunde, Quellzuordnung, Vorzeichen, tatsächlichen Meldetakt und bekannte Auflösung prüfen. Fehlende Werte nicht durch blindes Erhöhen des Meldealters verstecken.
- **Optionale Karte fehlt:** Ressource und Versionskennung gemäß [Kartenanleitung](DASHBOARD-KARTE.md) prüfen.
