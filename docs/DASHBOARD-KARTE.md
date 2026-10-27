# Optionale Karte im eigenen Dashboard

Die automatisch registrierte **Netzspitzen-Seite** benötigt diese Schritte nicht. Wer dieselbe Darstellung zusätzlich im eigenen Dashboard möchte, kann die vorhandene Karte weiterverwenden.

1. Benutzerprofil → **Erweiterter Modus**. **Einstellungen → Dashboards → ⋮ → Ressourcen** öffnen.
2. Ressource **`/grid_peak_monitor_static/grid-peak-card.js?v=0.1.0-alpha.6`** als **JavaScript-Modul** eintragen. Vorhandenen Eintrag aktualisieren statt duplizieren.
3. Browser neu laden. Dashboard bearbeiten → Karte hinzufügen → **Grid Peak Monitor**. Den Prognose-Sensor des gewünschten Monitors wählen.

Bei YAML-verwalteten Ressourcen den Eintrag in der vorhandenen Ressourcenliste aktualisieren; keinen zweiten Konfigurationsblock anlegen. Bei Updates die Versionskennung mit der installierten Integration abgleichen.

```yaml
type: custom:grid-peak-card
entity: sensor.beispiel_prognose # tatsächliche Prognose-Entity-ID wählen
view: overview
```

Beide Ansichten verwenden denselben Renderer. Beim eigenen Panel ist keine Ressourcen-URL von Hand zu pflegen. Die Installation der Integration durch HACS trägt die optionale Dashboardressource nicht automatisch ein.
