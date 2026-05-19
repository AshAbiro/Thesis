from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER_CSV = ROOT / "bangladesh_uhi_extraction_master.csv"
TEMPLATE_MD = ROOT / "paper_extraction_template.md"
PDFS_DIR = ROOT / "papers"
EXTRACTIONS_DIR = ROOT / "extractions"
OUTPUTS_DIR = ROOT / "outputs"
SCREENSHOTS_DIR = ROOT / "sources" / "screenshots"
NOTES_DIR = ROOT / "sources" / "notes"
RAW_PDFS_DIR = ROOT / "sources" / "raw_pdfs"

CORE_FIELDS = [
    "title",
    "authors",
    "year",
    "document_type",
    "study_location",
    "satellite_sensors",
    "temporal_coverage",
    "spatial_resolution_m",
    "lst_method",
    "lulc_algorithm",
    "overall_accuracy",
    "kappa",
    "lst_range_c",
    "evidence_status",
]

INDEX_FIELDS = [
    ("NDVI", "ndvi_method"),
    ("NDBI", "ndbi_method"),
    ("NDWI", "ndwi_method"),
    ("MNDWI", "mndwi_method"),
    ("Albedo", "albedo_method"),
    ("UTFVI", "utfvi_method"),
]


def ensure_workspace() -> None:
    for directory in [PDFS_DIR, EXTRACTIONS_DIR, OUTPUTS_DIR, SCREENSHOTS_DIR, NOTES_DIR, RAW_PDFS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def load_fieldnames() -> list[str]:
    if not MASTER_CSV.exists():
        raise FileNotFoundError(f"Master CSV not found: {MASTER_CSV}")

    with MASTER_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])

    if not header:
        raise ValueError("Master CSV is missing a header row.")

    return header


def load_rows() -> tuple[list[str], list[dict[str, str]]]:
    fieldnames = load_fieldnames()
    with MASTER_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_rows(fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with MASTER_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def clean_cell(value: str) -> str:
    if not value:
        return ""
    value = " ".join(str(value).split())
    return value.replace("|", "/")


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        table.append("| " + " | ".join(clean_cell(cell) or "-" for cell in padded[: len(headers)]) + " |")
    return "\n".join(table)


def format_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_pdfs() -> list[Path]:
    return sorted(PDFS_DIR.glob("*.pdf"))


def strip_file_prefix(stem: str) -> tuple[str, str]:
    match = re.match(r"^\(([^)]+)\)\s*(.*)$", stem)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", stem.strip()


def title_from_filename(stem: str) -> str:
    _, text = strip_file_prefix(stem)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("â€“", "-")
    text = text.replace("â€‘", "-")
    text = text.replace("â€”", "-")
    text = text.replace("â€'", "'")
    text = text.replace("–", "-")
    return text


def infer_bangladesh_signal(text: str) -> str:
    lowered = text.lower()
    for token in [
        "bangladesh",
        "dhaka",
        "chuadanga",
        "rajshahi",
        "khulna",
        "gazipur",
        "chattogram",
        "sylhet",
        "barishal",
        "kushtia",
    ]:
        if token in lowered:
            return "Bangladesh-linked by filename"
    return ""


def infer_country(text: str) -> str:
    return "Bangladesh" if infer_bangladesh_signal(text) else ""


def extraction_path(paper_id: str) -> Path:
    return EXTRACTIONS_DIR / f"{paper_id}.md"


def note_path(paper_id: str) -> Path:
    return NOTES_DIR / f"{paper_id}_source_log.md"


def screenshot_dir(paper_id: str) -> Path:
    return SCREENSHOTS_DIR / paper_id


def fill_template(metadata: dict[str, str]) -> str:
    template = TEMPLATE_MD.read_text(encoding="utf-8")
    replacements = {
        "Paper name": metadata.get("title", ""),
        "Authors": metadata.get("authors", ""),
        "Year": metadata.get("year", ""),
        "Document type": metadata.get("document_type", ""),
        "Publisher or institution": metadata.get("publisher_or_institution", ""),
        "DOI or URL": metadata.get("doi_or_url", ""),
        "Study location": metadata.get("study_location", ""),
        "Country": metadata.get("country", ""),
        "Urban focus": metadata.get("urban_focus", ""),
    }

    for label, value in replacements.items():
        pattern = rf"(?m)^- {re.escape(label)}:\s*$"
        replacement = f"- {label}: {value}".rstrip()
        template = re.sub(pattern, replacement, template)

    return template


def create_source_log(paper_id: str, title: str, location: str, year: str, pdf_name: str) -> None:
    note_path(paper_id).write_text(
        "\n".join(
            [
                f"# Source Log: {paper_id}",
                "",
                f"- Title: {title}",
                f"- Location: {location}",
                f"- Year: {year}",
                f"- PDF file: {pdf_name}",
                "- Screenshot set added:",
                "- Extraction status: not started",
                "- Notes:",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def create_extraction_stub(metadata: dict[str, str], pdf_name: str = "") -> Path:
    path = extraction_path(metadata["paper_id"])
    if path.exists():
        return path

    content = fill_template(metadata)
    if pdf_name:
        content += f"\n## File Link\n\n- PDF filename: {pdf_name}\n"
    path.write_text(content, encoding="utf-8")
    return path


def base_row(fieldnames: list[str]) -> dict[str, str]:
    return {field: "" for field in fieldnames}


def find_row(rows: list[dict[str, str]], paper_id: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("paper_id", "") == paper_id:
            return row
    return None


def add_or_update_row(rows: list[dict[str, str]], fieldnames: list[str], data: dict[str, str]) -> tuple[dict[str, str], bool]:
    row = find_row(rows, data["paper_id"])
    created = False
    if row is None:
        row = base_row(fieldnames)
        rows.append(row)
        created = True

    for key, value in data.items():
        if key in row and value and not row.get(key):
            row[key] = value

    return row, created


def new_paper(args: argparse.Namespace) -> int:
    ensure_workspace()
    fieldnames, rows = load_rows()

    title = args.title.strip()
    paper_id = args.paper_id.strip() if args.paper_id else slugify(title)
    if not paper_id:
        raise ValueError("paper_id could not be derived. Provide --paper-id explicitly.")

    if find_row(rows, paper_id):
        print(f"Paper '{paper_id}' already exists in the master CSV.", file=sys.stderr)
        return 1

    metadata = {
        "paper_id": paper_id,
        "title": title,
        "authors": args.authors or "",
        "year": str(args.year) if args.year is not None else "",
        "document_type": args.document_type or "",
        "publisher_or_institution": args.publisher_or_institution or "",
        "doi_or_url": args.doi_or_url or "",
        "study_location": args.location or "",
        "country": args.country or "Bangladesh",
        "urban_focus": args.urban_focus or "",
    }

    md_path = create_extraction_stub(metadata)
    screenshot_dir(paper_id).mkdir(parents=True, exist_ok=True)
    create_source_log(paper_id, title, args.location or "", str(args.year or ""), args.pdf_name or "")

    row_data = {
        "paper_id": paper_id,
        "title": title,
        "authors": args.authors or "",
        "year": str(args.year) if args.year is not None else "",
        "document_type": args.document_type or "",
        "study_location": args.location or "",
        "country": args.country or "Bangladesh",
        "urban_focus": args.urban_focus or "",
        "source_notes": f"Extraction stub created {format_timestamp()}",
    }
    add_or_update_row(rows, fieldnames, row_data)
    write_rows(fieldnames, rows)

    print(f"Created paper entry: {paper_id}")
    print(f"- Extraction file: {md_path}")
    print(f"- Screenshot folder: {screenshot_dir(paper_id)}")
    print(f"- Source log: {note_path(paper_id)}")
    return 0


def import_existing_pdfs(_: argparse.Namespace) -> int:
    ensure_workspace()
    fieldnames, rows = load_rows()
    pdfs = list_pdfs()

    if not pdfs:
        print("No PDFs found in papers/.")
        return 0

    created_rows = 0
    created_extractions = 0
    created_logs = 0

    for pdf_path in pdfs:
        title = title_from_filename(pdf_path.stem)
        prefix, _ = strip_file_prefix(pdf_path.stem)
        paper_id = slugify(title)
        if not paper_id:
            continue

        metadata = {
            "paper_id": paper_id,
            "title": title,
            "authors": "",
            "year": "",
            "document_type": "",
            "publisher_or_institution": "",
            "doi_or_url": "",
            "study_location": "",
            "country": infer_country(pdf_path.name),
            "urban_focus": "",
        }

        md_path = extraction_path(paper_id)
        if not md_path.exists():
            create_extraction_stub(metadata, pdf_path.name)
            created_extractions += 1

        screenshot_dir(paper_id).mkdir(parents=True, exist_ok=True)
        log_path = note_path(paper_id)
        if not log_path.exists():
            create_source_log(paper_id, title, "", "", pdf_path.name)
            created_logs += 1

        row_data = {
            "paper_id": paper_id,
            "title": title,
            "country": infer_country(pdf_path.name),
            "bangladesh_relevance": infer_bangladesh_signal(pdf_path.name),
            "source_notes": f"Imported from papers/{pdf_path.name}",
            "thesis_use_notes": prefix,
        }
        _, created = add_or_update_row(rows, fieldnames, row_data)
        if created:
            created_rows += 1

    write_rows(fieldnames, rows)

    print(f"PDFs scanned: {len(pdfs)}")
    print(f"CSV rows created: {created_rows}")
    print(f"Extraction stubs created: {created_extractions}")
    print(f"Source logs created: {created_logs}")
    return 0


def summarize_validation(row: dict[str, str]) -> str:
    parts = []
    if row.get("overall_accuracy"):
        parts.append(f"OA {row['overall_accuracy']}")
    if row.get("kappa"):
        parts.append(f"Kappa {row['kappa']}")
    if row.get("performance_metrics"):
        parts.append(row["performance_metrics"])
    return "; ".join(parts) or "Not filled"


def summarize_indices(row: dict[str, str]) -> str:
    labels = [label for label, field in INDEX_FIELDS if row.get(field)]
    return ", ".join(labels) or "Not filled"


def summarize_key_values(row: dict[str, str]) -> str:
    parts = []
    if row.get("lst_range_c"):
        parts.append(f"LST {row['lst_range_c']}")
    if row.get("lst_mean_c"):
        parts.append(f"Mean {row['lst_mean_c']}")
    if row.get("temperature_difference_c"):
        parts.append(f"DeltaT {row['temperature_difference_c']}")
    return "; ".join(parts) or "Not filled"


def row_priority(row: dict[str, str]) -> tuple[int, int, str, str]:
    completeness = sum(
        1
        for field in [
            "study_location",
            "satellite_sensors",
            "lst_method",
            "lulc_algorithm",
            "performance_metrics",
            "thesis_reuse_potential_score",
            "evidence_status",
        ]
        if row.get(field)
    )
    extracted = 1 if row.get("evidence_status") else 0
    return (-extracted, -completeness, row.get("study_location", ""), row.get("title", ""))


def build_comparative_review(rows: list[dict[str, str]]) -> str:
    headers = [
        "Paper",
        "Location",
        "Year(s) Studied",
        "Sensor",
        "LST Method",
        "Indices",
        "LULC Method",
        "Validation",
        "Key Reported Values",
        "Main Finding",
        "Dhaka Suitability",
        "Reuse Decision",
    ]
    table_rows: list[list[str]] = []
    for row in sorted(rows, key=row_priority):
        table_rows.append(
            [
                row.get("title") or row.get("paper_id", ""),
                row.get("study_location", ""),
                row.get("temporal_coverage") or row.get("year", ""),
                row.get("satellite_sensors", ""),
                row.get("lst_method", ""),
                summarize_indices(row),
                row.get("lulc_algorithm", ""),
                summarize_validation(row),
                summarize_key_values(row),
                row.get("key_findings", ""),
                row.get("dhaka_suitability_score", ""),
                row.get("thesis_use_notes", "") or row.get("thesis_reuse_potential_score", ""),
            ]
        )

    lines = [
        "# Comparative Review Matrix",
        "",
        f"Generated: {format_timestamp()}",
        "",
        "This table is built from `bangladesh_uhi_extraction_master.csv`.",
        "",
    ]
    if table_rows:
        lines.append(markdown_table(headers, table_rows))
    else:
        lines.append("No extracted papers found yet.")
    lines.append("")
    return "\n".join(lines)


def build_value_matrix(rows: list[dict[str, str]]) -> str:
    headers = [
        "Paper",
        "LST Range",
        "Mean LST",
        "NDVI Range",
        "NDBI Range",
        "NDWI/MNDWI Range",
        "OA",
        "Kappa",
        "RMSE/MAE/R2",
        "Urban-Rural Contrast",
        "Key Thresholds",
    ]
    table_rows: list[list[str]] = []
    for row in sorted(rows, key=row_priority):
        water_range = row.get("ndwi_range") or row.get("mndwi_range", "")
        table_rows.append(
            [
                row.get("title") or row.get("paper_id", ""),
                row.get("lst_range_c", ""),
                row.get("lst_mean_c", ""),
                row.get("ndvi_range", ""),
                row.get("ndbi_range", ""),
                water_range,
                row.get("overall_accuracy", ""),
                row.get("kappa", ""),
                row.get("performance_metrics", ""),
                row.get("urban_rural_contrast_c", ""),
                row.get("thresholds", ""),
            ]
        )

    lines = [
        "# Value Extraction Matrix",
        "",
        f"Generated: {format_timestamp()}",
        "",
    ]
    if table_rows:
        lines.append(markdown_table(headers, table_rows))
    else:
        lines.append("No extracted numeric values found yet.")
    lines.append("")
    return "\n".join(lines)


def build_scorecard(rows: list[dict[str, str]]) -> str:
    headers = [
        "Paper",
        "Reproducibility",
        "Robustness",
        "Dhaka Suitability",
        "Bangladesh Suitability",
        "Validation Strength",
        "Value Richness",
        "Thesis Reuse",
    ]
    table_rows: list[list[str]] = []
    for row in sorted(rows, key=row_priority):
        table_rows.append(
            [
                row.get("title") or row.get("paper_id", ""),
                row.get("reproducibility_score", ""),
                row.get("robustness_score", ""),
                row.get("dhaka_suitability_score", ""),
                row.get("bangladesh_suitability_score", ""),
                row.get("validation_strength_score", ""),
                row.get("numerical_extraction_richness_score", ""),
                row.get("thesis_reuse_potential_score", ""),
            ]
        )

    lines = [
        "# Paper Scorecard",
        "",
        f"Generated: {format_timestamp()}",
        "",
    ]
    if table_rows:
        lines.append(markdown_table(headers, table_rows))
    else:
        lines.append("No scored papers found yet.")
    lines.append("")
    return "\n".join(lines)


def build_method_inventory(rows: list[dict[str, str]]) -> str:
    sensor_counter = Counter(clean_cell(row.get("satellite_sensors", "")) for row in rows if row.get("satellite_sensors"))
    lst_counter = Counter(clean_cell(row.get("lst_method", "")) for row in rows if row.get("lst_method"))
    lulc_counter = Counter(clean_cell(row.get("lulc_algorithm", "")) for row in rows if row.get("lulc_algorithm"))
    location_counter = Counter(clean_cell(row.get("study_location", "")) for row in rows if row.get("study_location"))

    def counter_lines(title: str, counter: Counter[str]) -> list[str]:
        lines = [f"## {title}", ""]
        if not counter:
            lines.append("- No entries yet.")
        else:
            for key, count in counter.most_common():
                lines.append(f"- {key}: {count}")
        lines.append("")
        return lines

    lines = [
        "# Method Inventory",
        "",
        f"Generated: {format_timestamp()}",
        "",
    ]
    lines.extend(counter_lines("Locations", location_counter))
    lines.extend(counter_lines("Sensors", sensor_counter))
    lines.extend(counter_lines("LST Methods", lst_counter))
    lines.extend(counter_lines("LULC Algorithms", lulc_counter))
    return "\n".join(lines)


def build_paper_inventory(rows: list[dict[str, str]]) -> str:
    row_index = {row.get("paper_id", ""): row for row in rows}
    headers = [
        "Prefix",
        "PDF Filename",
        "Derived Title",
        "Paper ID",
        "Country Signal",
        "CSV Row",
        "Extraction Stub",
        "Source Log",
    ]
    table_rows: list[list[str]] = []
    for pdf_path in list_pdfs():
        prefix, _ = strip_file_prefix(pdf_path.stem)
        title = title_from_filename(pdf_path.stem)
        paper_id = slugify(title)
        table_rows.append(
            [
                prefix,
                pdf_path.name,
                title,
                paper_id,
                infer_country(pdf_path.name) or infer_bangladesh_signal(pdf_path.name) or "Not inferred",
                "Yes" if paper_id in row_index else "No",
                "Yes" if extraction_path(paper_id).exists() else "No",
                "Yes" if note_path(paper_id).exists() else "No",
            ]
        )

    lines = [
        "# Paper Inventory",
        "",
        f"Generated: {format_timestamp()}",
        "",
        f"- PDFs in papers/: {len(table_rows)}",
        "",
    ]
    if table_rows:
        lines.append(markdown_table(headers, table_rows))
    else:
        lines.append("No PDFs found in papers/.")
    lines.append("")
    return "\n".join(lines)


def build_priority_queue(rows: list[dict[str, str]]) -> str:
    row_index = {row.get("paper_id", ""): row for row in rows}
    primary: list[str] = []
    secondary: list[str] = []
    support: list[str] = []

    for pdf_path in list_pdfs():
        title = title_from_filename(pdf_path.stem)
        paper_id = slugify(title)
        row = row_index.get(paper_id, {})
        signal = " ".join(
            [
                title.lower(),
                row.get("country", "").lower(),
                row.get("bangladesh_relevance", "").lower(),
            ]
        )
        line = f"- {title}"

        if any(token in signal for token in ["dhaka", "bangladesh", "chuadanga", "rajshahi", "khulna", "gazipur", "chattogram", "sylhet", "barishal", "kushtia"]):
            primary.append(line)
        elif any(token in signal for token in ["review", "satellite remote sensing", "urban heat island", "machine learning", "surface urban heat island"]):
            secondary.append(line)
        else:
            support.append(line)

    lines = [
        "# Bangladesh Priority Queue",
        "",
        f"Generated: {format_timestamp()}",
        "",
        "## Primary Extraction First",
        "",
    ]
    lines.extend(primary or ["- No Bangladesh-linked titles inferred from filenames."])
    lines.extend(["", "## Secondary Method Support", ""])
    lines.extend(secondary or ["- No secondary support titles identified."])
    lines.extend(["", "## External or Generic Support", ""])
    lines.extend(support or ["- No external support titles identified.", ""])
    lines.append("")
    return "\n".join(lines)


def missing_core_fields(row: dict[str, str]) -> list[str]:
    return [field for field in CORE_FIELDS if not row.get(field, "").strip()]


def score_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "").strip())
    except ValueError:
        return -1.0


def build_status_report(rows: list[dict[str, str]]) -> str:
    pdf_count = len(list_pdfs())
    extraction_count = len(list(EXTRACTIONS_DIR.glob("*.md")))
    lines = [
        "# Status Report",
        "",
        f"Generated: {format_timestamp()}",
        "",
        f"- PDFs in papers/: {pdf_count}",
        f"- Extraction markdown files: {extraction_count}",
        f"- Total paper rows: {len(rows)}",
        f"- Rows with location filled: {sum(1 for row in rows if row.get('study_location'))}",
        f"- Rows with LST method filled: {sum(1 for row in rows if row.get('lst_method'))}",
        f"- Rows with LULC algorithm filled: {sum(1 for row in rows if row.get('lulc_algorithm'))}",
        f"- Rows with scores filled: {sum(1 for row in rows if row.get('thesis_reuse_potential_score'))}",
        "",
        "## Core Field Gaps",
        "",
    ]

    if not rows:
        lines.append("- No papers added yet.")
    else:
        for row in sorted(rows, key=lambda item: (len(missing_core_fields(item)),) + row_priority(item)):
            paper_name = row.get("title") or row.get("paper_id", "Unnamed paper")
            missing = missing_core_fields(row)
            if missing:
                lines.append(f"- {paper_name}: missing {len(missing)} core fields -> {', '.join(missing)}")
            else:
                lines.append(f"- {paper_name}: no core field gaps")

    ranked = sorted(
        [row for row in rows if row.get("thesis_reuse_potential_score")],
        key=lambda item: score_value(item, "thesis_reuse_potential_score"),
        reverse=True,
    )
    lines.extend(["", "## Highest Thesis Reuse Scores", ""])
    if not ranked:
        lines.append("- No thesis reuse scores entered yet.")
    else:
        for row in ranked[:10]:
            paper_name = row.get("title") or row.get("paper_id", "Unnamed paper")
            lines.append(f"- {paper_name}: {row.get('thesis_reuse_potential_score', '')}")

    lines.append("")
    return "\n".join(lines)


def build_outputs(_: argparse.Namespace) -> int:
    ensure_workspace()
    _, rows = load_rows()

    output_map = {
        OUTPUTS_DIR / "comparative_review_matrix.md": build_comparative_review(rows),
        OUTPUTS_DIR / "value_extraction_matrix.md": build_value_matrix(rows),
        OUTPUTS_DIR / "paper_scorecard.md": build_scorecard(rows),
        OUTPUTS_DIR / "method_inventory.md": build_method_inventory(rows),
        OUTPUTS_DIR / "paper_inventory.md": build_paper_inventory(rows),
        OUTPUTS_DIR / "bangladesh_priority_queue.md": build_priority_queue(rows),
        OUTPUTS_DIR / "status_report.md": build_status_report(rows),
    }

    for path, content in output_map.items():
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path}")

    return 0


def validate(args: argparse.Namespace) -> int:
    _, rows = load_rows()
    pdfs = list_pdfs()
    if not rows and not pdfs:
        print("No paper rows and no PDFs found.")
        return 0

    missing_count = 0
    for row in rows:
        paper_name = row.get("title") or row.get("paper_id", "Unnamed paper")
        missing = missing_core_fields(row)
        if missing:
            missing_count += 1
            print(f"{paper_name}: missing -> {', '.join(missing)}")

    missing_stubs = []
    for pdf_path in pdfs:
        paper_id = slugify(title_from_filename(pdf_path.stem))
        if not extraction_path(paper_id).exists():
            missing_stubs.append(pdf_path.name)

    if missing_stubs:
        print("Missing extraction stubs for:")
        for name in missing_stubs:
            print(f"- {name}")

    if missing_count == 0 and not missing_stubs:
        print("Workspace validation passed.")
        return 0

    print(f"{missing_count} paper row(s) have missing core fields.")
    return 1 if args.strict else 0


def status(_: argparse.Namespace) -> int:
    _, rows = load_rows()
    print(f"PDFs in papers/: {len(list_pdfs())}")
    print(f"Extraction markdown files: {len(list(EXTRACTIONS_DIR.glob('*.md')))}")
    print(f"Total paper rows: {len(rows)}")
    print(f"Rows with study location: {sum(1 for row in rows if row.get('study_location'))}")
    print(f"Rows with LST method: {sum(1 for row in rows if row.get('lst_method'))}")
    print(f"Rows with LULC algorithm: {sum(1 for row in rows if row.get('lulc_algorithm'))}")
    print(f"Rows with thesis reuse score: {sum(1 for row in rows if row.get('thesis_reuse_potential_score'))}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Bangladesh UHI/LST/LULC thesis workspace.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_paper_parser = subparsers.add_parser("new-paper", help="Create a new extraction entry and blank CSV row.")
    new_paper_parser.add_argument("--paper-id", help="Stable paper identifier. Defaults to a slug of the title.")
    new_paper_parser.add_argument("--title", required=True, help="Full paper title.")
    new_paper_parser.add_argument("--authors", help="Authors as shown in the paper.")
    new_paper_parser.add_argument("--year", type=int, help="Publication year.")
    new_paper_parser.add_argument("--document-type", help="journal article, thesis, report, etc.")
    new_paper_parser.add_argument("--publisher-or-institution", help="Publisher or university.")
    new_paper_parser.add_argument("--doi-or-url", help="DOI or source URL.")
    new_paper_parser.add_argument("--location", help="Study location.")
    new_paper_parser.add_argument("--country", help="Country name. Defaults to Bangladesh.")
    new_paper_parser.add_argument("--urban-focus", help="urban, peri-urban, metropolitan, etc.")
    new_paper_parser.add_argument("--pdf-name", help="Optional existing PDF filename for logging.")
    new_paper_parser.set_defaults(func=new_paper)

    import_parser = subparsers.add_parser("import-existing-pdfs", help="Register PDFs already stored in papers/.")
    import_parser.set_defaults(func=import_existing_pdfs)

    build_parser_cmd = subparsers.add_parser("build-outputs", help="Generate markdown outputs from the master CSV and papers/.")
    build_parser_cmd.set_defaults(func=build_outputs)

    validate_parser = subparsers.add_parser("validate", help="Check core-field completeness in the master CSV.")
    validate_parser.add_argument("--strict", action="store_true", help="Exit with code 1 when gaps are found.")
    validate_parser.set_defaults(func=validate)

    status_parser = subparsers.add_parser("status", help="Print a short workspace status summary.")
    status_parser.set_defaults(func=status)

    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    ensure_workspace()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
