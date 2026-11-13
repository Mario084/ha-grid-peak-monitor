# Eigenständiges Repository und weitere Testreleases

Ziel ist ausschließlich `Mario084/ha-grid-peak-monitor`, Maintainer `@Mario084`. Das private Website-Repository ist kein Veröffentlichungsziel. Dieses Repository enthält nur den bereinigten Grid-Peak-Monitor-Export und beginnt mit einer unabhängigen Git-History.

## Weitere Testreleases

1. Das GitHub-Quellpaket entpacken und seinen **Inhalt direkt in die Repository-Wurzel** übernehmen. Dort müssen `hacs.json`, `README.md`, `.github/` und `custom_components/` liegen. Alternativ die entsprechende saubere lokale Exportkopie verwenden. Niemals das gesamte Arbeitsverzeichnis hochladen.
2. Für HACS muss das eigenständige Monitor-Repository öffentlich zugänglich sein; andere private Repositorys bleiben unverändert. Keine produktiven HA-Daten, `output/`, `.storage`, Token-Dateien oder lokalen Logs übertragen.
3. Beschreibung setzen: „Netzbezug und Viertelstunden-Lastspitzen in Home Assistant beobachten – mit eigener Dashboard-Karte.“ Issues aktivieren. Themen: `home-assistant`, `hacs`, `energy`, `peak-power`.
4. GitHub-Actions-Prüfungen abwarten. Python-, JavaScript-, Paket- und HA-Laufzeittests sowie hassfest sind vorbereitet. Die öffentliche HACS-Prüfung läuft erst bei einem öffentlichen Repository. Ein lokal vorhandener Workflow ist noch kein bestätigter GitHub-Prüflauf.
5. Nach erfolgreichen Prüfungen einen **Prerelease-Entwurf** für `v0.1.0-alpha.7` anlegen. [Release-Notizen](../RELEASE_NOTES.md), Installations-ZIP und `SHA256SUMS.txt` verwenden. Ein Alpha-Release ausdrücklich als Prerelease kennzeichnen; keine bestehenden Tags oder Assets überschreiben.
6. Für den privaten Test genügt auch die direkte Weitergabe des Installations-ZIPs mit [Tester-Anleitung](TESTER.md). HACS kann private Repositorys nicht verwenden.
7. Rückmeldungen über die vorbereitete Issue-Vorlage erfassen. Nach den Tests Fehler beheben, neue Version prüfen und erst dann ein stabiles Release entscheiden.

## Später öffentlich/HACS

- hassfest und HACS-Action mit dem tatsächlichen öffentlichen Repository erfolgreich ausführen; Beschreibung, Topics, Issues und lokale Branddateien kontrollieren.
- Erst als benutzerdefiniertes HACS-Repository erproben. Die Aufnahme in den Standardkatalog ist ein eigener späterer Schritt gemäß [HACS](https://www.hacs.xyz/docs/publish/include/).
- Weitere HA-Versionen, andere Zähler und den DS916-Lauf dokumentieren. Den Portalabgleich experimentell lassen, bis er Ende zu Ende geprüft ist.
- Buy-me-a-coffee erst nach Einrichtung eines echten Profils verlinken. Aktuell existiert kein Zahlungslink.

Der Maintainer-Account und die URLs sind eingetragen. Der Zugriffsweg des verwendeten GitHub-Werkzeugs muss das private Repository ebenfalls sehen können, bevor Dateien darüber übertragen werden können. Das öffentliche Release wird nicht durch diese Vorbereitung ausgelöst.

## Lokale Alpha6-Artefakte

`scripts/build_release.py` erzeugt Pakete und Prüfsummen unter `dist/0.1.0-alpha.7/` und den bereinigten Export unter `output/github-ready-alpha6/`. Vorhandene Alpha5-Pakete werden nicht verändert. Niemals das gesamte Arbeitsverzeichnis einschließlich `output/` hochladen. Die lokale Strukturprüfung ersetzt keine öffentliche HACS-Action und keinen echten HACS-Installationsversuch.


## Automatisches Alpha-Release nach erfolgreicher Prüfung

Der Workflow `Publish tested alpha` veröffentlicht ausschließlich nach einem erfolgreichen `Validate`-Push-Lauf auf `main`, wenn die erste Commitzeile exakt `Release Grid Peak Monitor <Version>` lautet und die Version im Manifest dem Format `X.Y.Z-alpha.N` entspricht. Normale Änderungen und Pull-Request-Prüfläufe veröffentlichen nichts. Der geprüfte Commit muss weiterhin der aktuelle `main`-Stand sein.

Der Workflow baut aus genau diesem Commit die Pakete, prüft sie erneut und legt Tag, Prerelease und Anhänge an. Bereits vorhandene Releases und Assets werden nicht überschrieben. Stabile Releases entstehen auf diesem Weg nicht. Der benötigte Schreibzugriff ist auf den Release-Job begrenzt; es werden keine dauerhaften Zugangsdaten hinterlegt.
