# Laufende lokale Vorschau

Die erste netzlose Testinstanz war kurzlebig. Zusätzlich existiert jetzt ein eigener, weiterlaufender Container **`grid-peak-monitor-preview`** mit Home Assistant 2026.10.2 auf Port **8124** des Entwicklungs-Macs.

- Direkte Karte ohne Anmeldung: `http://<mac-mini>:8124/demo/index.html`.
- Vollständiges HA: `http://<mac-mini>:8124/lovelace/0`. Beim ersten Öffnen eigenen Testbenutzer anlegen und die Ersteinrichtung abschließen.
- Die tatsächliche erreichbare Heimnetz-Adresse wurde im Chat übergeben; sie gehört nicht in das weiterzugebende Quellpaket.

Alle Quellen und acht Tage vorbelegter Historie sind **synthetisch**. Zwei erzeugte HA-Sensoren liefern alle fünf Sekunden Netzleistung und fortlaufenden Energieimport an die echte Integration. Die direkte Ansicht verwendet dieselbe Karten-Datei wie das HA-Dashboard und liest dafür nur die künstlichen Demodaten über einen eigenen HTTP-Endpunkt. Sie verwendet keinen HA-Login. Im vollständigen HA läuft die Karte mit der normalen authentifizierten Verbindung.

Das zusätzliche Ziel im Kopf der direkten Vorschau wirkt nur in diesem Browser und zeigt Änderungen sofort. Es verändert nicht die Number-Entität der Testintegration. Diese lässt sich im vollständigen HA separat einstellen und behält ihren normalen Warnstatus mit Verzögerung.

## Dateien und Lebensdauer

- `scripts/ha_preview.py`: Start der separaten HA-Instanz und künstliche Sensorquellen.
- `demo/`: Direkte Browser-Vorschau.
- `output/ha-preview-config/`: Eigene persistente HA-Konfiguration, einschließlich eines später selbst angelegten Testbenutzers. Ignoriert und **niemals Bestandteil der ZIPs**.
- Ein Marker verhindert, dass das Startskript versehentlich einen beliebigen vorhandenen HA-Konfigurationsordner übernimmt.

Der Container läuft weiter, wenn die Unterhaltung endet. Er wird nicht automatisch entfernt. Die Konfiguration überlebt Stoppen/Starten. Nach einem Rechner- oder Docker-Neustart kann der Container bei Bedarf wieder gestartet werden; automatischer Start wurde nicht aktiviert.

Nur diesen eigenen Container bedienen:

```sh
docker stop grid-peak-monitor-preview
docker start grid-peak-monitor-preview
```

Der vorherige netzlose Prüflauf in `tests/ha_runtime.py` bleibt davon getrennt und entfernt seinen Testcontainer weiter automatisch. Keine produktive HA-Konfiguration und keine Geräte sind eingebunden. Die DS916 wurde nicht angesprochen.

## Auf einem anderen Entwicklungsrechner nachbauen

Im entpackten **Quellprojekt**, mit vorhandenem Docker und freiem Port 8124:

```sh
mkdir -p output/ha-preview-config
docker run -d --name grid-peak-monitor-preview --restart no \
  --cap-drop ALL --pids-limit 192 --memory 1g \
  -p 127.0.0.1:8124:8123 \
  --mount "type=bind,source=$PWD,target=/work,readonly" \
  --mount "type=bind,source=$PWD/output/ha-preview-config,target=/config" \
  --entrypoint python \
  ghcr.io/home-assistant/home-assistant:2026.10.2 /work/scripts/ha_preview.py
```

Damit ist die Vorschau auf diesem Rechner unter `http://127.0.0.1:8124/demo/index.html` erreichbar. Für den gewünschten Zugriff im Heimnetz zusätzlich die konkrete LAN-Adresse des Entwicklungsrechners als Port-Bindung eintragen. Einen bereits bestehenden Container dieses Namens zunächst prüfen und weiterverwenden.
