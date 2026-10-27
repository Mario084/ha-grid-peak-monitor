"""Build reproducible local install/source archives from an explicit allowlist."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "grid_peak_monitor"
VERSION = json.loads((ROOT / f"custom_components/{DOMAIN}/manifest.json").read_text())["version"]
TEXT = {".py", ".js", ".mjs", ".json", ".md", ".svg", ".yml", ".yaml"}
ALLOWED = TEXT | {".png", ".html"}


def paths(directory):
    return sorted(p for p in (ROOT/directory).rglob("*")
                  if p.is_file() and p.suffix in ALLOWED and "__pycache__" not in p.parts and not p.name.startswith("._"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(destination, files, prefix=""):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for file in sorted(files):
            item = zipfile.ZipInfo(prefix + file.relative_to(ROOT).as_posix(), date_time=(2026,1,1,0,0,0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            bundle.writestr(item, file.read_bytes())
    with zipfile.ZipFile(destination) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.namelist()) == len(files)
    return {"file": destination.name, "sha256": digest(destination.read_bytes()), "bytes": destination.stat().st_size}


def main():
    common = [ROOT/"README.md", ROOT/"RELEASE_NOTES.md", ROOT/"LICENSE", ROOT/"hacs.json", *paths("docs")]
    install = common + paths(f"custom_components/{DOMAIN}")
    source = install + paths("demo") + paths("tests") + paths("scripts") + paths(".github") + [ROOT/"package.json", ROOT/".gitignore", ROOT/".github/CODEOWNERS"]
    assert len(source) == len(set(source)), "duplicate source paths"
    for file in source:
        assert not file.is_symlink(), f"symlink disallowed: {file}"
        if file.suffix in TEXT | {".html"} or file.name in {"LICENSE", ".gitignore"}:
            text = file.read_text()
            assert not re.search(r"/(?:Users|home)/[^\s/]+/|192\.168\.|\b10\.\d+\.\d+\.\d+\b|-{5}BEGIN [^-]*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,}", text), f"private content: {file.relative_to(ROOT)}"
            assert not re.search(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b", text), f"JWT disallowed: {file.relative_to(ROOT)}"
    destination = ROOT/"dist"/VERSION
    destination.mkdir(parents=True, exist_ok=True)
    archives = [archive(destination/f"grid-peak-monitor-{VERSION}-install.zip", install),
                archive(destination/f"grid-peak-monitor-{VERSION}-source.zip", source, "grid-peak-monitor/"),
                archive(destination/f"grid-peak-monitor-{VERSION}-github.zip", source)]
    export = ROOT/"output"/("github-ready-"+VERSION.split("-")[-1].replace(".", ""))
    export.mkdir(parents=True, exist_ok=True)
    allowed = {file.relative_to(ROOT).as_posix() for file in source}
    unexpected = [file for file in export.rglob("*") if file.is_file() and file.relative_to(export).as_posix() not in allowed]
    assert not unexpected, "export contains unexpected files; inspect before rebuilding"
    for file in source:
        target = export/file.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    result = {"version": VERSION, "archives": archives,
              "install_files": len(install), "source_files": len(source),
              "source_manifest": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(source)}}
    (destination/"manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    (destination/"SHA256SUMS.txt").write_text("".join(f"{a['sha256']}  {a['file']}\n" for a in archives))
    print(json.dumps({k:v for k,v in result.items() if k!="source_manifest"}, indent=2))


if __name__ == "__main__":
    main()
