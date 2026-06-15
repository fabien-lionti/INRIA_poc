#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hal_acentauri_hceres_poc.py

Monolithic Python POC for an automated HAL-based bibliometric analysis of the
ACENTAURI team, oriented toward an HCERES-style evaluation report.

Design goals
------------
- Single script, no database, no backend, no dashboard.
- Autonomous by default: tries to discover HAL structure/query and infer useful
  metadata from HAL records.
- Optional CSV files are enrichments/overrides, never hard dependencies.
- Robust to missing/heterogeneous HAL metadata.
- Generates CSV tables, LaTeX tables, figures, edge lists and a Markdown report.

Typical usage
-------------
    python hal_acentauri_hceres_poc.py

Optional usage
--------------
    python hal_acentauri_hceres_poc.py \
        --start-year 2022 \
        --end-year 2026 \
        --team ACENTAURI \
        --output-dir outputs \
        --theme-mapping data/theme_mapping.csv \
        --members-csv data/acentauri_members.csv

Notes
-----
This is a proof of concept. It intentionally keeps all logic in one file, while
still being organized into functions. Indicators that rely on incomplete or
inferred information are explicitly marked in logs and reports.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import logging
import math
import re
import sys
import time
import unicodedata
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import numpy as np
    import pandas as pd
    import requests
except ModuleNotFoundError as exc:  # pragma: no cover
    missing = exc.name or "runtime dependency"
    raise SystemExit(
        f"Missing Python dependency: {missing}. "
        "Install the package with `python -m pip install -e .` "
        "or install dependencies with `python -m pip install -r requirements.txt`."
    ) from exc

try:
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    plt = None
    warnings.warn(f"matplotlib unavailable: figure generation disabled ({exc})")

try:
    import networkx as nx
except Exception as exc:  # pragma: no cover
    nx = None
    warnings.warn(f"networkx unavailable: network exports will be simplified ({exc})")

try:
    from rapidfuzz import fuzz, process  # type: ignore
except Exception:  # pragma: no cover
    fuzz = None
    process = None


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

HAL_SEARCH_URLS = [
    "https://api.hal.science/search/",
    "https://api.archives-ouvertes.fr/search/",  # legacy fallback
]
HAL_REF_STRUCTURE_URLS = [
    "https://api.hal.science/ref/structure/",
    "https://api.archives-ouvertes.fr/ref/structure/",  # legacy fallback
]

DEFAULT_START_YEAR = 2022
DEFAULT_END_YEAR = 2026
DEFAULT_TEAM_NAME = "ACENTAURI"
DEFAULT_OUTPUT_DIR = "outputs"

# HAL fields: some are standard, some may be absent depending on records.
HAL_FIELDS = [
    "halId_s",
    "docid",
    "uri_s",
    "title_s",
    "title_t",
    "abstract_s",
    "keyword_s",
    "producedDateY_i",
    "publicationDate_s",
    "submittedDate_s",
    "submittedDate_tdate",
    "docType_s",
    "authFullName_s",
    "authIdHal_s",
    "authFirstName_s",
    "authLastName_s",
    "authStructName_s",
    "authStructId_i",
    "structName_s",
    "structAcronym_s",
    "structId_i",
    "instStructName_s",
    "labStructName_s",
    "rteamStructName_s",
    "country_s",
    "language_s",
    "domain_s",
    "journalTitle_s",
    "conferenceTitle_s",
    "proceedingsTitle_s",
    "publisher_s",
    "doiId_s",
    "fileMain_s",
    "files_s",
    "linkExtUrl_s",
    "submitType_s",
]

# Easy-to-adjust publication filtering.
DEFAULT_EXCLUDED_DOC_TYPES = {
    "THESE",       # thesis
    "HDR",         # habilitation
    "LECTURE",     # lecture notes / course material
    "REPORT",      # technical report, configurable
    "MEM",         # master thesis / dissertation-like material
    "UNDEFINED",
}

ACADEMIC_KEYWORDS = [
    "univers", "inria", "cnrs", "inserm", "inrae", "ird", "cea", "ens", "ecole",
    "école", "polytech", "sorbonne", "laboratoire", "laboratory", "lab", "institut",
    "institute", "univ", "college", "faculty", "research center", "centre de recherche",
]
INDUSTRIAL_KEYWORDS = [
    "sa", "sas", "sarl", "ltd", "limited", "inc", "corp", "gmbh", "company", "industr",
    "technolog", "systems", "robotics", "automotive", "airbus", "thales", "naval", "bosch",
    "toyota", "renault", "framatome", "edf", "orange", "atos", "capgemini",
]

THEME_LABELS = ["ARC", "RIC", "MOC"]
UNKNOWN = "unknown"
UNASSIGNED = "unassigned"


# -----------------------------------------------------------------------------
# Logging and small helpers
# -----------------------------------------------------------------------------

def setup_logging(output_dir: Path, verbose: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "hal_acentauri_hceres_poc.log"
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    logging.info("Log file: %s", log_path)


def ensure_output_tree(output_dir: Path) -> Dict[str, Path]:
    paths = {
        "root": output_dir,
        "figures": output_dir / "figures",
        "tables": output_dir / "tables",
        "latex": output_dir / "latex",
        "reports": output_dir / "reports",
        "network": output_dir / "network",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value)
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name(value: Any) -> str:
    text = normalize_text(value)
    # Remove frequent punctuation particles but keep enough identity.
    text = re.sub(r"\b(dr|prof|mr|mrs|ms|mme|m)\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def listify(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def first_nonempty(*values: Any) -> Any:
    for v in values:
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        if isinstance(v, str) and not v.strip():
            continue
        if isinstance(v, (list, tuple)) and len(v) == 0:
            continue
        return v
    return None


def safe_join(values: Any, sep: str = " | ") -> str:
    vals = [str(v).strip() for v in listify(values) if str(v).strip()]
    return sep.join(dict.fromkeys(vals))


def safe_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            m = re.search(r"(19|20)\d{2}", value)
            if m:
                return int(m.group(0))
        return int(value)
    except Exception:
        return None


def save_df(df: pd.DataFrame, path: Path, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index, encoding="utf-8")
    logging.info("Wrote %s (%d rows)", path, len(df))


def save_latex(df: pd.DataFrame, path: Path, caption: str = "", label: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        latex = df.to_latex(index=False, escape=True, caption=caption or None, label=label or None)
    path.write_text(latex, encoding="utf-8")
    logging.info("Wrote %s", path)


def approximate_match(query: str, choices: Sequence[str], cutoff: float = 0.85) -> Optional[str]:
    qn = normalize_text(query)
    norm_to_original = {normalize_text(c): c for c in choices if str(c).strip()}
    norms = list(norm_to_original)
    if not qn or not norms:
        return None
    if process is not None and fuzz is not None:
        match = process.extractOne(qn, norms, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= cutoff * 100:
            return norm_to_original[match[0]]
        return None
    match = difflib.get_close_matches(qn, norms, n=1, cutoff=cutoff)
    return norm_to_original[match[0]] if match else None


def request_json(url: str, params: Dict[str, Any], timeout: int = 30, retries: int = 3) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            logging.warning("Request failed (%s/%s): %s | params=%s", attempt, retries, exc, params)
            time.sleep(min(2 * attempt, 8))
    raise RuntimeError(f"API request failed after {retries} attempts: {last_error}")


# -----------------------------------------------------------------------------
# HAL discovery and retrieval
# -----------------------------------------------------------------------------

@dataclass
class DiscoveryResult:
    query: str
    source: str
    confidence: str
    structure_id: Optional[int] = None
    structure_name: Optional[str] = None
    warnings: List[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "source": self.source,
            "confidence": self.confidence,
            "structure_id": self.structure_id,
            "structure_name": self.structure_name,
            "warnings": "; ".join(self.warnings or []),
        }


def discover_acentauri_hal_query(team_name: str, explicit_query: Optional[str], explicit_structure_id: Optional[int]) -> DiscoveryResult:
    """Try to discover the best HAL query for the team.

    Priority:
    1. Explicit HAL query.
    2. Explicit HAL structure id.
    3. HAL structure reference search by acronym/name.
    4. Text fallback query over structures and affiliations.
    """
    team = team_name.strip()
    if explicit_query:
        logging.info("Using explicit HAL query: %s", explicit_query)
        return DiscoveryResult(query=explicit_query, source="manual_query", confidence="manual", warnings=[])

    if explicit_structure_id is not None:
        q = f"structId_i:{explicit_structure_id}"
        logging.info("Using explicit HAL structure id: %s", explicit_structure_id)
        return DiscoveryResult(query=q, source="manual_structure_id", confidence="manual", structure_id=explicit_structure_id, warnings=[])

    warnings_list: List[str] = []
    for base_url in HAL_REF_STRUCTURE_URLS:
        params = {
            "q": f'acronym_s:"{team}" OR name_s:"{team}" OR valid_s:"VALID"',
            "fl": "docid,name_s,acronym_s,type_s,valid_s,parentName_s,url_s",
            "rows": 20,
            "wt": "json",
        }
        try:
            data = request_json(base_url, params=params, timeout=20, retries=2)
            docs = data.get("response", {}).get("docs", [])
            candidates = []
            for d in docs:
                names = listify(d.get("name_s")) + listify(d.get("acronym_s"))
                score = max((similarity(team, n) for n in names), default=0.0)
                if score >= 0.65 or normalize_text(team) in " ".join(normalize_text(n) for n in names):
                    candidates.append((score, d))
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                best = candidates[0][1]
                sid = safe_year(best.get("docid"))
                name = first_nonempty(safe_join(best.get("name_s")), safe_join(best.get("acronym_s")))
                if sid is not None:
                    q = f"structId_i:{sid}"
                    logging.info("Discovered likely HAL structure: %s (%s)", name, sid)
                    return DiscoveryResult(
                        query=q,
                        source="hal_ref_structure",
                        confidence="inferred_high" if candidates[0][0] > 0.9 else "inferred_medium",
                        structure_id=sid,
                        structure_name=name,
                        warnings=[],
                    )
        except Exception as exc:
            msg = f"HAL structure discovery failed on {base_url}: {exc}"
            warnings_list.append(msg)
            logging.warning(msg)

    # Fallback: broad text query. This can overmatch, so confidence is low.
    fallback_query = (
        f'(rteamStructName_s:"{team}" OR structAcronym_s:"{team}" OR '
        f'structName_s:"{team}" OR authStructName_s:"{team}" OR title_t:"{team}" OR abstract_t:"{team}")'
    )
    warnings_list.append("Could not identify a reliable HAL structure id; using broad textual fallback query.")
    logging.warning(warnings_list[-1])
    return DiscoveryResult(
        query=fallback_query,
        source="fallback_text_query",
        confidence="inferred_low",
        warnings=warnings_list,
    )


def similarity(a: str, b: str) -> float:
    an, bn = normalize_text(a), normalize_text(b)
    if not an or not bn:
        return 0.0
    return difflib.SequenceMatcher(None, an, bn).ratio()


def query_hal_api(query: str, start_year: int, end_year: int, rows: int = 500, sort: str = "producedDateY_i asc") -> List[Dict[str, Any]]:
    """Retrieve all HAL records for a query and a production-year range."""
    fq = f"producedDateY_i:[{start_year} TO {end_year}]"
    fields = ",".join(HAL_FIELDS)
    all_docs: List[Dict[str, Any]] = []

    for base_url in HAL_SEARCH_URLS:
        start = 0
        total_expected: Optional[int] = None
        try:
            while True:
                params = {
                    "q": query,
                    "fq": fq,
                    "fl": fields,
                    "rows": rows,
                    "start": start,
                    "sort": sort,
                    "wt": "json",
                }
                data = request_json(base_url, params=params, timeout=45, retries=3)
                response = data.get("response", {})
                docs = response.get("docs", [])
                total_expected = response.get("numFound", total_expected)
                all_docs.extend(docs)
                logging.info("HAL batch: start=%s rows=%s retrieved=%s total=%s", start, rows, len(docs), total_expected)
                if not docs or len(all_docs) >= int(total_expected or 0):
                    break
                start += rows
                time.sleep(0.2)
            logging.info("Retrieved %d raw HAL records from %s", len(all_docs), base_url)
            return all_docs
        except Exception as exc:
            logging.warning("HAL search failed on %s: %s", base_url, exc)
            all_docs = []
            continue

    raise RuntimeError("Unable to retrieve HAL records from available HAL endpoints.")


# -----------------------------------------------------------------------------
# Data loading: optional overrides/enrichments
# -----------------------------------------------------------------------------

def load_optional_csv(path: Optional[Path], expected_columns: Optional[Sequence[str]] = None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    if not path.exists():
        logging.warning("Optional CSV not found: %s", path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if expected_columns:
            missing = [c for c in expected_columns if c not in df.columns]
            if missing:
                logging.warning("CSV %s is missing expected columns: %s", path, missing)
        logging.info("Loaded optional CSV %s (%d rows)", path, len(df))
        return df
    except Exception as exc:
        logging.warning("Could not read optional CSV %s: %s", path, exc)
        return pd.DataFrame()


def infer_or_load_theme_mapping(theme_mapping_csv: Optional[Path], members_csv: Optional[Path]) -> pd.DataFrame:
    """Load theme mappings if available. Otherwise return an empty mapping.

    The script deliberately does not invent ARC/RIC/MOC meanings. It supports
    automatic indicators on the known subset only.
    """
    theme_df = load_optional_csv(theme_mapping_csv, expected_columns=["author_name", "theme"])
    members_df = load_optional_csv(members_csv)

    dfs = []
    if not theme_df.empty:
        dfs.append(theme_df)
    if not members_df.empty and {"author_name", "theme"}.issubset(members_df.columns):
        dfs.append(members_df[[c for c in members_df.columns if c in {"author_name", "theme", "status"}]])

    if not dfs:
        logging.warning("No theme mapping provided. ARC/RIC/MOC indicators will be computed only if themes can be inferred from metadata, otherwise marked unassigned.")
        return pd.DataFrame(columns=["author_name", "author_norm", "theme", "status", "source"])

    out = pd.concat(dfs, ignore_index=True).dropna(subset=["author_name", "theme"])
    out["author_norm"] = out["author_name"].map(normalize_name)
    out["theme"] = out["theme"].astype(str).str.strip().str.upper()
    out["source"] = "manual_csv"
    out = out.drop_duplicates(subset=["author_norm", "theme"])
    logging.info("Theme mapping coverage: %d author-theme rows", len(out))
    return out


# -----------------------------------------------------------------------------
# Cleaning, extraction and deduplication
# -----------------------------------------------------------------------------

def clean_publication_metadata(raw_docs: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for d in raw_docs:
        title = first_nonempty(d.get("title_s"), d.get("title_t"))
        if isinstance(title, list):
            title = title[0] if title else ""
        year = safe_year(d.get("producedDateY_i")) or safe_year(d.get("publicationDate_s")) or safe_year(d.get("submittedDate_s"))
        authors = [str(a).strip() for a in listify(d.get("authFullName_s")) if str(a).strip()]
        row = {
            "hal_id": first_nonempty(d.get("halId_s"), d.get("docid")),
            "docid": d.get("docid"),
            "hal_url": first_nonempty(d.get("uri_s"), f"https://hal.science/{d.get('halId_s')}" if d.get("halId_s") else ""),
            "title": title or "",
            "title_norm": normalize_text(title or ""),
            "year": year,
            "publication_date": first_nonempty(d.get("publicationDate_s"), ""),
            "deposit_date": first_nonempty(d.get("submittedDate_s"), d.get("submittedDate_tdate"), ""),
            "doc_type": str(first_nonempty(d.get("docType_s"), UNKNOWN)).upper(),
            "authors": safe_join(authors),
            "authors_list": authors,
            "first_author": authors[0] if authors else "",
            "first_author_norm": normalize_name(authors[0]) if authors else "",
            "author_ids": safe_join(d.get("authIdHal_s")),
            "author_structures": safe_join(d.get("authStructName_s")),
            "structures": safe_join(d.get("structName_s")),
            "structure_acronyms": safe_join(d.get("structAcronym_s")),
            "institutions": safe_join(d.get("instStructName_s")),
            "laboratories": safe_join(d.get("labStructName_s")),
            "research_teams": safe_join(d.get("rteamStructName_s")),
            "countries": safe_join(d.get("country_s")),
            "language": safe_join(d.get("language_s")),
            "domains": safe_join(d.get("domain_s")),
            "journal": safe_join(d.get("journalTitle_s")),
            "conference": safe_join(d.get("conferenceTitle_s")),
            "proceedings": safe_join(d.get("proceedingsTitle_s")),
            "publisher": safe_join(d.get("publisher_s")),
            "doi": safe_join(d.get("doiId_s")),
            "file_main": safe_join(d.get("fileMain_s")),
            "files": safe_join(first_nonempty(d.get("files_s"), d.get("fileMain_s"))),
            "external_links": safe_join(d.get("linkExtUrl_s")),
            "submit_type": safe_join(d.get("submitType_s")),
            "abstract": safe_join(d.get("abstract_s")),
            "keywords": safe_join(d.get("keyword_s")),
            "metadata_source": "hal_api",
        }
        row["has_full_text"] = bool(row["file_main"] or row["files"] or str(row["submit_type"]).lower() == "file")
        row["has_doi"] = bool(row["doi"])
        row["venue"] = first_nonempty(row["journal"], row["conference"], row["proceedings"], row["publisher"], "") or ""
        row["venue_type"] = infer_venue_type(row)
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    logging.info("Cleaned metadata for %d records", len(df))
    return df


def infer_venue_type(row: Dict[str, Any]) -> str:
    if row.get("journal"):
        return "journal"
    if row.get("conference"):
        return "conference"
    if row.get("proceedings"):
        return "proceedings"
    if row.get("publisher"):
        return "publisher_or_book"
    return "unknown"


def filter_publications(df: pd.DataFrame, excluded_doc_types: Iterable[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), df.copy()
    excluded = {str(x).upper().strip() for x in excluded_doc_types if str(x).strip()}
    mask = ~df["doc_type"].astype(str).str.upper().isin(excluded)
    kept = df[mask].copy()
    removed = df[~mask].copy()
    logging.info("Filtered records: kept=%d removed=%d excluded_types=%s", len(kept), len(removed), sorted(excluded))
    return kept, removed


def deduplicate_publications(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), df.copy()

    def dedup_key(row: pd.Series) -> str:
        doi = normalize_text(row.get("doi", ""))
        if doi:
            return f"doi::{doi}"
        hal_id = normalize_text(row.get("hal_id", ""))
        if hal_id:
            return f"hal::{hal_id}"
        title = normalize_text(row.get("title", ""))
        year = str(row.get("year", ""))
        fa = normalize_name(row.get("first_author", ""))
        venue = normalize_text(row.get("venue", ""))
        return f"txt::{title[:120]}::{year}::{fa}::{venue[:80]}"

    tmp = df.copy()
    tmp["dedup_key"] = tmp.apply(dedup_key, axis=1)
    # Prefer records with DOI and full text, then keep first stable record.
    tmp["dedup_score"] = tmp["has_doi"].astype(int) + tmp["has_full_text"].astype(int)
    tmp = tmp.sort_values(["dedup_key", "dedup_score"], ascending=[True, False])
    unique = tmp.drop_duplicates(subset=["dedup_key"], keep="first").drop(columns=["dedup_score"])
    duplicated = tmp[tmp.duplicated(subset=["dedup_key"], keep="first")].drop(columns=["dedup_score"])
    logging.info("Deduplication: unique=%d duplicates_removed=%d", len(unique), len(duplicated))
    return unique.reset_index(drop=True), duplicated.reset_index(drop=True)


# -----------------------------------------------------------------------------
# Team member and author inference
# -----------------------------------------------------------------------------

def extract_authors(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        authors = row.get("authors_list", [])
        if not isinstance(authors, list):
            authors = [a.strip() for a in str(row.get("authors", "")).split("|") if a.strip()]
        for pos, author in enumerate(authors, start=1):
            rows.append({
                "hal_id": row.get("hal_id"),
                "year": row.get("year"),
                "title": row.get("title"),
                "author_name": author,
                "author_norm": normalize_name(author),
                "author_position": pos,
                "doc_type": row.get("doc_type"),
                "venue": row.get("venue"),
            })
    return pd.DataFrame(rows)


def retrieve_or_infer_team_members(df: pd.DataFrame, members_csv: Optional[Path], team_name: str) -> pd.DataFrame:
    members_manual = load_optional_csv(members_csv)
    authors_df = extract_authors(df)
    if authors_df.empty:
        return pd.DataFrame(columns=["author_name", "author_norm", "publication_count", "member_source", "member_confidence"])

    counts = authors_df.groupby(["author_norm", "author_name"], dropna=False).size().reset_index(name="publication_count")
    counts = counts.sort_values("publication_count", ascending=False)

    # Inference: recurrent authors in records retrieved from a team query are likely team members.
    # Conservative threshold: at least 2 publications or in manual CSV.
    inferred = counts[counts["publication_count"] >= 2].copy()
    inferred["member_source"] = "inferred_from_hal_recurrence"
    inferred["member_confidence"] = np.where(inferred["publication_count"] >= 4, "medium", "low")

    if not members_manual.empty and "author_name" in members_manual.columns:
        manual = members_manual.copy()
        manual["author_norm"] = manual["author_name"].map(normalize_name)
        manual_counts = counts[["author_norm", "publication_count"]].drop_duplicates("author_norm")
        manual = manual.merge(manual_counts, on="author_norm", how="left")
        manual["publication_count"] = manual["publication_count"].fillna(0).astype(int)
        manual["member_source"] = "manual_csv"
        manual["member_confidence"] = "manual"
        cols = ["author_name", "author_norm", "publication_count", "member_source", "member_confidence"]
        combined = pd.concat([manual[cols], inferred[cols]], ignore_index=True)
        combined = combined.sort_values(["member_source", "publication_count"], ascending=[True, False])
        combined = combined.drop_duplicates("author_norm", keep="first")
    else:
        combined = inferred[["author_name", "author_norm", "publication_count", "member_source", "member_confidence"]]

    if combined.empty:
        logging.warning("No team members could be inferred reliably. Author-based indicators will be partial.")
    else:
        logging.info("Team members: %d identified/inferred", len(combined))
    return combined.reset_index(drop=True)


def identify_acentauri_members(pub_df: pd.DataFrame, members_df: pd.DataFrame) -> pd.DataFrame:
    if pub_df.empty:
        return pub_df.copy()
    member_norms = set(members_df.get("author_norm", pd.Series(dtype=str)).dropna().astype(str))
    out = pub_df.copy()
    ac_authors_col = []
    ac_count_col = []
    for _, row in out.iterrows():
        authors = row.get("authors_list", [])
        if not isinstance(authors, list):
            authors = [a.strip() for a in str(row.get("authors", "")).split("|") if a.strip()]
        ac = [a for a in authors if normalize_name(a) in member_norms]
        ac_authors_col.append(" | ".join(ac))
        ac_count_col.append(len(ac))
    out["acentauri_authors"] = ac_authors_col
    out["acentauri_author_count"] = ac_count_col
    out["has_acentauri_author"] = out["acentauri_author_count"] > 0
    return out


# -----------------------------------------------------------------------------
# Thematic analysis
# -----------------------------------------------------------------------------

def assign_publications_to_themes_first_author(pub_df: pd.DataFrame, theme_df: pd.DataFrame) -> pd.DataFrame:
    mapping = dict(zip(theme_df.get("author_norm", []), theme_df.get("theme", [])))
    rows = []
    for _, row in pub_df.iterrows():
        authors = row.get("authors_list", [])
        if not isinstance(authors, list):
            authors = [a.strip() for a in str(row.get("authors", "")).split("|") if a.strip()]
        assigned_theme = UNASSIGNED
        assigned_author = ""
        for a in authors:
            an = normalize_name(a)
            if an in mapping:
                assigned_theme = mapping[an]
                assigned_author = a
                break
        rows.append({
            "hal_id": row.get("hal_id"),
            "year": row.get("year"),
            "title": row.get("title"),
            "theme_first_author": assigned_theme,
            "theme_first_author_source_author": assigned_author,
        })
    return pd.DataFrame(rows)


def assign_publications_to_themes_prorata(pub_df: pd.DataFrame, theme_df: pd.DataFrame) -> pd.DataFrame:
    mapping = dict(zip(theme_df.get("author_norm", []), theme_df.get("theme", [])))
    rows = []
    for _, row in pub_df.iterrows():
        authors = row.get("authors_list", [])
        if not isinstance(authors, list):
            authors = [a.strip() for a in str(row.get("authors", "")).split("|") if a.strip()]
        theme_counts: Counter = Counter()
        known_authors = []
        for a in authors:
            theme = mapping.get(normalize_name(a))
            if theme:
                theme_counts[theme] += 1
                known_authors.append(a)
        total_known = sum(theme_counts.values())
        base = {
            "hal_id": row.get("hal_id"),
            "year": row.get("year"),
            "title": row.get("title"),
            "known_thematic_authors": " | ".join(known_authors),
            "known_thematic_author_count": total_known,
            "theme_set": " | ".join(sorted(theme_counts)) if theme_counts else UNASSIGNED,
            "is_multi_theme": len(theme_counts) > 1,
        }
        all_themes = sorted(set(THEME_LABELS) | set(theme_df.get("theme", [])))
        for theme in all_themes:
            base[f"theme_prorata_{theme}"] = theme_counts.get(theme, 0) / total_known if total_known else 0.0
        rows.append(base)
    return pd.DataFrame(rows)


def compute_theme_statistics(pub_df: pd.DataFrame, theme_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if pub_df.empty:
        return {}
    first = assign_publications_to_themes_first_author(pub_df, theme_df)
    prorata = assign_publications_to_themes_prorata(pub_df, theme_df)
    merged = pub_df.merge(first, on=["hal_id", "year", "title"], how="left").merge(prorata, on=["hal_id", "year", "title"], how="left")

    first_stats = (
        merged.groupby("theme_first_author", dropna=False).size()
        .reset_index(name="publication_count")
        .sort_values("publication_count", ascending=False)
    )

    prorata_cols = [c for c in merged.columns if c.startswith("theme_prorata_")]
    prorata_stats = pd.DataFrame({
        "theme": [c.replace("theme_prorata_", "") for c in prorata_cols],
        "fractional_publication_count": [merged[c].sum() for c in prorata_cols],
    }).sort_values("fractional_publication_count", ascending=False)

    annual_rows = []
    for year, g in merged.groupby("year", dropna=True):
        for col in prorata_cols:
            annual_rows.append({
                "year": int(year),
                "theme": col.replace("theme_prorata_", ""),
                "fractional_publication_count": g[col].sum(),
            })
    annual_prorata = pd.DataFrame(annual_rows)

    # Theme co-presence matrix.
    themes = sorted(set([c.replace("theme_prorata_", "") for c in prorata_cols]))
    matrix = pd.DataFrame(0.0, index=themes, columns=themes)
    for _, row in merged.iterrows():
        present = [t for t in themes if row.get(f"theme_prorata_{t}", 0.0) > 0]
        for a in present:
            for b in present:
                matrix.loc[a, b] += 1.0
    matrix = matrix.reset_index().rename(columns={"index": "theme"})

    multitheme = pd.DataFrame({
        "indicator": ["mono_theme_publications", "multi_theme_publications", "unassigned_publications"],
        "value": [
            int((merged.get("theme_set", UNASSIGNED).astype(str).str.contains(r"\|") == False).sum() - (merged.get("theme_set", UNASSIGNED) == UNASSIGNED).sum()),
            int(merged.get("is_multi_theme", False).sum()),
            int((merged.get("theme_set", UNASSIGNED) == UNASSIGNED).sum()),
        ],
    })

    coverage = pd.DataFrame({
        "indicator": ["publications_with_known_thematic_author", "publications_without_known_thematic_author", "theme_mapping_author_rows"],
        "value": [
            int((merged.get("known_thematic_author_count", 0) > 0).sum()),
            int((merged.get("known_thematic_author_count", 0) == 0).sum()),
            int(len(theme_df)),
        ],
    })

    return {
        "publications_with_themes": merged,
        "theme_first_author_stats": first_stats,
        "theme_prorata_stats": prorata_stats,
        "theme_annual_prorata": annual_prorata,
        "theme_copresence_matrix": matrix,
        "theme_mono_multi_summary": multitheme,
        "theme_mapping_coverage": coverage,
    }


# -----------------------------------------------------------------------------
# Indicators
# -----------------------------------------------------------------------------

def compute_global_indicators(raw_df: pd.DataFrame, filtered_df: pd.DataFrame, unique_df: pd.DataFrame, removed_df: pd.DataFrame, duplicates_df: pd.DataFrame, members_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    author_pub = extract_authors(unique_df)
    if not author_pub.empty:
        author_stats = author_pub.groupby(["author_norm", "author_name"]).agg(
            publication_count=("hal_id", "nunique"),
            first_author_count=("author_position", lambda s: int((s == 1).sum())),
        ).reset_index().sort_values("publication_count", ascending=False)
    else:
        author_stats = pd.DataFrame(columns=["author_name", "publication_count", "first_author_count"])

    producing_members = 0
    if not members_df.empty and not author_pub.empty:
        pub_counts = author_pub.groupby("author_norm")["hal_id"].nunique()
        producing_members = int(sum(pub_counts.get(a, 0) > 0 for a in members_df["author_norm"]))

    member_count = int(len(members_df))
    unique_count = int(len(unique_df))
    summary = pd.DataFrame([
        {"indicator": "raw_hal_records", "value": int(len(raw_df)), "status": "verified_hal_metadata"},
        {"indicator": "records_removed_by_filtering", "value": int(len(removed_df)), "status": "computed"},
        {"indicator": "records_after_filtering", "value": int(len(filtered_df)), "status": "computed"},
        {"indicator": "duplicates_removed", "value": int(len(duplicates_df)), "status": "computed"},
        {"indicator": "unique_publications", "value": unique_count, "status": "computed"},
        {"indicator": "identified_or_inferred_members", "value": member_count, "status": "manual_or_inferred"},
        {"indicator": "producing_members", "value": producing_members, "status": "partial_if_member_list_inferred"},
        {"indicator": "producing_member_rate", "value": producing_members / member_count if member_count else np.nan, "status": "partial_if_member_list_inferred"},
        {"indicator": "average_publications_per_member", "value": unique_count / member_count if member_count else np.nan, "status": "partial_if_member_list_inferred"},
        {"indicator": "median_publications_per_author", "value": float(author_stats["publication_count"].median()) if not author_stats.empty else np.nan, "status": "computed"},
        {"indicator": "multi_author_publications", "value": int(sum(unique_df["authors_list"].map(lambda x: len(x) if isinstance(x, list) else 0) > 1)) if not unique_df.empty else 0, "status": "computed"},
    ])

    annual = unique_df.groupby("year", dropna=True).size().reset_index(name="publication_count") if not unique_df.empty else pd.DataFrame(columns=["year", "publication_count"])
    doc_type = unique_df.groupby("doc_type", dropna=False).size().reset_index(name="publication_count").sort_values("publication_count", ascending=False) if not unique_df.empty else pd.DataFrame(columns=["doc_type", "publication_count"])
    annual_doc_type = unique_df.groupby(["year", "doc_type"], dropna=False).size().reset_index(name="publication_count") if not unique_df.empty else pd.DataFrame(columns=["year", "doc_type", "publication_count"])

    return {
        "hceres_summary_indicators": summary,
        "author_statistics": author_stats,
        "annual_statistics": annual,
        "document_type_statistics": doc_type,
        "annual_document_type_statistics": annual_doc_type,
    }


def extract_affiliations(row: pd.Series) -> List[str]:
    fields = ["laboratories", "institutions", "structures", "author_structures", "research_teams"]
    values: List[str] = []
    for f in fields:
        for val in re.split(r"\s*\|\s*", str(row.get(f, ""))):
            val = val.strip()
            if val:
                values.append(val)
    # keep unique, preserve order
    return list(dict.fromkeys(values))


def normalize_laboratories_and_institutions(name: str) -> str:
    n = str(name).strip()
    n = re.sub(r"\s+", " ", n)
    return n


def classify_partner(name: str) -> str:
    n = normalize_text(name)
    if any(k in n for k in INDUSTRIAL_KEYWORDS):
        return "industrial_or_private"
    if any(k in n for k in ACADEMIC_KEYWORDS):
        return "academic_or_public_research"
    return "unknown"


def analyze_collaborations(pub_df: pd.DataFrame, team_name: str) -> Dict[str, pd.DataFrame]:
    partner_counter: Counter = Counter()
    country_counter: Counter = Counter()
    edge_counter: Counter = Counter()
    pub_partner_rows = []

    team_norm = normalize_text(team_name)
    for _, row in pub_df.iterrows():
        affiliations = [normalize_laboratories_and_institutions(a) for a in extract_affiliations(row)]
        external_affiliations = [a for a in affiliations if team_norm not in normalize_text(a)]
        countries = [c.strip() for c in re.split(r"\s*\|\s*", str(row.get("countries", ""))) if c.strip()]
        for aff in external_affiliations:
            partner_counter[aff] += 1
            edge_counter[(team_name, aff, "team_partner")] += 1
        for c in countries:
            country_counter[c] += 1
        pub_partner_rows.append({
            "hal_id": row.get("hal_id"),
            "title": row.get("title"),
            "year": row.get("year"),
            "external_partner_count": len(external_affiliations),
            "has_external_partner": len(external_affiliations) > 0,
            "external_partners": " | ".join(external_affiliations),
        })

    partner_stats = pd.DataFrame([
        {"partner": p, "publication_count": c, "partner_type_inferred": classify_partner(p), "status": "inferred_from_affiliation_strings"}
        for p, c in partner_counter.most_common()
    ])
    country_stats = pd.DataFrame([
        {"country": c, "publication_count": n, "status": "hal_metadata_if_available"}
        for c, n in country_counter.most_common()
    ])
    pub_partner_df = pd.DataFrame(pub_partner_rows)
    collab_summary = pd.DataFrame([
        {"indicator": "publications_with_external_partners", "value": int(pub_partner_df["has_external_partner"].sum()) if not pub_partner_df.empty else 0, "status": "approximate_from_affiliations"},
        {"indicator": "share_with_external_partners", "value": float(pub_partner_df["has_external_partner"].mean()) if not pub_partner_df.empty else np.nan, "status": "approximate_from_affiliations"},
        {"indicator": "distinct_external_partners", "value": int(len(partner_counter)), "status": "approximate_from_affiliations"},
        {"indicator": "distinct_countries", "value": int(len(country_counter)), "status": "hal_metadata_if_available"},
    ])
    edge_list = pd.DataFrame([
        {"source": s, "target": t, "weight": w, "relation_type": r}
        for (s, t, r), w in edge_counter.items()
    ]).sort_values("weight", ascending=False) if edge_counter else pd.DataFrame(columns=["source", "target", "weight", "relation_type"])

    return {
        "publication_partner_flags": pub_partner_df,
        "partner_laboratory_or_institution_ranking": partner_stats,
        "partner_country_ranking": country_stats,
        "collaboration_summary": collab_summary,
        "collaboration_edge_list": edge_list,
    }


def analyze_publication_venues(pub_df: pd.DataFrame, scimago_csv: Optional[Path], core_csv: Optional[Path]) -> Dict[str, pd.DataFrame]:
    if pub_df.empty:
        empty = pd.DataFrame()
        return {"venue_statistics": empty, "journal_statistics": empty, "conference_statistics": empty, "venue_enriched": empty, "venue_summary": empty}

    venue_stats = pub_df.groupby(["venue", "venue_type"], dropna=False).size().reset_index(name="publication_count")
    venue_stats = venue_stats.sort_values("publication_count", ascending=False)
    journal_stats = venue_stats[venue_stats["venue_type"] == "journal"].copy()
    conference_stats = venue_stats[venue_stats["venue_type"].isin(["conference", "proceedings"])].copy()

    venue_enriched = venue_stats.copy()
    venue_enriched["scimago_quartile"] = "not_provided"
    venue_enriched["core_rank"] = "not_provided"
    venue_enriched["enrichment_status"] = "not_enriched"

    scimago = load_optional_csv(scimago_csv) if scimago_csv else pd.DataFrame()
    if scimago.empty:
        logging.warning("Scimago data not provided: journal quartile enrichment skipped.")
    else:
        venue_enriched = enrich_with_scimago_quartiles(venue_enriched, scimago)

    core = load_optional_csv(core_csv) if core_csv else pd.DataFrame()
    if core.empty:
        logging.warning("CORE data not provided: conference rank enrichment skipped.")
    else:
        venue_enriched = enrich_with_core_ranks(venue_enriched, core)

    annual_venue_type = pub_df.groupby(["year", "venue_type"], dropna=False).size().reset_index(name="publication_count")
    summary = pd.DataFrame([
        {"indicator": "distinct_venues", "value": int((venue_stats["venue"].astype(str).str.len() > 0).sum()), "status": "computed"},
        {"indicator": "publications_without_clear_venue", "value": int((pub_df["venue"].astype(str).str.len() == 0).sum() + (pub_df["venue_type"] == "unknown").sum()), "status": "computed"},
        {"indicator": "journal_publications", "value": int((pub_df["venue_type"] == "journal").sum()), "status": "computed"},
        {"indicator": "conference_or_proceedings_publications", "value": int(pub_df["venue_type"].isin(["conference", "proceedings"]).sum()), "status": "computed"},
    ])

    return {
        "venue_statistics": venue_stats,
        "journal_statistics": journal_stats,
        "conference_statistics": conference_stats,
        "venue_enriched": venue_enriched,
        "annual_venue_type_statistics": annual_venue_type,
        "venue_summary": summary,
    }


def enrich_with_scimago_quartiles(venue_df: pd.DataFrame, scimago_df: pd.DataFrame) -> pd.DataFrame:
    out = venue_df.copy()
    title_cols = [c for c in scimago_df.columns if normalize_text(c) in {"title", "journal title", "journal", "source title"}]
    quartile_cols = [c for c in scimago_df.columns if "quartile" in normalize_text(c) or normalize_text(c) in {"sjr best quartile", "best quartile"}]
    if not title_cols or not quartile_cols:
        logging.warning("Scimago CSV format not recognized. Expected a title and quartile column.")
        return out
    title_col, quart_col = title_cols[0], quartile_cols[0]
    choices = scimago_df[title_col].dropna().astype(str).unique().tolist()
    lookup = {normalize_text(r[title_col]): r[quart_col] for _, r in scimago_df.iterrows() if pd.notna(r.get(title_col))}
    q_values = []
    statuses = []
    for _, r in out.iterrows():
        if r.get("venue_type") != "journal":
            q_values.append(out.loc[_, "scimago_quartile"] if "scimago_quartile" in out else "not_applicable")
            statuses.append("not_applicable")
            continue
        match = approximate_match(str(r.get("venue", "")), choices, cutoff=0.86)
        if match:
            q_values.append(lookup.get(normalize_text(match), "unknown"))
            statuses.append("scimago_approximate_match")
        else:
            q_values.append("unknown")
            statuses.append("scimago_no_match")
    out["scimago_quartile"] = q_values
    out["enrichment_status"] = statuses
    return out


def enrich_with_core_ranks(venue_df: pd.DataFrame, core_df: pd.DataFrame) -> pd.DataFrame:
    out = venue_df.copy()
    title_cols = [c for c in core_df.columns if normalize_text(c) in {"title", "conference", "conference name", "name", "acronym"}]
    rank_cols = [c for c in core_df.columns if "rank" in normalize_text(c)]
    if not title_cols or not rank_cols:
        logging.warning("CORE CSV format not recognized. Expected a conference/name and rank column.")
        return out
    title_col, rank_col = title_cols[0], rank_cols[0]
    choices = core_df[title_col].dropna().astype(str).unique().tolist()
    lookup = {normalize_text(r[title_col]): r[rank_col] for _, r in core_df.iterrows() if pd.notna(r.get(title_col))}
    ranks = []
    statuses = []
    for _, r in out.iterrows():
        if r.get("venue_type") not in {"conference", "proceedings"}:
            ranks.append(out.loc[_, "core_rank"] if "core_rank" in out else "not_applicable")
            statuses.append("not_applicable")
            continue
        match = approximate_match(str(r.get("venue", "")), choices, cutoff=0.82)
        if match:
            ranks.append(lookup.get(normalize_text(match), "unknown"))
            statuses.append("core_approximate_match")
        else:
            ranks.append("unknown")
            statuses.append("core_no_match")
    out["core_rank"] = ranks
    out["core_enrichment_status"] = statuses
    return out


def compute_open_science_indicators(pub_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if pub_df.empty:
        return {"open_science_statistics": pd.DataFrame(), "annual_full_text_statistics": pd.DataFrame(), "language_statistics": pd.DataFrame()}
    total = len(pub_df)
    full_text = int(pub_df["has_full_text"].sum())
    doi = int(pub_df["has_doi"].sum())
    lang_counts = pub_df["language"].fillna(UNKNOWN).replace("", UNKNOWN).value_counts().reset_index()
    lang_counts.columns = ["language", "publication_count"]
    annual_full = pub_df.groupby("year", dropna=True).agg(
        publication_count=("hal_id", "nunique"),
        full_text_count=("has_full_text", "sum"),
        doi_count=("has_doi", "sum"),
    ).reset_index()
    annual_full["full_text_share"] = annual_full["full_text_count"] / annual_full["publication_count"].replace(0, np.nan)
    stats = pd.DataFrame([
        {"indicator": "publications_with_full_text_in_hal", "value": full_text, "share": full_text / total if total else np.nan, "status": "hal_metadata"},
        {"indicator": "publications_without_full_text_in_hal", "value": total - full_text, "share": (total - full_text) / total if total else np.nan, "status": "hal_metadata"},
        {"indicator": "publications_with_doi", "value": doi, "share": doi / total if total else np.nan, "status": "hal_metadata"},
        {"indicator": "publications_without_doi", "value": total - doi, "share": (total - doi) / total if total else np.nan, "status": "hal_metadata"},
        {"indicator": "english_publications", "value": int(pub_df["language"].astype(str).str.lower().str.contains("en|eng|anglais").sum()), "share": np.nan, "status": "approximate_language_metadata"},
        {"indicator": "french_publications", "value": int(pub_df["language"].astype(str).str.lower().str.contains("fr|fre|fra|fran").sum()), "share": np.nan, "status": "approximate_language_metadata"},
    ])
    return {
        "open_science_statistics": stats,
        "annual_full_text_statistics": annual_full,
        "language_statistics": lang_counts,
    }


# -----------------------------------------------------------------------------
# Figures and reports
# -----------------------------------------------------------------------------

def plot_bar(df: pd.DataFrame, x: str, y: str, path: Path, title: str, rotation: int = 45) -> None:
    if plt is None or df.empty or x not in df.columns or y not in df.columns:
        return
    fig = plt.figure(figsize=(9, 5))
    plt.bar(df[x].astype(str), df[y].astype(float))
    plt.title(title)
    plt.xlabel(x.replace("_", " "))
    plt.ylabel(y.replace("_", " "))
    plt.xticks(rotation=rotation, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    logging.info("Wrote figure %s", path)


def plot_stacked_or_lines(df: pd.DataFrame, index_col: str, category_col: str, value_col: str, path: Path, title: str, kind: str = "bar") -> None:
    if plt is None or df.empty:
        return
    try:
        pivot = df.pivot_table(index=index_col, columns=category_col, values=value_col, aggfunc="sum", fill_value=0)
        fig = plt.figure(figsize=(9, 5))
        if kind == "line":
            pivot.plot(marker="o", ax=plt.gca())
        else:
            pivot.plot(kind="bar", stacked=True, ax=plt.gca())
        plt.title(title)
        plt.xlabel(index_col.replace("_", " "))
        plt.ylabel(value_col.replace("_", " "))
        plt.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)
        logging.info("Wrote figure %s", path)
    except Exception as exc:
        logging.warning("Could not generate figure %s: %s", path, exc)


def plot_matrix(matrix_df: pd.DataFrame, path: Path, title: str) -> None:
    if plt is None or matrix_df.empty:
        return
    try:
        idx = matrix_df.iloc[:, 0].astype(str).tolist()
        mat = matrix_df.drop(columns=[matrix_df.columns[0]]).astype(float).values
        fig = plt.figure(figsize=(7, 6))
        plt.imshow(mat, aspect="auto")
        plt.title(title)
        plt.xticks(range(len(idx)), idx, rotation=45, ha="right")
        plt.yticks(range(len(idx)), idx)
        plt.colorbar(label="count")
        plt.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)
        logging.info("Wrote figure %s", path)
    except Exception as exc:
        logging.warning("Could not generate matrix figure %s: %s", path, exc)


def generate_figures(outputs: Dict[str, Path], tables: Dict[str, pd.DataFrame]) -> None:
    fig_dir = outputs["figures"]
    plot_bar(tables.get("annual_statistics", pd.DataFrame()), "year", "publication_count", fig_dir / "publications_per_year.png", "Publications per year", rotation=0)
    plot_bar(tables.get("document_type_statistics", pd.DataFrame()), "doc_type", "publication_count", fig_dir / "publication_type_distribution.png", "Publication type distribution")
    plot_stacked_or_lines(tables.get("theme_annual_prorata", pd.DataFrame()), "year", "theme", "fractional_publication_count", fig_dir / "publications_by_theme_over_time.png", "Publications by theme over time", kind="line")
    plot_bar(tables.get("theme_prorata_stats", pd.DataFrame()), "theme", "fractional_publication_count", fig_dir / "theme_prorata_distribution.png", "Theme distribution, prorata", rotation=0)
    plot_matrix(tables.get("theme_copresence_matrix", pd.DataFrame()), fig_dir / "theme_copresence_matrix.png", "Theme co-presence matrix")
    partners = tables.get("partner_laboratory_or_institution_ranking", pd.DataFrame()).head(15)
    if not partners.empty:
        plot_bar(partners, "partner", "publication_count", fig_dir / "top_partner_institutions.png", "Top partner institutions")
    venues = tables.get("venue_statistics", pd.DataFrame()).head(15)
    if not venues.empty:
        plot_bar(venues, "venue", "publication_count", fig_dir / "top_venues.png", "Top venues")
    annual_full = tables.get("annual_full_text_statistics", pd.DataFrame())
    if not annual_full.empty:
        plot_bar(annual_full, "year", "full_text_share", fig_dir / "full_text_availability_over_time.png", "Full-text availability over time", rotation=0)


def export_csv_tables(outputs: Dict[str, Path], tables: Dict[str, pd.DataFrame]) -> None:
    for name, df in tables.items():
        if isinstance(df, pd.DataFrame):
            save_df(df, outputs["tables"] / f"{name}.csv")


def export_latex_tables(outputs: Dict[str, Path], tables: Dict[str, pd.DataFrame]) -> None:
    latex_targets = {
        "hceres_summary_indicators": ("Global production summary", "tab:hceres_summary"),
        "annual_statistics": ("Annual publication count", "tab:annual_publications"),
        "document_type_statistics": ("Publication types", "tab:publication_types"),
        "author_statistics": ("Top authors", "tab:top_authors"),
        "theme_prorata_stats": ("Theme distribution", "tab:theme_distribution"),
        "theme_first_author_stats": ("Theme distribution by first team author", "tab:theme_first_author"),
        "theme_mapping_coverage": ("Theme mapping coverage", "tab:theme_mapping_coverage"),
        "collaboration_summary": ("Collaboration summary", "tab:collaboration_summary"),
        "partner_laboratory_or_institution_ranking": ("Top partner laboratories and institutions", "tab:partner_ranking"),
        "partner_country_ranking": ("Partner country ranking", "tab:partner_country_ranking"),
        "venue_statistics": ("Top publication venues", "tab:top_venues"),
        "annual_venue_type_statistics": ("Annual venue type statistics", "tab:annual_venue_type_statistics"),
        "open_science_statistics": ("Open science indicators", "tab:open_science"),
        "annual_full_text_statistics": ("Annual full-text availability", "tab:annual_full_text_statistics"),
    }
    for name, (caption, label) in latex_targets.items():
        df = tables.get(name)
        if isinstance(df, pd.DataFrame) and not df.empty:
            # Keep LaTeX tables readable.
            display_df = df.head(30).copy()
            save_latex(display_df, outputs["latex"] / f"{name}.tex", caption=caption, label=label)


def generate_markdown_or_text_report(outputs: Dict[str, Path], args: argparse.Namespace, discovery: DiscoveryResult, tables: Dict[str, pd.DataFrame]) -> None:
    summary = tables.get("hceres_summary_indicators", pd.DataFrame())
    open_stats = tables.get("open_science_statistics", pd.DataFrame())
    theme_cov = tables.get("theme_mapping_coverage", pd.DataFrame())
    top_authors = tables.get("author_statistics", pd.DataFrame()).head(10)
    top_venues = tables.get("venue_statistics", pd.DataFrame()).head(10)
    partners = tables.get("partner_laboratory_or_institution_ranking", pd.DataFrame()).head(10)

    def metric(name: str) -> str:
        if summary.empty:
            return "unknown"
        r = summary[summary["indicator"] == name]
        if r.empty:
            return "unknown"
        v = r.iloc[0]["value"]
        if pd.isna(v):
            return "unknown"
        if isinstance(v, float):
            return f"{v:.3g}"
        return str(v)

    lines = []
    lines.append(f"# HAL/HCERES Bibliometric POC — {args.team}\n")
    lines.append("## Scope\n")
    lines.append(f"- Team: **{args.team}**")
    lines.append(f"- Period: **{args.start_year}–{args.end_year}**")
    lines.append(f"- HAL query: `{discovery.query}`")
    lines.append(f"- Query source/confidence: **{discovery.source} / {discovery.confidence}**")
    if discovery.structure_id:
        lines.append(f"- Discovered/used HAL structure id: **{discovery.structure_id}**")
    if discovery.warnings:
        lines.append("- Discovery warnings: " + "; ".join(discovery.warnings))
    lines.append("")

    lines.append("## Main production indicators\n")
    lines.append(f"- Raw HAL records retrieved: **{metric('raw_hal_records')}**")
    lines.append(f"- Records after filtering: **{metric('records_after_filtering')}**")
    lines.append(f"- Duplicates removed: **{metric('duplicates_removed')}**")
    lines.append(f"- Unique publications retained: **{metric('unique_publications')}**")
    lines.append(f"- Identified or inferred members: **{metric('identified_or_inferred_members')}**")
    lines.append(f"- Producing member rate: **{metric('producing_member_rate')}**")
    lines.append("")

    lines.append("## Top authors\n")
    if top_authors.empty:
        lines.append("No author ranking available.")
    else:
        for _, r in top_authors.iterrows():
            lines.append(f"- {r.get('author_name')}: {r.get('publication_count')} publications")
    lines.append("")

    lines.append("## Thematic analysis\n")
    if theme_cov.empty:
        lines.append("No theme coverage table available. ARC/RIC/MOC results are likely incomplete unless a mapping CSV was provided.")
    else:
        for _, r in theme_cov.iterrows():
            lines.append(f"- {r.get('indicator')}: {r.get('value')}")
    lines.append("The report distinguishes between publications assigned through known author-theme mappings and unassigned publications. The script does not invent the meaning of ARC/RIC/MOC when public metadata is insufficient.")
    lines.append("")

    lines.append("## Collaboration patterns\n")
    if partners.empty:
        lines.append("No partner ranking available. Affiliation metadata may be incomplete.")
    else:
        for _, r in partners.iterrows():
            lines.append(f"- {r.get('partner')}: {r.get('publication_count')} publications ({r.get('partner_type_inferred')})")
    lines.append("")

    lines.append("## Publication venues\n")
    if top_venues.empty:
        lines.append("No clear venue statistics available.")
    else:
        for _, r in top_venues.iterrows():
            venue = r.get("venue") or "unknown venue"
            lines.append(f"- {venue}: {r.get('publication_count')} publications ({r.get('venue_type')})")
    lines.append("")

    lines.append("## Open science indicators\n")
    if open_stats.empty:
        lines.append("No open science statistics available.")
    else:
        for _, r in open_stats.iterrows():
            value = r.get("value")
            share = r.get("share")
            if pd.notna(share):
                lines.append(f"- {r.get('indicator')}: {value} ({share:.1%}) [{r.get('status')}]")
            else:
                lines.append(f"- {r.get('indicator')}: {value} [{r.get('status')}]")
    lines.append("")

    lines.append("## Limitations and validation needs\n")
    lines.append("- HAL metadata can be incomplete or heterogeneous across records.")
    lines.append("- The inferred member list is only a heuristic unless `acentauri_members.csv` is provided.")
    lines.append("- Theme attribution is reliable only for authors present in the theme mapping CSV or otherwise discoverable from metadata.")
    lines.append("- Partner classification as academic/industrial is approximate and based on organization-name heuristics.")
    lines.append("- Scimago and CORE enrichments are skipped unless external CSV files are provided.")
    lines.append("- Internationalization indicators are partial when country metadata is missing.")
    lines.append("")

    path = outputs["reports"] / "hceres_summary_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logging.info("Wrote report %s", path)




# -----------------------------------------------------------------------------
# Deterministic template-based LaTeX report generation
# -----------------------------------------------------------------------------

def latex_escape_text(text: Any) -> str:
    """Escape plain text for safe insertion in LaTeX."""
    value = "" if text is None else str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def latex_format_value(value: Any) -> str:
    """Format scalar values for narrative LaTeX text."""
    if value is None:
        return "unknown"
    try:
        if pd.isna(value):
            return "unknown"
    except Exception:
        pass
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)):
            return "unknown"
        # Percent-like shares are already stored as [0, 1] in some tables.
        if 0 <= float(value) <= 1:
            return f"{float(value):.1%}"
        return f"{float(value):.3g}"
    return latex_escape_text(value)


def get_summary_metric(summary: pd.DataFrame, name: str, default: str = "unknown") -> str:
    """Read one indicator from hceres_summary_indicators."""
    if summary is None or summary.empty:
        return default
    if "indicator" not in summary.columns or "value" not in summary.columns:
        return default
    rows = summary.loc[summary["indicator"].astype(str) == name, "value"]
    if rows.empty:
        return default
    return latex_format_value(rows.iloc[0])


def get_open_science_metric(open_stats: pd.DataFrame, name: str, default: str = "unknown") -> str:
    """Read one indicator from open_science_statistics, preferring share if available."""
    if open_stats is None or open_stats.empty or "indicator" not in open_stats.columns:
        return default
    row = open_stats.loc[open_stats["indicator"].astype(str) == name]
    if row.empty:
        return default
    r = row.iloc[0]
    if "share" in row.columns and pd.notna(r.get("share")):
        return latex_format_value(r.get("share"))
    if "value" in row.columns:
        return latex_format_value(r.get("value"))
    return default


def table_exists(outputs: Dict[str, Path], table_name: str) -> bool:
    return (outputs["latex"] / f"{table_name}.tex").exists()


def figure_exists(outputs: Dict[str, Path], figure_name: str) -> bool:
    return (outputs["figures"] / figure_name).exists()


def latex_table_block(outputs: Dict[str, Path], table_name: str, caption: str, label: str) -> str:
    """Return a safe LaTeX block for an exported table, or a small warning paragraph."""
    caption_e = latex_escape_text(caption)
    label_e = latex_escape_text(label)
    rel_path = f"../latex/{table_name}.tex"
    if table_exists(outputs, table_name):
        return rf"""
\begin{{table}}[H]
\centering
\caption{{{caption_e}}}
\label{{{label_e}}}
\resizebox{{\textwidth}}{{!}}{{\input{{{rel_path}}}}}
\end{{table}}
""".strip()
    return rf"\paragraph{{Table indisponible.}} Le tableau \texttt{{{latex_escape_text(table_name)}.tex}} n'a pas été généré, probablement parce que les métadonnées correspondantes sont absentes ou vides."


def latex_figure_block(outputs: Dict[str, Path], figure_name: str, caption: str, label: str, width: str = "0.82\\textwidth") -> str:
    """Return a safe LaTeX block for an exported figure, or a short warning paragraph."""
    caption_e = latex_escape_text(caption)
    label_e = latex_escape_text(label)
    rel_path = f"../figures/{figure_name}"
    if figure_exists(outputs, figure_name):
        return rf"""
\begin{{figure}}[H]
\centering
\includegraphics[width={width}]{{{rel_path}}}
\caption{{{caption_e}}}
\label{{{label_e}}}
\end{{figure}}
""".strip()
    return rf"\paragraph{{Figure indisponible.}} La figure \texttt{{{latex_escape_text(figure_name)}}} n'a pas été générée, probablement faute de données exploitables."


def compact_table_comment(df: pd.DataFrame, value_col: str, label_col: str, top_n: int = 3) -> str:
    """Create a short deterministic comment about top rows of a table."""
    if df is None or df.empty or value_col not in df.columns or label_col not in df.columns:
        return "Les données disponibles ne permettent pas d'identifier un classement robuste."
    work = df[[label_col, value_col]].dropna().copy().head(top_n)
    if work.empty:
        return "Les données disponibles ne permettent pas d'identifier un classement robuste."
    items = []
    for _, r in work.iterrows():
        label = latex_escape_text(r[label_col])
        value = latex_format_value(r[value_col])
        items.append(f"{label} ({value})")
    return "Les premières entrées du classement sont : " + ", ".join(items) + "."


def build_deterministic_latex_body(
    outputs: Dict[str, Path],
    args: argparse.Namespace,
    discovery: DiscoveryResult,
    tables: Dict[str, pd.DataFrame],
) -> str:
    """Build the LaTeX body with deterministic template logic only."""
    summary = tables.get("hceres_summary_indicators", pd.DataFrame())
    annual = tables.get("annual_statistics", pd.DataFrame())
    doc_types = tables.get("document_type_statistics", pd.DataFrame())
    authors = tables.get("author_statistics", pd.DataFrame())
    theme_cov = tables.get("theme_mapping_coverage", pd.DataFrame())
    theme_prorata = tables.get("theme_prorata_stats", pd.DataFrame())
    collaboration = tables.get("collaboration_summary", pd.DataFrame())
    partners = tables.get("partner_laboratory_or_institution_ranking", pd.DataFrame())
    countries = tables.get("partner_country_ranking", pd.DataFrame())
    venues = tables.get("venue_statistics", pd.DataFrame())
    open_stats = tables.get("open_science_statistics", pd.DataFrame())

    team = latex_escape_text(args.team)
    period = f"{args.start_year}--{args.end_year}"
    query = latex_escape_text(discovery.query)
    source = latex_escape_text(discovery.source)
    confidence = latex_escape_text(discovery.confidence)
    warnings_text = latex_escape_text("; ".join(discovery.warnings or [])) if discovery.warnings else "Aucun avertissement spécifique lors de la découverte de la requête."

    raw_records = get_summary_metric(summary, "raw_hal_records")
    after_filtering = get_summary_metric(summary, "records_after_filtering")
    duplicates_removed = get_summary_metric(summary, "duplicates_removed")
    unique_publications = get_summary_metric(summary, "unique_publications")
    members = get_summary_metric(summary, "identified_or_inferred_members")
    producing_rate = get_summary_metric(summary, "producing_member_rate")
    avg_pub = get_summary_metric(summary, "average_publications_per_member")
    med_pub = get_summary_metric(summary, "median_publications_per_member")
    multi_author_share = get_summary_metric(summary, "multi_author_publication_share")
    external_share = get_summary_metric(summary, "external_partner_publication_share")

    full_text_share = get_open_science_metric(open_stats, "publications_with_full_text")
    doi_share = get_open_science_metric(open_stats, "publications_with_doi")
    english_share = get_open_science_metric(open_stats, "english_publications")
    french_share = get_open_science_metric(open_stats, "french_publications")

    if annual is not None and not annual.empty and "year" in annual.columns:
        years = ", ".join(latex_escape_text(y) for y in annual["year"].astype(str).tolist())
        annual_comment = f"La série annuelle exploitable couvre les années {years}. Les variations annuelles doivent être interprétées en tenant compte de l'éventuelle incomplétude de HAL pour l'année courante ou les dépôts tardifs."
    else:
        annual_comment = "La distribution annuelle n'a pas pu être reconstruite de manière fiable à partir des métadonnées disponibles."

    doc_type_comment = compact_table_comment(doc_types, "publication_count", "doc_type", top_n=4)
    author_comment = compact_table_comment(authors, "publication_count", "author_name", top_n=5)
    partner_comment = compact_table_comment(partners, "publication_count", "partner", top_n=5)
    country_comment = compact_table_comment(countries, "publication_count", "country", top_n=5)
    venue_comment = compact_table_comment(venues, "publication_count", "venue", top_n=5)

    if theme_cov is None or theme_cov.empty:
        theme_coverage_comment = "Aucun tableau de couverture thématique n'a été généré. L'attribution ARC/RIC/MOC doit donc être considérée comme non disponible ou très partielle."
    else:
        cov_lines = []
        for _, r in theme_cov.iterrows():
            cov_lines.append(f"{latex_escape_text(r.get('indicator'))}: {latex_format_value(r.get('value'))}")
        theme_coverage_comment = "La couverture de la cartographie thématique est la suivante : " + "; ".join(cov_lines) + "."

    if theme_prorata is None or theme_prorata.empty:
        theme_comment = "La distribution par thème n'est pas suffisamment documentée. Le script ne déduit pas le sens des acronymes ARC, RIC et MOC lorsqu'il n'est pas présent dans les données ou dans un fichier de configuration."
    else:
        theme_comment = compact_table_comment(theme_prorata, "fractional_publication_count", "theme", top_n=5)

    if collaboration is None or collaboration.empty:
        collaboration_comment = "Les indicateurs synthétiques de collaboration sont indisponibles ou incomplets."
    else:
        items = []
        for _, r in collaboration.iterrows():
            items.append(f"{latex_escape_text(r.get('indicator'))}: {latex_format_value(r.get('value'))}")
        collaboration_comment = "Synthèse des collaborations : " + "; ".join(items[:8]) + "."

    return rf"""
\section{{Analyse bibliométrique de l'équipe {team}}}

\subsection{{Périmètre, sources et méthode}}

Ce rapport constitue une version de travail automatiquement générée pour appuyer la préparation d'une évaluation de type HCERES de l'équipe {team} sur la période {period}. L'analyse repose sur les métadonnées HAL récupérées par le pipeline local, puis sur des traitements déterministes : filtrage des types de documents, déduplication, extraction des auteurs et affiliations, calcul d'indicateurs, analyse thématique lorsque la cartographie est disponible, analyse des collaborations, analyse des supports de publication et indicateurs de science ouverte.

La requête HAL utilisée est \texttt{{{query}}}. Sa source est \texttt{{{source}}} avec une confiance déclarée \texttt{{{confidence}}}. Les avertissements associés à la découverte automatique sont : {warnings_text}

Le rapport distingue trois niveaux d'information : les métadonnées directement récupérées dans HAL, les informations inférées par heuristique, et les enrichissements éventuellement fournis par fichiers CSV optionnels. Les indicateurs fondés sur des heuristiques ou des métadonnées incomplètes doivent être validés manuellement avant intégration dans un document institutionnel.

{latex_table_block(outputs, "hceres_summary_indicators", "Synthèse globale des indicateurs HCERES", "tab:hceres_summary")}

\subsection{{Production scientifique globale}}

Le pipeline a récupéré {raw_records} notices HAL brutes. Après filtrage des types de documents exclus, {after_filtering} notices restent exploitables avant déduplication. Le nombre final de publications uniques retenues est {unique_publications}. Le nombre de doublons supprimés est {duplicates_removed}.

La liste de membres identifiés ou inférés contient {members} personnes. Le taux de membres produisants estimé est {producing_rate}. Le nombre moyen de publications par membre est {avg_pub}, et la médiane est {med_pub}. Ces valeurs dépendent de la qualité des métadonnées auteurs et de la complétude de la liste de membres.

{author_comment}

{latex_table_block(outputs, "annual_statistics", "Évolution annuelle du nombre de publications", "tab:annual_statistics")}

{latex_figure_block(outputs, "publications_per_year.png", "Nombre de publications par année", "fig:publications_per_year")}

{annual_comment}

\subsection{{Répartition par type de document}}

La répartition par type de document permet de distinguer articles de revues, conférences, workshops, chapitres, actes et autres catégories présentes dans HAL. {doc_type_comment}

{latex_table_block(outputs, "document_type_statistics", "Répartition des publications par type de document", "tab:document_type_statistics")}

{latex_figure_block(outputs, "publication_type_distribution.png", "Distribution des publications par type de document", "fig:publication_type_distribution")}

\subsection{{Analyse thématique}}

L'analyse thématique repose sur les labels internes disponibles, notamment ARC, RIC et MOC lorsque la cartographie auteur--thème est fournie ou inférable. Le script ne force pas d'interprétation sémantique des acronymes lorsque les sources publiques ou les fichiers de configuration ne permettent pas de l'établir de manière fiable.

{theme_coverage_comment}

{theme_comment}

Deux méthodes sont distinguées : l'attribution au premier auteur identifié de l'équipe et l'attribution prorata entre les thèmes des auteurs identifiés. La première méthode donne une lecture simple, mais peut sous-estimer les contributions transverses ; la seconde décrit mieux les co-publications inter-thèmes, mais dépend davantage de la complétude de la cartographie.

{latex_table_block(outputs, "theme_prorata_stats", "Distribution thématique par attribution prorata", "tab:theme_prorata_stats")}

{latex_table_block(outputs, "theme_first_author_stats", "Distribution thématique par premier auteur identifié", "tab:theme_first_author_stats")}

{latex_table_block(outputs, "theme_mapping_coverage", "Couverture de la cartographie thématique", "tab:theme_mapping_coverage")}

{latex_figure_block(outputs, "publications_by_theme_over_time.png", "Évolution temporelle des publications par thème", "fig:publications_by_theme_over_time")}

{latex_figure_block(outputs, "theme_prorata_distribution.png", "Distribution thématique par attribution prorata", "fig:theme_prorata_distribution")}

{latex_figure_block(outputs, "theme_copresence_matrix.png", "Matrice de coprésence des thèmes", "fig:theme_copresence_matrix")}

\subsection{{Collaborations scientifiques}}

La part de publications multi-auteurs est estimée à {multi_author_share}. La part de publications impliquant au moins un partenaire externe est estimée à {external_share}. Ces indicateurs sont calculés à partir des auteurs et affiliations disponibles, avec une normalisation heuristique des laboratoires, institutions et pays.

{collaboration_comment}

{partner_comment}

{country_comment}

{latex_table_block(outputs, "collaboration_summary", "Synthèse des collaborations", "tab:collaboration_summary")}

{latex_table_block(outputs, "partner_laboratory_or_institution_ranking", "Principaux partenaires institutionnels ou laboratoires", "tab:partner_ranking")}

{latex_table_block(outputs, "partner_country_ranking", "Répartition par pays lorsque disponible", "tab:partner_country_ranking")}

{latex_figure_block(outputs, "top_partner_institutions.png", "Principales institutions partenaires", "fig:top_partner_institutions")}

\subsection{{Supports de publication}}

L'analyse des supports de publication agrège les informations de journaux, conférences, proceedings, workshops, éditeurs et lieux de publication lorsque ces champs sont disponibles dans HAL. {venue_comment}

Les enrichissements Scimago et CORE sont optionnels. Si les fichiers correspondants sont absents, le script conserve l'analyse des supports mais marque les quartiles ou rangs comme indisponibles.

{latex_table_block(outputs, "venue_statistics", "Principaux supports de publication", "tab:venue_statistics")}

{latex_table_block(outputs, "annual_venue_type_statistics", "Évolution annuelle des types de supports", "tab:annual_venue_type_statistics")}

{latex_figure_block(outputs, "top_venues.png", "Supports de publication les plus fréquents", "fig:top_venues")}

\subsection{{Science ouverte et internationalisation}}

La part de publications avec texte intégral disponible dans HAL est estimée à {full_text_share}. La part de publications disposant d'un DOI est estimée à {doi_share}. La part de publications en anglais est estimée à {english_share}, tandis que la part de publications en français est estimée à {french_share}. Ces statistiques sont calculées uniquement à partir des champs disponibles dans HAL.

Les indicateurs d'internationalisation reposent principalement sur les pays associés aux affiliations. Lorsque ces champs sont absents ou hétérogènes, les résultats doivent être considérés comme partiels.

{latex_table_block(outputs, "open_science_statistics", "Indicateurs de science ouverte", "tab:open_science_statistics")}

{latex_table_block(outputs, "annual_full_text_statistics", "Évolution annuelle de la disponibilité du texte intégral", "tab:annual_full_text_statistics")}

{latex_figure_block(outputs, "full_text_availability_over_time.png", "Disponibilité du texte intégral dans HAL au cours du temps", "fig:full_text_availability_over_time")}

\subsection{{Limites de l'analyse automatique}}

\begin{{itemize}}
    \item La complétude du périmètre dépend de la requête HAL ou de l'identifiant de structure utilisé.
    \item Les noms d'auteurs, affiliations, laboratoires et institutions peuvent être hétérogènes entre notices.
    \item Certaines publications peuvent manquer de DOI, de support de publication, de langue, de pays ou de fichier texte intégral.
    \item La liste des membres est inférée si aucun fichier \texttt{{acentauri\_members.csv}} n'est fourni.
    \item L'attribution ARC/RIC/MOC est fiable seulement pour les auteurs couverts par une cartographie explicite ou inférable.
    \item La classification académique ou industrielle des partenaires repose sur des heuristiques lexicales.
    \item Les enrichissements Scimago et CORE sont absents si les fichiers optionnels ne sont pas fournis.
\end{{itemize}}

\subsection{{Synthèse HCERES}}

Ce pipeline fournit une base reproductible pour objectiver la production scientifique de l'équipe {team} sur la période {period}. Il permet d'obtenir un premier niveau d'analyse sur le volume de publications, la dynamique annuelle, les types de documents, les auteurs récurrents, les collaborations, les supports de publication, la science ouverte et, lorsque les données le permettent, la structuration thématique interne.

Cette version doit être considérée comme un outil de pré-analyse. Les points à valider avant usage institutionnel sont le périmètre HAL, la liste des membres, la cartographie thématique, les affiliations partenaires, les supports de publication et les éventuels classements externes.
""".strip()


def build_standalone_deterministic_latex_report(latex_body: str, args: argparse.Namespace) -> str:
    """Wrap the deterministic LaTeX body in a compilable document."""
    title = latex_escape_text(f"Rapport bibliométrique HAL/HCERES — {args.team}")
    period = latex_escape_text(f"Période {args.start_year}--{args.end_year}")
    return rf"""\documentclass[11pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage[french]{{babel}}
\usepackage{{lmodern}}
\usepackage{{geometry}}
\usepackage{{graphicx}}
\usepackage{{booktabs}}
\usepackage{{longtable}}
\usepackage{{array}}
\usepackage{{float}}
\usepackage{{hyperref}}
\geometry{{margin=2.5cm}}

\title{{{title}}}
\author{{Génération automatique déterministe à partir des métadonnées HAL}}
\date{{{period}}}

\begin{{document}}
\maketitle

\begin{{center}}
\emph{{Version de travail générée automatiquement. Les indicateurs inférés ou incomplets doivent être validés manuellement avant usage institutionnel.}}
\end{{center}}

{latex_body}

\end{{document}}
"""


def generate_deterministic_latex_report(
    outputs: Dict[str, Path],
    args: argparse.Namespace,
    discovery: DiscoveryResult,
    tables: Dict[str, pd.DataFrame],
) -> None:
    """
    Generate an HCERES-oriented LaTeX report without any external AI API.

    The report is template-based, free, local, and reproducible. It uses only the
    deterministic tables and figures already produced by the pipeline.
    """
    latex_body = build_deterministic_latex_body(outputs, args, discovery, tables)

    body_path = outputs["reports"] / "hceres_deterministic_report_body.tex"
    body_path.write_text(latex_body, encoding="utf-8")
    logging.info("Wrote deterministic LaTeX body: %s", body_path)

    standalone = build_standalone_deterministic_latex_report(latex_body, args)
    standalone_path = outputs["reports"] / "hceres_deterministic_report_standalone.tex"
    standalone_path.write_text(standalone, encoding="utf-8")
    logging.info("Wrote standalone deterministic LaTeX report: %s", standalone_path)


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monolithic HAL bibliometric POC for ACENTAURI / HCERES.")
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("--team", type=str, default=DEFAULT_TEAM_NAME)
    parser.add_argument("--hal-query", type=str, default=None, help="Explicit HAL query override, e.g. 'structId_i:123456'.")
    parser.add_argument("--hal-structure-id", type=int, default=None, help="Explicit HAL structure id override.")
    parser.add_argument("--members-csv", type=Path, default=Path("data/acentauri_members.csv"))
    parser.add_argument("--theme-mapping", type=Path, default=Path("data/theme_mapping.csv"))
    parser.add_argument("--scimago-csv", type=Path, default=Path("data/scimago_journals.csv"))
    parser.add_argument("--core-csv", type=Path, default=Path("data/core_conferences.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--include-doc-types", type=str, default="", help="Comma-separated doc types to force-include.")
    parser.add_argument("--exclude-doc-types", type=str, default=",".join(sorted(DEFAULT_EXCLUDED_DOC_TYPES)), help="Comma-separated HAL doc types to exclude.")
    parser.add_argument("--no-filter-theses-hdr", action="store_true", help="Disable default filtering of theses/HDR and other non-research records.")
    parser.add_argument("--rows", type=int, default=500, help="HAL API pagination batch size.")
    parser.add_argument("--no-latex-report", action="store_true", help="Disable deterministic LaTeX report generation.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = ensure_output_tree(args.output_dir)
    setup_logging(outputs["root"], verbose=args.verbose)
    logging.info("Starting HAL/HCERES POC for %s, %s-%s", args.team, args.start_year, args.end_year)

    discovery = discover_acentauri_hal_query(args.team, args.hal_query, args.hal_structure_id)
    (outputs["reports"] / "hal_query_discovery.json").write_text(json.dumps(discovery.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    raw_docs = query_hal_api(discovery.query, args.start_year, args.end_year, rows=args.rows)
    raw_df = clean_publication_metadata(raw_docs)
    save_df(raw_df.drop(columns=["authors_list"], errors="ignore"), outputs["tables"] / "raw_hal_records.csv")

    if args.no_filter_theses_hdr:
        excluded_types = set()
    else:
        excluded_types = {x.strip().upper() for x in args.exclude_doc_types.split(",") if x.strip()}
        include_types = {x.strip().upper() for x in args.include_doc_types.split(",") if x.strip()}
        excluded_types -= include_types

    filtered_df, removed_df = filter_publications(raw_df, excluded_types)
    unique_df, duplicates_df = deduplicate_publications(filtered_df)

    theme_df = infer_or_load_theme_mapping(args.theme_mapping, args.members_csv)
    members_df = retrieve_or_infer_team_members(unique_df, args.members_csv, args.team)
    unique_df = identify_acentauri_members(unique_df, members_df)

    tables: Dict[str, pd.DataFrame] = {}
    tables["cleaned_publications"] = unique_df.drop(columns=["authors_list"], errors="ignore")
    tables["filtered_out_records"] = removed_df.drop(columns=["authors_list"], errors="ignore")
    tables["duplicate_records"] = duplicates_df.drop(columns=["authors_list"], errors="ignore")
    tables["identified_or_inferred_members"] = members_df
    tables["theme_mapping"] = theme_df

    tables.update(compute_global_indicators(raw_df, filtered_df, unique_df, removed_df, duplicates_df, members_df))
    tables.update(compute_theme_statistics(unique_df, theme_df))
    tables.update(analyze_collaborations(unique_df, args.team))
    tables.update(analyze_publication_venues(unique_df, args.scimago_csv, args.core_csv))
    tables.update(compute_open_science_indicators(unique_df))

    export_csv_tables(outputs, tables)
    export_latex_tables(outputs, tables)
    generate_figures(outputs, tables)

    # Network edge list in dedicated folder too.
    if "collaboration_edge_list" in tables:
        save_df(tables["collaboration_edge_list"], outputs["network"] / "collaboration_edge_list.csv")

    generate_markdown_or_text_report(outputs, args, discovery, tables)

    if not args.no_latex_report:
        generate_deterministic_latex_report(outputs, args, discovery, tables)

    logging.info("Done. Outputs written to %s", outputs["root"].resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logging.error("Interrupted by user")
        raise SystemExit(130)
    except Exception as exc:
        logging.exception("Pipeline failed: %s", exc)
        raise SystemExit(1)
