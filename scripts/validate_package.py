"""Offline structural checks, not a claim of a public HACS installation."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/grid_peak_monitor"


def main():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    version = manifest["version"]
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["name"] == manifest["name"]
    assert hacs["homeassistant"] == "2026.10.2"
    assert not hacs.get("content_in_root", False)
    assert not hacs.get("zip_release", False), "HACS uses component tree, not manual install ZIP"
    assert [p.name for p in (ROOT / "custom_components").iterdir() if p.is_dir() and p.name != "__pycache__"] == ["grid_peak_monitor"]
    assert {"frontend", "panel_custom", "http", "websocket_api"} <= set(manifest["dependencies"])
    assert manifest["documentation"] == "https://github.com/Mario084/ha-grid-peak-monitor"
    assert (COMPONENT / "brand/icon.png").read_bytes().startswith(b"\x89PNG")
    assert json.loads((ROOT / "package.json").read_text())["version"] == version
    assert f'VERSION = "{version}"' in (COMPONENT / "const.py").read_text()
    assert f"grid-peak-card.js?v={version}" in (COMPONENT / "frontend/grid-peak-panel.js").read_text()
    english = json.loads((COMPONENT / "strings.json").read_text())
    assert english == json.loads((COMPONENT / "translations/en.json").read_text())
    for language in ("en", "de"):
        strings = json.loads((COMPONENT / f"translations/{language}.json").read_text())
        assert set(strings["config"]["step"]) == {"user", "settings"}
        assert "advanced" in strings["config"]["step"]["settings"]["sections"]
        assert set(strings["selector"]["import_sign"]["options"]) == {"choose", "positive", "negative"}
    dist = ROOT / "dist" / version
    report = json.loads((dist / "manifest.json").read_text())
    for archive in report["archives"]:
        path = dist / archive["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == archive["sha256"]
        with zipfile.ZipFile(path) as bundle:
            assert bundle.testzip() is None
            assert len(bundle.namelist()) == len(set(bundle.namelist()))
            for name in bundle.namelist():
                assert not name.startswith("/") and ".." not in Path(name).parts
                assert not any(part in {"output", "private", "privateoutput", ".storage", ".env", "__pycache__"} or part.startswith("._") for part in Path(name).parts), name
                assert "live-source.json" not in name and "ui-auth.json" not in name
            if "install.zip" in path.name:
                assert "custom_components/grid_peak_monitor/frontend/grid-peak-panel.js" in bundle.namelist()
                assert "custom_components/grid_peak_monitor/panel.py" in bundle.namelist()
                assert not any(name.startswith("tests/") for name in bundle.namelist())
    print(json.dumps({"version": version, "repository_structure": True, "manifest_hacs": True, "brand": True,
                      "translations": True, "panel_packaged": True, "archive_hashes": True,
                      "private_paths_excluded": True, "public_hacs_validation": "not run", "real_hacs_install": "not run"}))


if __name__ == "__main__":
    main()
