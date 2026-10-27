# Nächster Test: Synology DS916

Stand: Die HA-Testinstanz auf der DS916 ist ausgeschaltet. Es wurde keine Verbindung hergestellt und dort nichts installiert. Die produktive HA-Instanz bleibt außerhalb dieses Tests.

## Vorbereiten

1. Die vorhandene **Testinstanz** einschalten und deren URL identifizieren.
2. Backup dieser Testinstanz erstellen und HA-Version prüfen. Für diese Alpha wurde 2026.10.2 getestet. Eine bestehende Instanz nicht nur für dieses Paket ungeprüft aktualisieren.
3. Nur dort das Installations-ZIP nach README installieren.
4. Zwei passende Test-Entitäten auswählen. Wenn echte Zählerberichte bereits lesend in der Testinstanz ankommen, deren Bezugsrichtung, Einheiten und Berichtsintervall prüfen. Keine neue Verbindung zur Produktionsinstanz allein für diesen Test einrichten.

## Beobachten und vergleichen

| Prüfung | Erwartung |
| --- | --- |
| Start mitten im Viertel | Zunächst kein vollständiger Peak; keine künstliche Null. |
| Nach vollständigem Viertel | `Δ Bezugsenergie × 4` entspricht dem archivierten Durchschnitt; kleine Abweichung durch interpolierte Grenzen möglich. |
| Zielwert ändern | Number-Entität, Sensorattribute und Karte übernehmen denselben Wert; nach Neustart erhalten. |
| Netzbezug positiv/negativ | Bei korrekter Einstellung bleibt Bezug positiv, Einspeisung ist null Import. |
| Bericht bleibt numerisch gleich | Bei echten wiederholten Berichten weiterhin aktuell; ohne Berichte nach Ablauf als veraltet markiert. |
| Ausfall länger als Meldealter | Datenlücke, keine erfundene Spitze und keine falsche Entwarnung. |
| Neustart im Viertel | Bekannte Basis wird übernommen, eine längere Unterbrechung bleibt erkennbar. |
| Handy und Desktop | Verlauf, Datumswahl, leere Slots und Balkendetails funktionieren. |
| Bestehender Portal-Importer, falls vorhanden | Erst separat aktivieren; Portalviertel blau, lokale Monatswerte separat. |

Mindestens einen vollständigen Tag beobachten, danach einen Neustart und eine kontrollierte Lücke prüfen. Für belastbare Aussagen über Monatsabdeckung länger laufen lassen. Sommerzeit wurde bisher synthetisch getestet, nicht auf der DS916 beobachtet.

Falls keine passenden Zählerquellen vorhanden sind, zuerst mit zwei synthetischen Entitäten in dieser Testinstanz arbeiten. Keinen Generator auf reale Zähler-Entity-IDs schreiben und keine Lasten für Tests schalten.

## Vor einer Veröffentlichung festhalten

HA-Version, tatsächliche Quell-Einheiten und Meldeintervalle, Intervallabweichungen, Verhalten bei Neustart/Lücken und Browser festhalten. Für weitergegebene Logs und Screenshots private Entity-Namen und Messwerte anonymisieren. Testinstallation bei Bedarf über README wieder entfernen.
