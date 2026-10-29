#!/usr/bin/env python3
"""
DI4A website builder
====================

Scans ``content/`` (one sub-folder per theme), builds the catalogue
``data/catalog.json``, copies the publishable documents (``.ipynb``,
``.pdf`` and ``.zip`` only) under descriptive download names ending with ``_AfDB_DI4A``,
renders one static page per theme and assembles the deployable site in
``dist/``.

Typical usage (from the repository root)::

    python scripts/build_site.py                 # build into ./dist
    python scripts/build_site.py --serve         # build, then serve on :8080
    python scripts/build_site.py --update-readme # also refresh README tables
    python -m unittest discover tests            # run the unit tests

The script has a single optional dependency, PyYAML, used to read the
``_meta.yml`` files and ``site.config.yml``.  Without it, metadata files
are ignored and a warning is printed.

Design notes
------------
* The content folder is the single source of truth: no code change is
  needed to add or remove a theme or a document.
* Source files are never modified; renamed *copies* are written to
  ``dist/files/<theme>/``.
* Every step that falls back to a default (missing ``_meta.yml``, missing
  description, ...) emits a warning.  In GitHub Actions these warnings are
  rendered as workflow annotations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

try:  # optional dependency
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parent.parent

# Only these extensions are published; everything else is silently ignored.
PUBLISHED_TYPES = {".ipynb": "lab", ".pdf": "presentation", ".zip": "resource"}
DOC_TYPES = ("lab", "presentation", "resource")

# Language of a published file: "en", "fr", or "both" for a single file that
# holds both languages (typically a ZIP archive).  Order used inside a card.
LANG_ORDER = {"en": 0, "fr": 1, "both": 2}

GENERIC_DESC = {
    "lab": ("Hands-on Jupyter notebook: run it in Google Colab or download it.",
            "Notebook Jupyter pratique : à exécuter dans Google Colab ou à télécharger."),
    "presentation": ("Presentation deck or support document (PDF).",
                     "Présentation ou support de cours (PDF)."),
    "resource": ("Downloadable archive (ZIP): notebooks, code, data or other project files.",
                 "Archive téléchargeable (ZIP) : notebooks, code, données ou autres fichiers du projet."),
}

DEFAULT_CONFIG = {
    "repo": "datainnov4africa-web/DI4A-Website",
    "deploy_branch": "gh-pages",
    "base_url": "",
    "download_suffix": "_AfDB_DI4A",
    "forbidden_terms": [r"ATI\d*", r"(19|20)\d{2}", "Mauritius|Maurice", "Workshop|Atelier"],
    "image_credits": [],
}

LANG_PATTERN = re.compile(r"(?:^|[_\-. ])(EN|FR)(?=$|[_\-. ])", re.IGNORECASE)
EMOJI_PATTERN = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF⭐⬆↔-↪️‍]+"
)


# ---------------------------------------------------------------------------
# Logging helpers (GitHub Actions annotations when available)
# ---------------------------------------------------------------------------
def log(level: str, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true" and level in {"warning", "error", "notice"}:
        print(f"::{level}::{message}")
    else:
        print(f"[{level.upper():7}] {message}")


def info(msg: str) -> None:
    log("info", msg)


def warn(msg: str) -> None:
    log("warning", msg)


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------
def strip_accents(text: str) -> str:
    """Return ``text`` with diacritics removed (é -> e, ç -> c)."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def strip_html(text: str) -> str:
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def clean_markdown(text: str) -> str:
    """Remove emojis, markdown emphasis and links; collapse whitespace."""
    text = EMOJI_PATTERN.sub("", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)        # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)      # links
    text = re.sub(r"[*`~]{1,3}", "", text)                    # emphasis (underscores kept: file names)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -–—:·|")


def slugify(text: str) -> str:
    """Lower-case, ASCII, hyphen-separated identifier (used for theme ids)."""
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "theme"


def title_from_folder(name: str) -> str:
    """``Machine-Learning`` -> ``Machine Learning``; ``NTL`` stays ``NTL``."""
    words = re.split(r"[\s_\-]+", name.strip())
    out = []
    for w in words:
        if not w:
            continue
        out.append(w if w.isupper() and len(w) <= 5 else w[:1].upper() + w[1:])
    return " ".join(out)


def forbidden_regex(terms: list[str]) -> re.Pattern:
    """Compile the forbidden-term list into one whole-token regex."""
    if not terms:
        return re.compile(r"(?!x)x")  # never matches
    joined = "|".join(f"(?:{t})" for t in terms)
    return re.compile(rf"^(?:{joined})$", re.IGNORECASE)


def to_title_case_tokens(text: str) -> list[str]:
    """Split free text into ASCII ``Title_Case`` tokens."""
    text = strip_accents(clean_markdown(strip_html(text.replace("_", " "))))
    text = text.replace("&", " and ").replace("+", " plus ")
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    out = []
    for tok in tokens:
        if tok.isupper() and len(tok) <= 8:  # keep acronyms (RAG, NASA, COICOP, WAEMU)
            out.append(tok)
        elif tok.isdigit():
            out.append(tok)
        elif tok[1:] != tok[1:].lower() and not tok.isupper():  # keep CamelCase (GitHub, WorldPop)
            out.append(tok[:1].upper() + tok[1:])
        else:
            out.append(tok[:1].upper() + tok[1:].lower())
    return out


def make_download_name(
    base: str,
    ext: str,
    *,
    lang: str | None,
    suffix: str,
    forbidden: re.Pattern,
    max_tokens: int = 14,
) -> tuple[str, list[str]]:
    """Build ``Descriptive_Title_Case_EN_AfDB_DI4A.ext``.

    ``lang="both"`` (one file holding both languages) yields ``..._EN_FR_AfDB_DI4A.ext``.
    Returns the file name and the list of tokens that were removed because
    they matched the forbidden-term list.
    """
    tokens = to_title_case_tokens(base)
    suffix_tokens = [t for t in re.split(r"_+", suffix) if t]
    # Remove the suffix tokens wherever they appear: the suffix is appended once below.
    suffix_upper = {t.upper() for t in suffix_tokens}
    tokens = [t for t in tokens if t.upper() not in suffix_upper]
    removed = [t for t in tokens if forbidden.match(t)]
    tokens = [t for t in tokens if not forbidden.match(t)]
    # Language marker at the end, exactly once.
    if lang:
        tokens = [t for t in tokens if t.upper() not in {"EN", "FR"}]
    tokens = tokens[:max_tokens]
    if lang == "both":
        tokens += ["EN", "FR"]
    elif lang:
        tokens.append(lang.upper())
    if not tokens:
        tokens = ["Document"]
    return "_".join(tokens) + suffix + ext, removed


def clean_stem(stem: str, suffix: str = DEFAULT_CONFIG["download_suffix"]) -> str:
    """Strip language token, publication suffix tokens and a leading time code.

    ``1045_hands-on_EN_DI4A`` -> ``hands-on``; ``GEE_FR_DI4A`` -> ``GEE``.
    """
    stem = LANG_PATTERN.sub("", stem)
    suffix_tokens = {t.lower() for t in re.split(r"[_\-\s]+", suffix) if t}
    tokens = [t for t in re.split(r"[_\-\s]+", stem) if t]
    tokens = [t for t in tokens if t.lower() not in suffix_tokens]
    if tokens and re.fullmatch(r"\d{3,4}", tokens[0]):
        tokens = tokens[1:]
    return " ".join(tokens) or stem


def detect_lang(filename: str) -> str | None:
    stem = Path(filename).stem
    found = LANG_PATTERN.findall(stem)
    return found[-1].lower() if found else None


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def bilingual(value, fallback_en: str = "", fallback_fr: str | None = None) -> dict:
    """Normalise a metadata value into ``{"en": ..., "fr": ...}``."""
    fr_default = fallback_fr if fallback_fr is not None else fallback_en
    if isinstance(value, dict):
        en = str(value.get("en") or value.get("fr") or fallback_en).strip()
        fr = str(value.get("fr") or value.get("en") or fr_default).strip()
        return {"en": en, "fr": fr}
    if isinstance(value, str) and value.strip():
        return {"en": value.strip(), "fr": value.strip()}
    return {"en": fallback_en, "fr": fr_default}


# ---------------------------------------------------------------------------
# Notebook introspection
# ---------------------------------------------------------------------------
def notebook_intro(path: Path) -> tuple[str | None, str | None]:
    """Return (title, first paragraph) from the first Markdown cells."""
    try:
        with path.open(encoding="utf-8") as fh:
            nb = json.load(fh)
    except (OSError, ValueError) as exc:
        warn(f"{path}: cannot parse notebook ({exc})")
        return None, None
    title, para = None, None
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        for raw in strip_html(source).splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                if title is None:
                    title = clean_markdown(line.lstrip("#"))
                continue
            if line.startswith((">", "|", "---")):
                continue
            if title is not None and para is None:
                text = clean_markdown(line)
                if len(text) >= 40:
                    para = text
        if title and para:
            break
    if para and len(para) > 320:
        cut = para[:320]
        para = cut[: cut.rfind(" ")] + "…"
    return title, para


# ---------------------------------------------------------------------------
# File dates
# ---------------------------------------------------------------------------
_git_available: bool | None = None


def file_updated(path: Path) -> str:
    """ISO date of the last git commit touching ``path``; mtime otherwise."""
    global _git_available
    if _git_available is None:
        _git_available = shutil.which("git") is not None and (REPO_ROOT / ".git").exists()
    if _git_available:
        try:
            out = subprocess.run(
                ["git", "log", "-1", "--format=%cI", "--", str(path)],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=20, check=False,
            ).stdout.strip()
            if out:
                return out[:10]
        except (OSError, subprocess.SubprocessError):
            pass
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Configuration & metadata
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    if yaml is None:
        warn(f"PyYAML is not installed: {path.name} ignored (pip install pyyaml)")
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:  # noqa: BLE001 - we want to report any YAML error
        warn(f"{path}: invalid YAML ({exc}); file ignored")
        return {}
    if not isinstance(data, dict):
        warn(f"{path}: expected a mapping at top level; file ignored")
        return {}
    return data


def load_config(path: Path, repo_override: str | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({k: v for k, v in load_yaml(path).items() if v is not None})
    if repo_override:
        cfg["repo"] = repo_override
    if not cfg.get("base_url"):
        owner, _, name = cfg["repo"].partition("/")
        if name.lower() == f"{owner.lower()}.github.io":
            cfg["base_url"] = f"https://{owner}.github.io/"
        else:
            cfg["base_url"] = f"https://{owner}.github.io/{name}/"
    if not cfg["base_url"].endswith("/"):
        cfg["base_url"] += "/"
    return cfg


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------
def pair_key(filename: str, dmeta: dict) -> str:
    """Key used to group the EN and FR versions of the same document.

    By default the language token is removed from the file stem
    (``Data_Visualization_EN.pdf`` and ``Data_Visualization_FR.pdf`` share
    the key ``data-visualization.pdf``).  ``group:`` in ``_meta.yml`` forces
    the association of two files whose names differ.
    """
    if dmeta.get("group"):
        return slugify(str(dmeta["group"]))
    path = Path(filename)
    return f"{slugify(clean_stem(path.stem))}{path.suffix.lower()}"


def scan_content(content_dir: Path, cfg: dict) -> list[dict]:
    """Walk ``content/`` and return the list of theme dictionaries."""
    forbidden = forbidden_regex(cfg.get("forbidden_terms") or [])
    suffix = cfg.get("download_suffix") or "_AfDB_DI4A"
    themes: list[dict] = []
    if not content_dir.is_dir():
        warn(f"content folder not found: {content_dir}")
        return themes

    for folder in sorted(p for p in content_dir.iterdir() if p.is_dir()):
        if folder.name.startswith((".", "_", "~")):
            continue
        meta_path = folder / "_meta.yml"
        meta = load_yaml(meta_path)
        if not meta_path.exists():
            warn(f"{folder.name}: no _meta.yml — using defaults (title from folder name, generic description)")
        theme_id = slugify(folder.name)
        default_title = title_from_folder(folder.name)
        title = bilingual(meta.get("title"), default_title)
        description = bilingual(
            meta.get("description"),
            f"Training resources on {title['en']}: hands-on labs and presentations prepared by "
            f"Data Innovation for Africa.",
            f"Ressources de formation sur {title['fr']} : labs pratiques et présentations préparés par "
            f"Data Innovation for Africa.",
        )
        doc_meta_all = meta.get("documents") or {}
        if not isinstance(doc_meta_all, dict):
            warn(f"{folder.name}: 'documents' in _meta.yml must be a mapping keyed by file name")
            doc_meta_all = {}

        # ------------------------------------------------------------------
        # 1. One record per published file ("version")
        # ------------------------------------------------------------------
        versions: list[dict] = []
        used_names: set[str] = set()
        for file in sorted(folder.iterdir()):
            if not file.is_file() or file.name.startswith((".", "_", "~$")):
                continue
            ext = file.suffix.lower()
            doc_type = PUBLISHED_TYPES.get(ext)
            if doc_type is None:
                continue  # other formats are ignored on purpose
            dmeta = doc_meta_all.get(file.name) or {}
            if not isinstance(dmeta, dict):
                dmeta = {}
            nb_title, nb_para = (None, None)
            if ext == ".ipynb":
                nb_title, nb_para = notebook_intro(file)
            lang = str(dmeta.get("lang") or detect_lang(file.name) or "").lower()
            if lang not in LANG_ORDER:
                if doc_type == "resource":
                    lang = "both"  # an archive without a language suffix is assumed to bundle both
                else:
                    warn(f"{folder.name}/{file.name}: language not detected (use a _EN/_FR suffix or "
                         f"'lang:' in _meta.yml) — assuming English")
                    lang = "en"
            text_lang = "en" if lang == "both" else lang
            fallback_title = nb_title or title_from_folder(clean_stem(file.stem, suffix))
            doc_title = bilingual(dmeta.get("title"), fallback_title)
            if not dmeta.get("title"):
                warn(f"{folder.name}/{file.name}: no title in _meta.yml — using '{fallback_title}'")
            fallback_desc_en = nb_para or GENERIC_DESC[doc_type][0]
            fallback_desc_fr = nb_para or GENERIC_DESC[doc_type][1]
            doc_desc = bilingual(dmeta.get("description"), fallback_desc_en, fallback_desc_fr)
            if not dmeta.get("description"):
                warn(f"{folder.name}/{file.name}: no description in _meta.yml — using "
                     + ("the notebook's first paragraph" if nb_para else "a generic description"))

            base_name = dmeta.get("download") or doc_title["en"]
            download_name, removed = make_download_name(
                str(base_name), ext, lang=lang, suffix=suffix, forbidden=forbidden
            )
            if removed:
                warn(f"{folder.name}/{file.name}: removed forbidden token(s) {removed} from download name")
            if download_name in used_names:
                stem = download_name[: -len(suffix + ext)]
                n = 2
                while f"{stem}_{n}{suffix}{ext}" in used_names:
                    n += 1
                download_name = f"{stem}_{n}{suffix}{ext}"
                warn(f"{folder.name}/{file.name}: duplicate download name, renamed to {download_name}")
            used_names.add(download_name)

            size = file.stat().st_size
            versions.append({
                "_key": pair_key(file.name, dmeta),
                "_order": dmeta.get("order", 1000),
                "_title": doc_title,
                "_description": doc_desc,
                "_type": doc_type,
                "_format": ext.lstrip("."),
                "lang": lang,
                "title": doc_title[text_lang],
                "description": doc_desc[text_lang],
                "size": size,
                "size_human": human_size(size),
                "updated": file_updated(file),
                "source": f"content/{folder.name}/{file.name}",
                "download_name": download_name,
                "file": f"files/{theme_id}/{download_name}",
            })

        # ------------------------------------------------------------------
        # 2. Group the versions of the same document (EN + FR -> one entry)
        # ------------------------------------------------------------------
        groups: dict[str, list[dict]] = {}
        for v in versions:
            key = v["_key"]
            bucket = groups.setdefault(key, [])
            # A single file holding both languages ("both") never shares a card.
            clash = bool(bucket) and (
                v["lang"] == "both"
                or any(o["lang"] in {v["lang"], "both"} for o in bucket)
                or any(o["_type"] != v["_type"] for o in bucket)
            )
            if clash:
                warn(f"{folder.name}/{Path(v['source']).name}: cannot be paired (same language or different "
                     f"type as another file of the group) — kept as a separate entry")
                key = f"{key}--{slugify(Path(v['source']).stem)}"
                bucket = groups.setdefault(key, [])
            bucket.append(v)

        present = {v["source"].rsplit("/", 1)[-1] for v in versions}
        for stale in sorted(set(doc_meta_all) - present):
            warn(f"{folder.name}/_meta.yml: entry '{stale}' matches no published file (removed or renamed?)")

        documents: list[dict] = []
        for key, group in groups.items():
            group.sort(key=lambda v: LANG_ORDER[v["lang"]])
            by_lang = {v["lang"]: v for v in group}
            first = group[0]
            card_title = {L: (by_lang[L]["_title"][L] if L in by_lang else first["_title"][L]) for L in ("en", "fr")}
            card_desc = {L: (by_lang[L]["_description"][L] if L in by_lang else first["_description"][L])
                         for L in ("en", "fr")}
            public_versions = {}
            for v in group:
                public_versions[v["lang"]] = {k: val for k, val in v.items() if not k.startswith("_")}
            documents.append({
                "id": slugify(Path(key).stem if "." in key else key),
                "type": first["_type"],
                "format": first["_format"],
                "langs": [v["lang"] for v in group],
                "bilingual": len(group) > 1,
                "title": card_title,
                "description": card_desc,
                "updated": max(v["updated"] for v in group),
                "versions": public_versions,
                "order": min(v["_order"] for v in group),
            })
        documents.sort(key=lambda d: (d["order"], d["type"], d["title"]["en"].lower()))
        # A notebook and a PDF sharing the same stem are two documents: keep their ids distinct.
        seen: dict[str, int] = {}
        for d in documents:
            seen[d["id"]] = seen.get(d["id"], 0) + 1
        for d in documents:
            d.pop("order", None)
            if seen[d["id"]] > 1:
                d["id"] = f"{d['id']}-{d['format']}"

        cover = meta.get("cover")
        cover_src = None
        if cover:
            candidate = folder / str(cover)
            if candidate.is_file():
                cover_src = candidate
            else:
                warn(f"{folder.name}: cover '{cover}' not found in theme folder")
        else:
            for candidate in sorted(folder.glob("_cover.*")):
                if candidate.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png", ".svg", ".avif"}:
                    cover_src = candidate
                    break

        counts = {kind: sum(d["type"] == kind for d in documents) for kind in DOC_TYPES}
        counts["files"] = len(versions)
        themes.append({
            "id": theme_id,
            "folder": folder.name,
            "order": meta.get("order", 1000),
            "icon": str(meta.get("icon") or "folder"),
            "title": title,
            "description": description,
            "cover": f"assets/img/covers/{theme_id}{cover_src.suffix.lower()}" if cover_src else None,
            "_cover_src": str(cover_src) if cover_src else None,
            "counts": counts,
            "documents": documents,
        })
        if not documents:
            warn(f"{folder.name}: theme has no publishable file (.ipynb, .pdf, .zip) — it will be listed as empty")
    themes.sort(key=lambda t: (t["order"], t["title"]["en"].lower()))
    return themes


# ---------------------------------------------------------------------------
# Rendering & assembly
# ---------------------------------------------------------------------------
def render_template(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def add_links(themes: list[dict], cfg: dict) -> None:
    """Attach download / view / Colab / preview links to each document."""
    repo = cfg["repo"]
    branch = cfg["deploy_branch"]
    base_url = cfg["base_url"]
    for theme in themes:
        for d in theme["documents"]:
            for v in d["versions"].values():
                rel = v["file"]
                links = {"download": rel, "absolute": base_url + rel}
                if d["type"] == "lab":
                    links["view"] = f"https://nbviewer.org/github/{repo}/blob/{branch}/{rel}"
                    links["colab"] = f"https://colab.research.google.com/github/{repo}/blob/{branch}/{rel}"
                elif d["type"] == "presentation":
                    links["preview"] = rel
                # resources (ZIP archives): download only
                v["links"] = links


def build_catalog(themes: list[dict], cfg: dict) -> dict:
    stats = {
        "themes": len(themes),
        "labs": sum(t["counts"]["lab"] for t in themes),
        "presentations": sum(t["counts"]["presentation"] for t in themes),
        "resources": sum(t["counts"]["resource"] for t in themes),
    }
    stats["documents"] = stats["labs"] + stats["presentations"] + stats["resources"]
    stats["files"] = sum(t["counts"]["files"] for t in themes)
    public_themes = [{k: v for k, v in t.items() if not k.startswith("_")} for t in themes]
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "site": {
            "repo": cfg["repo"],
            "deploy_branch": cfg["deploy_branch"],
            "base_url": cfg["base_url"],
            "repo_url": f"https://github.com/{cfg['repo']}",
            "download_suffix": cfg["download_suffix"],
            "image_credits": cfg.get("image_credits") or [],
        },
        "stats": stats,
        "themes": public_themes,
    }


PAGE_DESC_DEFAULT = (
    "Open training resources on data science, Earth observation and AI for Africa, prepared by the "
    "African Development Bank's Data Innovation for Africa (DI4A) team."
)



I18N_TEXT_RE = re.compile(r'(<(\w+)\b[^>]*\sdata-i18n="([\w.]+)"[^>]*>)([^<]*)(</\2>)')
STAT_RE = re.compile(r'(<span class="stat-value" data-stat="(\w+)">)[^<]*(</span>)')


def prerender_i18n(page: str, dictionary: dict, stats: dict | None = None) -> str:
    """Write the English interface strings (and key figures) into the HTML.

    The client re-applies translations at runtime; pre-rendering the default
    language means the first paint already matches the final layout (no
    cumulative layout shift) and the page is readable without JavaScript.
    """
    def lookup(key: str):
        node = dictionary
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        return node if isinstance(node, str) else None

    def repl(m: re.Match) -> str:
        value = lookup(m.group(3))
        if value is None:
            return m.group(0)
        value = value.replace("{year}", str(dt.date.today().year))
        return f"{m.group(1)}{html.escape(value)}{m.group(5)}"

    page = I18N_TEXT_RE.sub(repl, page)
    if stats:
        page = STAT_RE.sub(lambda m: f"{m.group(1)}{stats.get(m.group(2), 0)}{m.group(3)}", page)
    return page

LANGS = ("en", "fr")
OG_LOCALES = {"en": "en_GB", "fr": "fr_FR"}


def load_dicts(i18n_dir: Path) -> dict[str, dict]:
    dicts: dict[str, dict] = {}
    for lang in LANGS:
        path = i18n_dir / f"{lang}.json"
        try:
            dicts[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            warn(f"{path}: cannot read ({exc}); interface strings not pre-rendered for '{lang}'")
            dicts[lang] = {}
    return dicts


def page_mapping(cfg: dict, lang: str, root: str, rel_path: str) -> dict[str, str]:
    """Placeholders shared by every page: root paths, language alternates, canonical URLs.

    ``root`` is the relative path from the page back to the site root (e.g. ``../../``),
    ``rel_path`` the page path relative to a language root (``""`` or ``themes/ntl/``).
    """
    prefix = {l: ("fr/" if l == "fr" else "") for l in LANGS}
    base = cfg["base_url"]
    return {
        "LANG": lang,
        "ROOT": root,
        "HOME": root + prefix[lang],
        "ALT_EN": root + prefix["en"] + rel_path,
        "ALT_FR": root + prefix["fr"] + rel_path,
        "BASE_URL": base,
        "CANONICAL": base + prefix[lang] + rel_path,
        "CANONICAL_EN": base + prefix["en"] + rel_path,
        "CANONICAL_FR": base + prefix["fr"] + rel_path,
        "OG_LOCALE": OG_LOCALES[lang],
    }


def assemble(site_dir: Path, i18n_dir: Path, out_dir: Path, themes: list[dict], catalog: dict, cfg: dict) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(site_dir, out_dir, ignore=shutil.ignore_patterns("theme.html", "index.html", "*.map"))
    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    (out_dir / "files").mkdir(exist_ok=True)
    (out_dir / "assets" / "img" / "covers").mkdir(parents=True, exist_ok=True)
    if i18n_dir.is_dir():
        shutil.copytree(i18n_dir, out_dir / "i18n", dirs_exist_ok=True)
    dicts = load_dicts(i18n_dir)

    # Renamed copies of the published documents (sources are left untouched).
    for theme in themes:
        tdir = out_dir / "files" / theme["id"]
        tdir.mkdir(parents=True, exist_ok=True)
        for d in theme["documents"]:
            for v in d["versions"].values():
                shutil.copy2(REPO_ROOT / v["source"], tdir / v["download_name"])
        if theme.get("_cover_src"):
            shutil.copy2(theme["_cover_src"], out_dir / theme["cover"])

    # 404 page: served by GitHub Pages at any path, so its links are absolute.
    page404 = out_dir / "404.html"
    if page404.exists():
        page404.write_text(prerender_i18n(render_template(page404.read_text(encoding="utf-8"), {
            "ROOT": cfg["base_url"], "BASE_URL": cfg["base_url"],
        }), dicts["en"]), encoding="utf-8")

    # Home and theme pages, one copy per language (EN at the root, FR under /fr/).
    index_tpl = (site_dir / "index.html").read_text(encoding="utf-8")
    theme_tpl = (site_dir / "theme.html").read_text(encoding="utf-8")
    for lang in LANGS:
        lang_dir = out_dir / "fr" if lang == "fr" else out_dir
        lang_dir.mkdir(parents=True, exist_ok=True)
        meta = dicts[lang].get("meta", {}) if dicts[lang] else {}
        mapping = page_mapping(cfg, lang, "../" if lang == "fr" else "./", "")
        mapping.update({
            "PAGE_TITLE": html.escape(meta.get("site_title") or "Data Innovation for Africa — DI4A"),
            "PAGE_DESC": html.escape(meta.get("site_desc") or PAGE_DESC_DEFAULT),
        })
        (lang_dir / "index.html").write_text(
            prerender_i18n(render_template(index_tpl, mapping), dicts[lang], catalog["stats"]), encoding="utf-8")
        for theme in themes:
            page_dir = lang_dir / "themes" / theme["id"]
            page_dir.mkdir(parents=True, exist_ok=True)
            mapping = page_mapping(cfg, lang, "../../../" if lang == "fr" else "../../", f"themes/{theme['id']}/")
            mapping.update({
                "THEME_ID": theme["id"],
                "PAGE_TITLE": html.escape(f"{theme['title'][lang]} — DI4A"),
                "PAGE_DESC": html.escape(theme["description"][lang]),
                "THEME_TITLE": html.escape(theme["title"][lang]),
                "THEME_DESC": html.escape(theme["description"][lang]),
            })
            (page_dir / "index.html").write_text(
                prerender_i18n(render_template(theme_tpl, mapping), dicts[lang]), encoding="utf-8")

    (out_dir / "data" / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    (out_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {cfg['base_url']}sitemap.xml\n", encoding="utf-8")
    today = dt.date.today().isoformat()
    urls = []
    for lang in LANGS:
        prefix = "fr/" if lang == "fr" else ""
        urls.append(cfg["base_url"] + prefix)
        urls += [f"{cfg['base_url']}{prefix}themes/{t['id']}/" for t in themes]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sitemap += [f"  <url><loc>{html.escape(u)}</loc><lastmod>{today}</lastmod></url>" for u in urls]
    sitemap.append("</urlset>")
    (out_dir / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")


def verify_output(out_dir: Path, cfg: dict) -> list[str]:
    """Check every published file name: suffix present, no forbidden term."""
    forbidden = forbidden_regex(cfg.get("forbidden_terms") or [])
    suffix = cfg["download_suffix"]
    problems = []
    for f in (out_dir / "files").rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in PUBLISHED_TYPES:
            problems.append(f"{f.name}: unexpected file type")
        if not f.stem.endswith(suffix):
            problems.append(f"{f.name}: missing suffix {suffix}")
        bad = [t for t in f.stem.split("_") if forbidden.match(t)]
        if bad:
            problems.append(f"{f.name}: forbidden token(s) {bad}")
        if re.search(r"[^A-Za-z0-9_.]", f.name):
            problems.append(f"{f.name}: non-ASCII or special characters")
    return problems


# ---------------------------------------------------------------------------
# README catalogue tables
# ---------------------------------------------------------------------------
def catalog_markdown(catalog: dict, lang: str) -> str:
    base = catalog["site"]["base_url"]
    labels = {
        "en": ("Theme", "Labs", "Presentations", "Archives", "Page"),
        "fr": ("Thème", "Labs", "Présentations", "Archives", "Page"),
    }[lang]
    badges = {
        "en": {"lab": "Lab", "presentation": "Presentation", "resource": "Archive"},
        "fr": {"lab": "Lab", "presentation": "Présentation", "resource": "Archive"},
    }[lang]
    lines = [f"| {labels[0]} | {labels[1]} | {labels[2]} | {labels[3]} | {labels[4]} |", "|---|:-:|:-:|:-:|---|"]
    for t in catalog["themes"]:
        c = t["counts"]
        lines.append(f"| **{t['title'][lang]}** | {c['lab']} | {c['presentation']} | {c.get('resource', 0)} "
                     f"| [{base}themes/{t['id']}/]({base}themes/{t['id']}/) |")
    for t in catalog["themes"]:
        lines.append("")
        lines.append(f"<details><summary><b>{t['title'][lang]}</b> — {len(t['documents'])} documents</summary>")
        lines.append("")
        for d in t["documents"]:
            badge = badges.get(d["type"], d["type"])
            links = " · ".join(
                f"[{'EN+FR' if L == 'both' else L.upper()}]({base}{v['file']}) <sub>({v['size_human']})</sub>"
                for L, v in d["versions"].items())
            lines.append(f"- **{badge}** — {d['title'][lang]} — {links}")
        lines.append("")
        lines.append("</details>")
    return "\n".join(lines)


def update_readme(readme: Path, catalog: dict) -> bool:
    if not readme.exists():
        warn(f"{readme} not found; README not updated")
        return False
    text = readme.read_text(encoding="utf-8")
    changed = False
    for lang in ("en", "fr"):
        start, end = f"<!-- CATALOG-{lang.upper()}:START -->", f"<!-- CATALOG-{lang.upper()}:END -->"
        if start in text and end in text:
            before, _, rest = text.partition(start)
            _, _, after = rest.partition(end)
            new = f"{before}{start}\n{catalog_markdown(catalog, lang)}\n{end}{after}"
            if new != text:
                text, changed = new, True
    if changed:
        readme.write_text(text, encoding="utf-8")
        info("README catalogue tables refreshed")
    return changed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the DI4A static website.")
    parser.add_argument("--content", default=str(REPO_ROOT / "content"))
    parser.add_argument("--site", default=str(REPO_ROOT / "site"))
    parser.add_argument("--i18n", default=str(REPO_ROOT / "i18n"))
    parser.add_argument("--out", default=str(REPO_ROOT / "dist"))
    parser.add_argument("--config", default=str(REPO_ROOT / "site.config.yml"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"),
                        help="owner/name of the GitHub repository (default: $GITHUB_REPOSITORY or config)")
    parser.add_argument("--update-readme", action="store_true", help="refresh the catalogue tables in README.md")
    parser.add_argument("--serve", action="store_true", help="serve the built site on http://localhost:8080")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    cfg = load_config(Path(args.config), args.repo)
    info(f"repository {cfg['repo']} — site {cfg['base_url']}")
    themes = scan_content(Path(args.content), cfg)
    add_links(themes, cfg)
    catalog = build_catalog(themes, cfg)
    assemble(Path(args.site), Path(args.i18n), Path(args.out), themes, catalog, cfg)
    problems = verify_output(Path(args.out), cfg)
    for p in problems:
        log("error", p)
    if problems:
        return 1
    s = catalog["stats"]
    info(f"{s['themes']} theme(s), {s['labs']} lab(s), {s['presentations']} presentation(s), "
         f"{s['resources']} archive(s) -> {args.out}")
    for t in themes:
        for d in t["documents"]:
            for v in d["versions"].values():
                info(f"  {t['id']}/{v['download_name']}")
    if args.update_readme:
        update_readme(REPO_ROOT / "README.md", catalog)
    if args.serve:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.out)
        info(f"serving {args.out} on http://localhost:{args.port}/ (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
