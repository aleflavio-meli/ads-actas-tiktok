#!/usr/bin/env python3
"""
build_index.py — regenera actas/index.html a partir de los archivos en
actas/minutas/ y actas/agendas/.

Uso:
    python build_index.py

Qué hace:
  1. Lee todos los .html en minutas/ y agendas/ (nombre esperado:
     YYYY-MM-DD_slug.html).
  2. Extrae el <title> de cada archivo.
  3. Si ya existe una entrada para ese archivo en el index.html actual,
     conserva sus tags manuales (curados a mano) en vez de perderlos.
  4. Si es un archivo nuevo, lo agrega con tags placeholder — hay que
     editarlos a mano en el index.html generado, o pasar --tag después.
  5. Reescribe actas/index.html completo, ordenado por fecha descendente.

Este script no depende de librerías externas — solo stdlib.
Pensado para correr después de generar una minuta/agenda nueva con el
skill /meeting-organization y copiarla a actas/minutas/ o actas/agendas/.
"""

import re
import json
from pathlib import Path

ACTAS_DIR = Path(__file__).resolve().parent
MINUTAS_DIR = ACTAS_DIR / "minutas"
AGENDAS_DIR = ACTAS_DIR / "agendas"
INDEX_PATH = ACTAS_DIR / "index.html"

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)\.html$")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
ENTRIES_RE = re.compile(r"const ENTRIES = (\[.*?\]);", re.DOTALL)


def load_existing_entries():
    """Lee el ENTRIES actual del index.html (si existe) para no perder tags manuales."""
    if not INDEX_PATH.exists():
        return {}
    text = INDEX_PATH.read_text(encoding="utf-8")
    match = ENTRIES_RE.search(text)
    if not match:
        return {}
    # El array está escrito como JS con comillas dobles y sin trailing commas raras;
    # normalizamos claves sin comillas a JSON válido de forma simple.
    raw = match.group(1)
    raw = re.sub(r"(\w+):", r'"\1":', raw)  # date: -> "date":
    raw = re.sub(r",\s*([\]}])", r"\1", raw)  # elimina trailing commas
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {(e["file"]): e for e in entries}


def extract_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = TITLE_RE.search(text)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return path.stem


def collect(dir_path: Path, entry_type: str, existing: dict, prefix: str):
    entries = []
    if not dir_path.exists():
        return entries
    for path in sorted(dir_path.glob("*.html")):
        m = FILENAME_RE.match(path.name)
        if not m:
            print(f"⚠ Saltando {path.name}: no sigue el patrón YYYY-MM-DD_slug.html")
            continue
        date = m.group(1)
        rel_file = f"{prefix}/{path.name}"
        prior = existing.get(rel_file)
        if prior:
            tags = prior.get("tags", [])
            title = prior.get("title", extract_title(path))
        else:
            tags = ["Sin curar — editar tags"]
            title = extract_title(path)
        entries.append({
            "date": date,
            "type": entry_type,
            "title": title,
            "tags": tags,
            "file": rel_file,
        })
    return entries


def render_entries_js(entries) -> str:
    lines = ["const ENTRIES = ["]
    for e in entries:
        tags_js = ", ".join(json.dumps(t, ensure_ascii=False) for t in e["tags"])
        lines.append(
            '  { date: "%s", type: "%s", title: %s, tags: [%s], file: "%s" },'
            % (e["date"], e["type"], json.dumps(e["title"], ensure_ascii=False), tags_js, e["file"])
        )
    lines.append("];")
    return "\n".join(lines)


def main():
    existing = load_existing_entries()
    entries = collect(MINUTAS_DIR, "minuta", existing, "minutas")
    entries += collect(AGENDAS_DIR, "agenda", existing, "agendas")
    entries.sort(key=lambda e: (e["date"], e["type"]), reverse=True)

    if not INDEX_PATH.exists():
        print("✗ No existe actas/index.html todavía — generá la plantilla base una vez a mano.")
        return

    text = INDEX_PATH.read_text(encoding="utf-8")
    new_js = render_entries_js(entries)
    # lambda como replacement evita que re.sub interprete '\1' etc. dentro de new_js
    new_text = ENTRIES_RE.sub(lambda _: new_js, text, count=1)
    INDEX_PATH.write_text(new_text, encoding="utf-8")

    n_new = sum(1 for e in entries if e["tags"] == ["Sin curar — editar tags"])
    print(f"✓ index.html regenerado con {len(entries)} entradas ({n_new} sin curar).")
    if n_new:
        print("  → Editá los tags de las entradas nuevas directamente en index.html antes de compartir.")


if __name__ == "__main__":
    main()
