# HAL ACENTAURI HCERES POC

Proof of concept for an automated HAL-based bibliometric analysis pipeline oriented toward an HCERES-style report for the ACENTAURI team.

The implementation is deliberately simple: a single Python module named:

```text
hal_acentauri_hceres_poc.py
```

The report generation is deterministic and template-based. Paid AI APIs were used during development and material preparation, while the generated report content itself is produced from computed indicators and explicit metadata provenance.

## What it does

The pipeline:

- discovers or uses the HAL structure/query for a team;
- retrieves HAL records for a configurable period;
- cleans and filters publication metadata;
- deduplicates records;
- identifies team members from HAL metadata or optional CSV files;
- computes HCERES-oriented indicators;
- exports CSV tables, LaTeX tables, figures, a Markdown summary, and a standalone LaTeX report.

## Install

Recommended for local development:

```bash
python -m pip install -e .
```

With development/test extras:

```bash
python -m pip install -e ".[dev]"
```

Legacy requirements-based installation is also supported:

```bash
python -m pip install -r requirements.txt
```

## Run

After editable installation:

```bash
hal-acentauri-hceres-poc
```

Or directly from the repository:

```bash
python hal_acentauri_hceres_poc.py
```

Optional example:

```bash
python hal_acentauri_hceres_poc.py \
  --start-year 2022 \
  --end-year 2026 \
  --team ACENTAURI \
  --output-dir outputs
```

Disable the LaTeX report generation if needed:

```bash
python hal_acentauri_hceres_poc.py --no-latex-report
```

The command contacts the public HAL API. Re-running it can update the outputs if HAL metadata has changed.

## Optional files

The script runs without optional files, but the following CSV files can improve accuracy:

```text
data/acentauri_members.csv
data/theme_mapping.csv
data/scimago_journals.csv
data/core_conferences.csv
```

Example files are provided in `data/*.example.csv`.

Example `data/theme_mapping.csv`:

```csv
author_name,theme,status
Fabien Lionti,MOC,phd
Ezio Malis,ARC,researcher
Philippe Martinet,RIC,researcher
```

These files are enrichments/overrides, not mandatory dependencies.

## Outputs

By default, generated artifacts are written into `outputs/`:

```text
outputs/
  figures/
  tables/
  latex/
  reports/
  network/
```

Main generated reports:

```text
outputs/reports/hceres_summary_report.md
outputs/reports/hceres_deterministic_report_body.tex
outputs/reports/hceres_deterministic_report_standalone.tex
```

If a LaTeX distribution is installed, compile the standalone report with:

```bash
cd outputs/reports
pdflatex hceres_deterministic_report_standalone.tex
```

Generated outputs are ignored by Git. Keep the source code, example CSV files, and documentation versioned; regenerate reports when needed.

## Validate

Static smoke tests do not require HAL access:

```bash
python -m unittest discover -s tests
```

Full pipeline validation requires installed dependencies and network access to HAL:

```bash
hal-acentauri-hceres-poc --output-dir outputs
```

## Notes

The script distinguishes between:

- verified HAL metadata;
- inferred information;
- manually supplied CSV information;
- unavailable or incomplete information.

It does not invent the meaning of ARC/RIC/MOC when public or local mapping data is insufficient.
