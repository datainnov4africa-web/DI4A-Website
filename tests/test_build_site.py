"""Unit tests for scripts/build_site.py (run: python -m unittest discover tests)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_site as bs  # noqa: E402

FORBIDDEN = bs.forbidden_regex([
    r"ATI\d*", r"(19|20)\d{2}", "Mauritius|Maurice", "Workshop|Atelier|Session",
    "October|Octobre",
])


class NamingTests(unittest.TestCase):
    def test_title_case_with_suffix(self):
        name, removed = bs.make_download_name(
            "Introduction to Python for data analysis", ".ipynb",
            lang=None, suffix="_AfDB_DI4A", forbidden=FORBIDDEN)
        self.assertEqual(name, "Introduction_To_Python_For_Data_Analysis_AfDB_DI4A.ipynb")
        self.assertEqual(removed, [])

    def test_accents_and_special_chars_removed(self):
        name, _ = bs.make_download_name(
            "Lumières nocturnes : anatomie d'un fichier (HDF5) — été", ".pdf",
            lang="fr", suffix="_AfDB_DI4A", forbidden=FORBIDDEN)
        self.assertEqual(name, "Lumieres_Nocturnes_Anatomie_D_Un_Fichier_HDF5_Ete_FR_AfDB_DI4A.pdf")

    def test_forbidden_tokens_are_stripped(self):
        name, removed = bs.make_download_name(
            "ATI2026 Workshop Mauritius October 2026 RAG hands-on", ".ipynb",
            lang="en", suffix="_AfDB_DI4A", forbidden=FORBIDDEN)
        self.assertEqual(name, "RAG_Hands_On_EN_AfDB_DI4A.ipynb")
        self.assertEqual({r.lower() for r in removed}, {"ati2026", "workshop", "mauritius", "october", "2026"})

    def test_suffix_not_duplicated(self):
        name, _ = bs.make_download_name(
            "Data_Visualization_Best_Practices_AfDB_DI4A", ".pdf",
            lang=None, suffix="_AfDB_DI4A", forbidden=FORBIDDEN)
        self.assertEqual(name, "Data_Visualization_Best_Practices_AfDB_DI4A.pdf")

    def test_language_marker_once(self):
        name, _ = bs.make_download_name("NTL hands-on part 1 EN", ".ipynb",
                                        lang="en", suffix="_AfDB_DI4A", forbidden=FORBIDDEN)
        self.assertEqual(name, "NTL_Hands_On_Part_1_EN_AfDB_DI4A.ipynb")

    def test_clean_stem_and_suffix_tokens(self):
        self.assertEqual(bs.clean_stem("1045_hands-on_EN_DI4A"), "hands on")
        self.assertEqual(bs.clean_stem("GEE_FR_DI4A"), "GEE")
        self.assertEqual(bs.clean_stem("night-time-lights_AfDB-DI4A"), "night time lights")
        name, _ = bs.make_download_name("1430 DI4A practical guide EN AfDB DI4A", ".pdf",
                                        lang="en", suffix="_AfDB_DI4A",
                                        forbidden=bs.forbidden_regex([r"\d{3,4}"]))
        self.assertEqual(name, "Practical_Guide_EN_AfDB_DI4A.pdf")

    def test_detect_lang(self):
        self.assertEqual(bs.detect_lang("GEE_FR_BigData.pdf"), "fr")
        self.assertEqual(bs.detect_lang("notes_EN.ipynb"), "en")
        self.assertIsNone(bs.detect_lang("night-time-lights.pptx"))

    def test_title_from_folder(self):
        self.assertEqual(bs.title_from_folder("Machine-Learning"), "Machine Learning")
        self.assertEqual(bs.title_from_folder("NTL"), "NTL")
        self.assertEqual(bs.title_from_folder("data_visualization basics"), "Data Visualization Basics")

    def test_slugify(self):
        self.assertEqual(bs.slugify("Machine Learning"), "machine-learning")
        self.assertEqual(bs.slugify("Données & Cartes"), "donnees-cartes")


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        content = self.root / "content"
        theme = content / "Machine-Learning"
        theme.mkdir(parents=True)
        nb = {
            "cells": [
                {"cell_type": "markdown", "source": [
                    "<img src='x.png'>\n", "# 🚀 Intro to Python for Data Analysis\n", "\n",
                    "This notebook introduces pandas and matplotlib through a real survey dataset "
                    "from a statistical office.\n"]},
                {"cell_type": "code", "source": ["print(1)"]},
            ],
            "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
        }
        (theme / "intro_python_EN.ipynb").write_text(json.dumps(nb), encoding="utf-8")
        (theme / "slides_Workshop_2026_FR.pdf").write_bytes(b"%PDF-1.4 fake")
        (theme / "ignored.pptx").write_bytes(b"zip")
        (theme / "~$lock.pptx").write_bytes(b"")
        (content / "_drafts").mkdir()
        (content / "_drafts" / "x.pdf").write_bytes(b"%PDF")
        self.cfg = dict(bs.DEFAULT_CONFIG)
        self.cfg["forbidden_terms"] = [r"ATI\d*", r"(19|20)\d{2}", "Workshop|Atelier"]
        self.content = content

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_without_meta(self):
        themes = bs.scan_content(self.content, self.cfg)
        self.assertEqual(len(themes), 1)
        t = themes[0]
        self.assertEqual(t["id"], "machine-learning")
        self.assertEqual(t["title"]["en"], "Machine Learning")
        self.assertEqual(t["counts"], {"lab": 1, "presentation": 1, "resource": 0, "files": 2})
        names = {v["download_name"] for d in t["documents"] for v in d["versions"].values()}
        self.assertIn("Intro_To_Python_For_Data_Analysis_EN_AfDB_DI4A.ipynb", names)
        self.assertIn("Slides_FR_AfDB_DI4A.pdf", names)  # Workshop / 2026 stripped
        lab = next(d for d in t["documents"] if d["type"] == "lab")
        self.assertTrue(lab["description"]["en"].startswith("This notebook introduces pandas"))
        self.assertEqual(lab["langs"], ["en"])
        self.assertFalse(lab["bilingual"])

    def test_scan_with_meta(self):
        (self.content / "Machine-Learning" / "_meta.yml").write_text(
            "order: 1\nicon: brain\ntitle:\n  en: Machine Learning\n  fr: Apprentissage automatique\n"
            "documents:\n  intro_python_EN.ipynb:\n    download: Python_For_Data_Analysis_Primer\n"
            "    title: {en: Python primer, fr: Initiation à Python}\n", encoding="utf-8")
        if bs.yaml is None:  # pragma: no cover
            self.skipTest("PyYAML not installed")
        themes = bs.scan_content(self.content, self.cfg)
        t = themes[0]
        self.assertEqual(t["title"]["fr"], "Apprentissage automatique")
        self.assertEqual(t["icon"], "brain")
        lab = next(d for d in t["documents"] if d["type"] == "lab")
        self.assertEqual(lab["versions"]["en"]["download_name"], "Python_For_Data_Analysis_Primer_EN_AfDB_DI4A.ipynb")
        self.assertEqual(lab["title"]["fr"], "Initiation à Python")

    def test_links(self):
        themes = bs.scan_content(self.content, self.cfg)
        cfg = bs.load_config(self.root / "missing.yml", "owner/repo")
        bs.add_links(themes, cfg)
        lab = next(d for d in themes[0]["documents"] if d["type"] == "lab")["versions"]["en"]
        self.assertTrue(lab["links"]["colab"].startswith(
            "https://colab.research.google.com/github/owner/repo/blob/gh-pages/files/machine-learning/"))
        self.assertEqual(cfg["base_url"], "https://owner.github.io/repo/")


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.content = Path(self.tmp.name) / "content"
        self.theme = self.content / "Viz"
        self.theme.mkdir(parents=True)
        for name in ("Data_Visualization_EN.pdf", "Data_Visualization_FR.pdf", "Cheatsheet_EN.pdf",
                     "guide_colors_EN.pdf", "guide_couleurs_FR.pdf"):
            (self.theme / name).write_bytes(b"%PDF-1.4 fake")
        self.cfg = dict(bs.DEFAULT_CONFIG)

    def tearDown(self):
        self.tmp.cleanup()

    def test_suffix_pairing_and_single(self):
        docs = bs.scan_content(self.content, self.cfg)[0]["documents"]
        by_id = {d["id"]: d for d in docs}
        paired = by_id["data-visualization"]
        self.assertTrue(paired["bilingual"])
        self.assertEqual(paired["langs"], ["en", "fr"])
        self.assertEqual(paired["versions"]["fr"]["download_name"], "Data_Visualization_FR_AfDB_DI4A.pdf")
        self.assertEqual(paired["versions"]["en"]["download_name"], "Data_Visualization_EN_AfDB_DI4A.pdf")
        single = by_id["cheatsheet"]
        self.assertFalse(single["bilingual"])
        self.assertEqual(single["langs"], ["en"])
        # different stems are NOT paired without a group in _meta.yml
        self.assertIn("guide-colors", by_id)
        self.assertIn("guide-couleurs", by_id)

    def test_forced_group(self):
        if bs.yaml is None:  # pragma: no cover
            self.skipTest("PyYAML not installed")
        (self.theme / "_meta.yml").write_text(
            "documents:\n  guide_colors_EN.pdf: {group: colour-guide}\n  guide_couleurs_FR.pdf: {group: colour-guide}\n",
            encoding="utf-8")
        docs = bs.scan_content(self.content, self.cfg)[0]["documents"]
        by_id = {d["id"]: d for d in docs}
        self.assertIn("colour-guide", by_id)
        self.assertEqual(by_id["colour-guide"]["langs"], ["en", "fr"])
        self.assertNotIn("guide-couleurs", by_id)

    def test_notebook_and_pdf_with_same_stem_get_distinct_ids(self):
        for name in ("1445_hands-on_EN_DI4A.ipynb", "1445_hands-on_FR_DI4A.ipynb",
                     "1445_hands-on_EN_DI4A.pdf", "1445_hands-on_FR_DI4A.pdf"):
            (self.theme / name).write_text('{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
                                           if name.endswith(".ipynb") else "%PDF-1.4", encoding="utf-8")
        docs = bs.scan_content(self.content, self.cfg)[0]["documents"]
        ids = [d["id"] for d in docs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("hands-on-ipynb", ids)
        self.assertIn("hands-on-pdf", ids)

    def test_removing_a_version_makes_card_monolingual(self):
        (self.theme / "Data_Visualization_FR.pdf").unlink()
        docs = bs.scan_content(self.content, self.cfg)[0]["documents"]
        paired = next(d for d in docs if d["id"] == "data-visualization")
        self.assertFalse(paired["bilingual"])
        self.assertEqual(list(paired["versions"]), ["en"])


class ArchiveTests(unittest.TestCase):
    """ZIP archives are published as 'resource' documents (download only)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.content = self.root / "content"
        self.theme = self.content / "CPI"
        self.theme.mkdir(parents=True)
        (self.theme / "toolkit.zip").write_bytes(b"PK\x03\x04 fake")
        (self.theme / "slides_EN.pdf").write_bytes(b"%PDF-1.4 fake")
        self.cfg = dict(bs.DEFAULT_CONFIG)

    def tearDown(self):
        self.tmp.cleanup()

    def test_both_language_marker(self):
        name, _ = bs.make_download_name("Price index toolkit", ".zip", lang="both",
                                        suffix="_AfDB_DI4A", forbidden=FORBIDDEN)
        self.assertEqual(name, "Price_Index_Toolkit_EN_FR_AfDB_DI4A.zip")

    def test_archive_without_suffix_is_bilingual_single_file(self):
        themes = bs.scan_content(self.content, self.cfg)
        bs.add_links(themes, bs.load_config(self.root / "missing.yml", "owner/repo"))
        t = themes[0]
        self.assertEqual(t["counts"]["resource"], 1)
        self.assertEqual(t["counts"]["presentation"], 1)
        zip_doc = next(d for d in t["documents"] if d["type"] == "resource")
        self.assertEqual(zip_doc["langs"], ["both"])
        self.assertFalse(zip_doc["bilingual"])
        v = zip_doc["versions"]["both"]
        self.assertEqual(v["download_name"], "Toolkit_EN_FR_AfDB_DI4A.zip")
        self.assertNotIn("preview", v["links"])
        self.assertNotIn("colab", v["links"])
        self.assertIn("download", v["links"])
        catalog = bs.build_catalog(themes, self.cfg)
        self.assertEqual(catalog["stats"]["resources"], 1)
        self.assertEqual(catalog["stats"]["documents"], 2)
        md = bs.catalog_markdown(catalog, "en")
        self.assertIn("**Archive**", md)
        self.assertIn("[EN+FR]", md)

    def test_archive_with_language_suffix(self):
        (self.theme / "toolkit.zip").rename(self.theme / "toolkit_FR.zip")
        docs = bs.scan_content(self.content, self.cfg)[0]["documents"]
        zip_doc = next(d for d in docs if d["type"] == "resource")
        self.assertEqual(zip_doc["langs"], ["fr"])
        self.assertEqual(zip_doc["versions"]["fr"]["download_name"], "Toolkit_FR_AfDB_DI4A.zip")


if __name__ == "__main__":
    unittest.main()
