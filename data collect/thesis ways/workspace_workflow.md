# Workspace Workflow

This workspace is now structured to support repeatable thesis extraction.

## Folder Layout

- `papers/`: your actual paper PDF library
- `extractions/`: one extraction markdown file per paper
- `sources/screenshots/`: figure or page screenshots, grouped by `paper_id`
- `sources/notes/`: quick source logs and intake notes
- `sources/raw_pdfs/`: optional overflow storage if you later separate raw sources
- `outputs/`: auto-generated comparison tables and status files
- `scripts/`: workspace utilities

## Main Files

- `bangladesh_uhi_lst_lulc_thesis_framework.md`: master framework
- `bangladesh_uhi_extraction_master.csv`: master extraction sheet
- `paper_extraction_template.md`: blank extraction template
- `thesis_methodology_blueprint.md`: thesis-ready methodology draft
- `bangladesh_uhi_csv_dictionary.md`: CSV field guide

## Core Commands

### 1. Create a New Paper Entry

```powershell
python scripts/thesis_workspace.py new-paper `
  --paper-id dhaka_example_2024_lst `
  --title "Example Dhaka LST and LULC Study" `
  --authors "Author A; Author B" `
  --year 2024 `
  --document-type "journal article" `
  --location "Dhaka" `
  --urban-focus "metropolitan"
```

This command:

- creates `extractions/<paper_id>.md`
- creates a screenshot folder under `sources/screenshots/`
- creates a source log under `sources/notes/`
- appends a blank row to `bangladesh_uhi_extraction_master.csv`

### 2. Import PDFs Already Stored in `papers/`

```powershell
python scripts/thesis_workspace.py import-existing-pdfs
```

This command:

- scans all PDFs already inside `papers/`
- derives a `paper_id` and title from each filename
- creates `extractions/<paper_id>.md` if missing
- creates `sources/notes/<paper_id>_source_log.md` if missing
- creates or updates the corresponding row in `bangladesh_uhi_extraction_master.csv`

### 3. Build Comparison Outputs

```powershell
python scripts/thesis_workspace.py build-outputs
```

This command generates:

- `outputs/comparative_review_matrix.md`
- `outputs/value_extraction_matrix.md`
- `outputs/paper_scorecard.md`
- `outputs/method_inventory.md`
- `outputs/paper_inventory.md`
- `outputs/status_report.md`

### 4. Validate Extraction Completeness

```powershell
python scripts/thesis_workspace.py validate
```

Strict mode returns a failing exit code if gaps exist:

```powershell
python scripts/thesis_workspace.py validate --strict
```

### 5. View Quick Status

```powershell
python scripts/thesis_workspace.py status
```

## Recommended Working Sequence

1. if PDFs already exist in `papers/`, run `import-existing-pdfs`
2. place screenshots inside `sources/screenshots/<paper_id>/`
3. extract the paper into `extractions/<paper_id>.md`
4. fill the corresponding row in `bangladesh_uhi_extraction_master.csv`
5. run `build-outputs`
6. run `validate`

## Practical Rule

Do not write final thesis conclusions directly into the framework before the values are captured in the paper markdown and master CSV. The CSV and paper file should remain the primary evidence record.
