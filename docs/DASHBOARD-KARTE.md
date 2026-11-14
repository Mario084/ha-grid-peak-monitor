# Optionale Karte im eigenen Dashboard

Die automatisch registrierte **Netzspitzen-Seite** benötigt diese Schritte nicht. Wer dieselbe Darstellung zusätzlich im eigenen Dashboard möchte, kann die vorhandene Karte weiterverwenden.

1. Benutzerprofil → **Erweiterter Modus**. **Einstellungen → Dashboards → ⋮ → Ressourcen** öffnen.
2. Ressource **`/grid_peak_monitor_static/grid-peak-card.js?v=0.1.0-alpha.7`** als **JavaScript-Modul** eintragen. Vorhandenen Eintrag aktualisieren statt duplizieren.
3. Browser neu laden. Dashboard bearbeiten → Karte hinzufügen → **Grid Peak Monitor**. Den Prognose-Sensor des gewünschten Monitors wählen.

Bei YAML-verwalteten Ressourcen den Eintrag in der vorhandenen Ressourcenliste aktualisieren; keinen zweiten Konfigurationsblock anlegen. Bei Updates die Versionskennung mit der installierten Integration abgleichen.

```yaml
type: custom:grid-peak-card
entity: sensor.beispiel_prognose # tatsächliche Prognose-Entity-ID wählen
view: overview
```

Beide Ansichten verwenden denselben Renderer. Beim eigenen Panel ist keine Ressourcen-URL von Hand zu pflegen. Die Installation der Integration durch HACS trägt die optionale Dashboardressource nicht automatisch ein.

## Optionaler Portalanschluss

Für normale Installationen zuerst [Netzbetreiberdaten ergänzen](NETZBETREIBERDATEN.md) lesen. Die folgenden Optionen gelten ausschließlich für die eigene Dashboard-Karte, wenn ein passender separater Adapter bereits vorhanden ist. Die automatische Netzspitzen-Seite bietet diese Optionen in Alpha 7 nicht an.

```yaml
type: custom:grid-peak-card
entity: sensor.beispiel_prognose # tatsächliche Prognose-Entity-ID wählen
portal_history: true
# Optional: vorhandene, unabhängig ermittelte Portal-Monatsspitze in kW
# portal_peak: sensor.beispiel_portal_monatsspitze
```

`portal_history` ruft den authentifizierten HA-WebSocket-Befehl `netznoe_quarter_audit/history` mit `date` und `month` auf. Erwartet wird `day.quarters`: Einträge mit `utc` (ISO-Zeitstempel mit Zeitzone am Intervallanfang) oder `start` (Unix-Sekunden) sowie `kw` (nichtnegative mittlere Bezugsleistung der Viertelstunde). Die Karte übernimmt Werte auf passenden 900-Sekunden-Grenzen für den ausgewählten Tag.

Der dafür benötigte Adapter `netznoe_quarter_audit` ist **nicht Teil dieses Projekts**. Eine andere Netz-NÖ-Integration oder eine HA-Energiestatistik erfüllt diesen Vertrag nicht automatisch. Ohne passenden Adapter die Option weglassen; ein nicht verfügbarer Adapter blockiert den lokalen Verlauf nicht.

Portalwerte ersetzen nur in der Tagesgrafik das zugehörige UTC-Intervall und werden blau markiert. Das lokale Archiv, die lokalen Top-Intervalle und Tagesmaxima bleiben HA-Schätzungen. `portal_peak` zeigt einen bereits vorhandenen Monatsspitzen-Sensor separat an; die Karte berechnet daraus keinen Portal-Monatsnachweis. Der echte Portal-Abgleich ist noch nicht Ende zu Ende geprüft.
