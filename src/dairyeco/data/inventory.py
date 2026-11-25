"""Read-only inventory of ``data/raw/`` and builder for ``dataset_manifest.csv``.

Walks every file under the raw directory, records size, media type and
SHA-256, assigns a likely source with an explicit identification basis, and
builds ``data/metadata/dataset_manifest.csv``.
Nothing under ``data/raw/`` is ever written, renamed or moved.

Run: ``uv run python -m dairyeco.data.inventory``
"""

from __future__ import annotations

import csv
import hashlib
import mimetypes
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from dairyeco.config import METADATA_DIR, PROJECT_ROOT, RAW_DIR

INVENTORY_CSV = METADATA_DIR / "raw_file_inventory.csv"
MANIFEST_CSV = METADATA_DIR / "dataset_manifest.csv"

# Source assignment rules. Directory names are user-provided context; the
# ``basis`` text says which internal evidence confirmed each mapping (see
# reports/dataset_audit.md for the evidence and page/sheet references).
DIRECTORY_SOURCES = {
    "agribalyse_3_2": (
        "agribalyse_3_2",
        "high",
        "user-renamed directory; workbook/PDF titles and contents state AGRIBALYSE 3.2",
    ),
    "pdo_cheese_lca": (
        "pdo_cheese_lca",
        "medium",
        (
            "user-renamed directory; workbooks contain 44 French PDO cheeses, FU = 1 kg cheese; "
            "no DOI/citation/licence metadata inside the files"
        ),
    ),
    "uslci": (
        "uslci",
        "high",
        (
            "user-renamed directory; openLCA JSON-LD export (openlca.json schemaVersion 3) "
            "with US LCI process/flow entities"
        ),
    ),
}

# Root-level PDFs are identified by text found on their first pages.
PDF_SIGNATURES = {
    "anl_nist_regional_plastics_2024": (
        "ANL/ESIA-24/3",
        (
            "first pages: report number ANL/ESIA-24/3, 'Life-Cycle Analysis Datasets for "
            "Regionalized Plastic Pathways', Argonne + NIST authors, February 2024"
        ),
    ),
    "ifc_wbg_ehs_dairy_2007": (
        "Environmental, Health, and Safety Guidelines",
        (
            "first page: 'Environmental, Health, and Safety Guidelines for Dairy Processing', "
            "World Bank Group, dated April 30, 2007"
        ),
    ),
}


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    file_name: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str
    likely_source: str
    source_component: str
    identification_confidence: str
    identification_basis: str


@dataclass(frozen=True)
class DatasetManifestRecord:
    dataset_id: str
    title: str
    provider: str
    version: str
    url: str
    download_date: str
    licence: str
    geography: str
    reference_year: str
    functional_unit: str
    system_boundary: str
    lcia_method: str
    file_path: str
    file_count: int
    total_size_bytes: int
    sha256_checksum: str
    identification_confidence: str
    data_type: str
    intended_use: str
    limitations: str


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sniff_media_type(path: Path) -> str:
    """Media type from extension, falling back to magic bytes for unknown/missing extensions."""
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and path.suffix:
        return guessed
    with path.open("rb") as handle:
        head = handle.read(8)
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"PK\x03\x04") and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            if "xl/workbook.xml" in archive.namelist():
                return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return "application/zip"
    return guessed or "application/octet-stream"


def _pdf_first_pages_text(path: Path, pages: int = 3) -> str:
    import pdfplumber  # local import: only needed for root-level PDFs

    with pdfplumber.open(path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages[:pages])


def identify(path: Path, raw_dir: Path) -> tuple[str, str, str, str]:
    """Return (likely_source, source_component, confidence, basis) for one file."""
    parts = path.relative_to(raw_dir).parts
    if len(parts) > 1 and parts[0] in DIRECTORY_SOURCES:
        source, confidence, basis = DIRECTORY_SOURCES[parts[0]]
        component = parts[1] if len(parts) > 2 else "root"
        if path.name.upper() == "MANIFEST.TXT":
            component = "download_manifest"
        return source, component, confidence, basis
    if path.suffix.lower() == ".pdf":
        text = _pdf_first_pages_text(path)
        for source, (needle, basis) in PDF_SIGNATURES.items():
            if needle in text:
                return source, "report_pdf", "high", basis
    return "unidentified", "", "low", "no directory rule or content signature matched"


def build_inventory(raw_dir: Path = RAW_DIR) -> list[FileRecord]:
    records = []
    for path in sorted(p for p in raw_dir.rglob("*") if p.is_file()):
        source, component, confidence, basis = identify(path, raw_dir)
        records.append(
            FileRecord(
                relative_path=path.relative_to(raw_dir.parent.parent).as_posix(),
                file_name=path.name,
                extension=path.suffix.lower().lstrip("."),
                media_type=sniff_media_type(path),
                size_bytes=path.stat().st_size,
                sha256=sha256_file(path),
                likely_source=source,
                source_component=component,
                identification_confidence=confidence,
                identification_basis=basis,
            )
        )
    return records


def dataset_checksum(records: list[FileRecord]) -> str:
    """Deterministic aggregate checksum: SHA-256 over sorted 'sha256  relative_path' lines."""
    if len(records) == 1:
        return records[0].sha256
    lines = sorted(f"{r.sha256}  {r.relative_path}" for r in records)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def build_dataset_manifest(records: list[FileRecord]) -> list[DatasetManifestRecord]:
    """Build the 5-source dataset manifest from inventoried file records."""
    by_source: dict[str, list[FileRecord]] = {}
    for rec in records:
        by_source.setdefault(rec.likely_source, []).append(rec)

    specs = [
        {
            "dataset_id": "agribalyse_3_2",
            "title": (
                "AGRIBALYSE 3.2 — French Agricultural and Food Product LCA Spreadsheets "
                "and Methodological Documentation"
            ),
            "provider": "ADEME, INRAE (Means-InOut), GIS REVALIM, EVEA S.A. Coopérative",
            "version": (
                "v3.2 (September 2024 release; food products workbook published Aug 2025; "
                "conventional agriculture workbook updated 18/11/2025; organic updated 12/11/2024)"
            ),
            "url": "https://www.agribalyse.fr",
            "download_date": "2026-11-11",
            "licence": "Licence Ouverte / Open Licence v2.0 ('Etalab')",
            "geography": "FR (France consumption mix for food products; France farm gate for agriculture)",
            "reference_year": "2024 (v3.2 calculations; background Ecoinvent 3.9.1, WFLDB 3.5, CIQUAL 2020)",
            "functional_unit": (
                "1 kg of food product consumed at the consumer (food workbook); "
                "1 kg of agricultural product at farm gate (agriculture workbooks)"
            ),
            "system_boundary": (
                "Cradle-to-grave / field-to-plate across 6 stages (Agriculture, Transformation, "
                "Emballage, Transport, Supermarché et distribution, Consommation) for food products; "
                "cradle-to-farm-gate for agricultural products"
            ),
            "lcia_method": (
                "EF 3.1 adapted for SimaPro v1.00 (EF 3.1 normalization/weighting single score mPt "
                "+ 16 midpoint indicators + 3 climate sub-indicators; long-term emissions included)"
            ),
            "file_path": "data/raw/agribalyse_3_2/",
            "identification_confidence": "high",
            "data_type": "published-reference (LCIA spreadsheet tables + methodology PDFs/annexes)",
            "intended_use": (
                "Finished dairy product LCA reference benchmarks, stage contribution analysis "
                "(including embedded Emballage stage), raw milk farm-gate comparison, and cheese yield/density reference"
            ),
            "limitations": (
                "Product-level food impacts already embed a fixed baseline packaging ('PACK AGB' or 'PACK PROXY') "
                "and consumer losses; cannot be used as a free-form packaging BOM engine without subtracting or "
                "holding constant the embedded Emballage stage; 7 duplicate Code AGB rows exist for packaging fixes; "
                "Egg and Quinoa FR errors flagged in Notice"
            ),
        },
        {
            "dataset_id": "pdo_cheese_lca",
            "title": "French PDO Cheeses LCI, LCIA and Process Characterization Dataset (44 PDO Cheeses)",
            "provider": "French PDO Cheese LCA Research Authors (INRAE / Institut Agro / Actalia Dataverse deposit)",
            "version": "2022 deposit (workbooks modified 2022-04-04 to 2022-08-25; PDO specs accessed Sep/Nov 2020)",
            "url": "not_embedded_in_raw_files (Dataverse bundle with MANIFEST.TXT; INAO spec URLs in specifications workbook)",
            "download_date": "2026-11-11",
            "licence": "not_embedded_in_raw_files (verify Dataverse landing page licence before external redistribution)",
            "geography": "FR (44 French Protected Designation of Origin cheese supply chains; Ecoinvent 3 FR/RER/GLO & AGRIBALYSE 3.0 FR)",
            "reference_year": "2020-2022 (PDO specifications accessed 2020; workbooks modified 2022; AGRIBALYSE 3.0 milk)",
            "functional_unit": "1 kg of ripened cheese (FU = 1kg of cheese)",
            "system_boundary": (
                "Cradle-to-ripened-cheese factory/shared-cellar exit gate across 7 base stages "
                "(Milk production, Milk transport, Milk pumping, Milk storage, Milk processing, Cheese ripening, "
                "Equipment cleaning) plus Cheese transport in Alternative scenario; excludes packaging, retail and consumer stages"
            ),
            "lcia_method": (
                "EF 3.0 / ILCD-compatible 28-indicator midpoint suite (16 main categories + 3 climate sub-indicators "
                "+ 9 toxicity/ecotoxicity chemical-group sub-indicators; no single score)"
            ),
            "file_path": "data/raw/pdo_cheese_lca/",
            "identification_confidence": "medium",
            "data_type": "published-reference (cheese-level LCI/LCIA and characterization workbooks)",
            "intended_use": (
                "Cheese manufacturing process LCI/LCIA reference, co-product allocation study, and exploratory "
                "44-cheese case study grouped strictly by cheese entity"
            ),
            "limitations": (
                "Small specialized sample (44 cheeses); LCIA sheet has 1,232 cheese x indicator rows (28 per cheese) "
                "which are NOT independent observations; excludes packaging; data_PDOcheeses_LCI lacks .xlsx extension "
                "and labels ripening wood as m3 in Initial scenario vs kg in Additional scenario; trailing whitespace "
                "and 'Camenbert'/'Camembert' spelling mismatch across tables; no DOI/licence embedded in files"
            ),
        },
        {
            "dataset_id": "uslci",
            "title": "U.S. Life Cycle Inventory (USLCI) Database (openLCA JSON-LD Export)",
            "provider": "National Renewable Energy Laboratory (NREL) / Federal LCA Commons",
            "version": "openLCA JSON-LD schemaVersion 3 (repositoryClientVersion 6, repositoryServerVersion 5; 2026-09-30 export)",
            "url": "https://www.lcacommons.gov/lca-collaboration/National_Renewable_Energy_Laboratory/USLCI_Database",
            "download_date": "2026-11-11",
            "licence": "USLCI Public Use / Federal LCA Commons Open Terms (free public use with citation)",
            "geography": "US / Northern America primary (730 US, 182 Northern America, 96 Global, 391 unspecified/regional variants)",
            "reference_year": "1990-2025 (virgin polyolefins 2014-2016, PET/PVC 2022, rPET/rHDPE/rPP 2016, containerboard 2013-2014, trucking 2024)",
            "functional_unit": (
                "Process-specific quantitative reference flow (primarily 1 kg, 1000 kg, 1.10516007 kg, 13.5 kg, "
                "1 Mg, 1 sh tn = 907.18474 kg, 1 t*km, 1 m3, 1 l, 1 MJ, or 1 kWh)"
            ),
            "system_boundary": "Gate-to-gate unit processes (1,408 UNIT_PROCESS) and cradle-to-gate aggregated processes (26 LCI_RESULT)",
            "lcia_method": "None bundled in export (0 lcia_methods in JSON-LD; requires external TRACI/IPCC/EF characterization factors)",
            "file_path": "data/raw/uslci/",
            "identification_confidence": "high",
            "data_type": "published-reference (unit-process and LCI-result inventory flows)",
            "intended_use": (
                "Packaging material, conversion, recycled resin, fuel combustion, freight transport and end-of-life "
                "inventory reference for BOM-based packaging and logistics modelling"
            ),
            "limitations": (
                "No bundled LCIA characterization methods; 97 Bridge Processes (including all 27 US Electricity Baseline "
                "bridges and 55 USEEIO bridges such as Flat glass Bridge) have 0 elementary flows and unlinked upstream "
                "inputs (2,171 of 6,833 product-flow inputs lack an internal provider in this standalone export); "
                "no container glass or liquid packaging board (LPB) process; non-uniform reference units (sh tn, Mg, 1000 kg); "
                "no cost or price data"
            ),
        },
        {
            "dataset_id": "anl_nist_regional_plastics_2024",
            "title": "Life-Cycle Analysis Datasets for Regionalized Plastic Pathways (ANL/ESIA-24/3)",
            "provider": "Argonne National Laboratory (ANL) and National Institute of Standards and Technology (NIST)",
            "version": "ANL/ESIA-24/3 (February 2024)",
            "url": "https://www.osti.gov/ (Report ANL/ESIA-24/3)",
            "download_date": "2026-11-11",
            "licence": "U.S. Government / DOE OSTI Public Technical Report",
            "geography": "USA, Western Europe, MENA (Middle East and North Africa), China, and 4-region Cross-regional average",
            "reference_year": "2024 report (GREET 2022 model; 2020 IEA electricity/NG data; 2010-2016 baseline technology shares with 2019-2022 sensitivity)",
            "functional_unit": (
                "1 kg of virgin plastic resin (PET, HDPE, LDPE, PP, PVC) or 1 kg of olefin monomer (ethylene, propylene); "
                "also 1 kWh electricity and 1 MJ natural gas in Figure 18"
            ),
            "system_boundary": (
                "Cradle-to-gate virgin resin / monomer production (raw material extraction through monomer and "
                "polymerization at plant gate; excludes package conversion, transport to dairy, filling and end-of-life)"
            ),
            "lcia_method": "GREET 2022 100-year GHG Carbon Intensity (kg CO2e / kg, covering CO2, CH4, N2O)",
            "file_path": "data/raw/[2024  Taemin Kim] Life-Cycle Analysis Datasets for Regionalized Plastic Pathways.pdf.pdf",
            "identification_confidence": "high",
            "data_type": "published-reference (PDF report tables and figure values)",
            "intended_use": (
                "Regionalized cradle-to-gate carbon intensity factors for virgin PET, HDPE, LDPE, PP and PVC resins "
                "and sensitivity to monomer/feedstock pathways and regional electricity grids"
            ),
            "limitations": (
                "Cradle-to-gate virgin resin only (not a complete package LCA; excludes blow molding/thermoforming and EoL); "
                "MENA is a macro-regional proxy, not Uzbekistan; covers GHG carbon intensity only (no water/eutrophication); "
                "prose on p. 28 misstates USA PTA-based PET CI as 1.92 (China's value) whereas Table 5 shows 1.75; "
                "filename has double .pdf.pdf suffix"
            ),
        },
        {
            "dataset_id": "ifc_wbg_ehs_dairy_2007",
            "title": "Environmental, Health, and Safety (EHS) Guidelines for Dairy Processing",
            "provider": "International Finance Corporation (IFC) / World Bank Group (citing Nordic Council of Ministers 2001 & EDA 2002 / EC 2006)",
            "version": "April 30, 2007",
            "url": "https://www.ifc.org/ehsguidelines (111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf)",
            "download_date": "2026-11-11",
            "licence": "World Bank Group / IFC Public EHS Guideline Terms",
            "geography": "International guideline; Table 2-3 benchmarks from European, Swedish, Danish, Finnish and Norwegian dairies",
            "reference_year": "2007 publication (underlying plant survey benchmarks from 2001-2002 / EC 2006 BREF)",
            "functional_unit": (
                "Per unit of processed milk or product: L/L processed milk, kWh/L processed milk, Liters/L processed milk, "
                "kg/1000 l (solid waste), L/kg ice cream, KWh/kg ice cream; mg/l, pH, degC, MPN/100 ml for effluent guidelines"
            ),
            "system_boundary": (
                "Gate-to-gate dairy processing facility operations (milk reception, processing, CIP cleaning, utilities, "
                "wastewater discharge and solid waste; excludes raw milk farming and upstream packaging manufacture)"
            ),
            "lcia_method": "Operational intensity benchmarks and regulatory/guideline effluent concentration limits (not LCIA)",
            "file_path": "data/raw/111927-WP-ENGLISH-Dairy-Processing-PUBLIC.pdf",
            "identification_confidence": "high",
            "data_type": "published-reference (historical industry benchmark ranges and EHS effluent guidelines)",
            "intended_use": (
                "Sanity-check bounds and default proxy ranges for dairy plant water intake, energy consumption, "
                "wastewater discharge, solid waste generation and effluent pollutant limits; template for company data collection"
            ),
            "limitations": (
                "Published in 2007 from 2001-2002 European/Nordic dairy surveys (not current Uzbekistan plant data or regulation); "
                "values are wide plant-level ranges, not independent ML training observations; Ice cream energy cell (0.75-1.6 KWh/kg) "
                "spans all four Nordic country columns as a single merged cell"
            ),
        },
    ]

    manifest_rows: list[DatasetManifestRecord] = []
    for spec in specs:
        ds_id = spec["dataset_id"]
        ds_records = by_source.get(ds_id, [])
        manifest_rows.append(
            DatasetManifestRecord(
                dataset_id=ds_id,
                title=spec["title"],
                provider=spec["provider"],
                version=spec["version"],
                url=spec["url"],
                download_date=spec["download_date"],
                licence=spec["licence"],
                geography=spec["geography"],
                reference_year=spec["reference_year"],
                functional_unit=spec["functional_unit"],
                system_boundary=spec["system_boundary"],
                lcia_method=spec["lcia_method"],
                file_path=spec["file_path"],
                file_count=len(ds_records),
                total_size_bytes=sum(r.size_bytes for r in ds_records),
                sha256_checksum=dataset_checksum(ds_records),
                identification_confidence=spec["identification_confidence"],
                data_type=spec["data_type"],
                intended_use=spec["intended_use"],
                limitations=spec["limitations"],
            )
        )
    return manifest_rows


def write_inventory(records: list[FileRecord], out: Path = INVENTORY_CSV) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(FileRecord.__dataclass_fields__), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(asdict(r) for r in records)


def write_manifest(
    manifest_records: list[DatasetManifestRecord], out: Path = MANIFEST_CSV
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(DatasetManifestRecord.__dataclass_fields__),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(asdict(r) for r in manifest_records)


def main() -> None:
    records = build_inventory()
    write_inventory(records)
    manifest_records = build_dataset_manifest(records)
    write_manifest(manifest_records)
    print(f"{len(records)} files -> {INVENTORY_CSV.relative_to(PROJECT_ROOT)}")
    print(f"{len(manifest_records)} datasets -> {MANIFEST_CSV.relative_to(PROJECT_ROOT)}")
    for m in manifest_records:
        print(
            f"  {m.dataset_id}: {m.file_count} files, {m.total_size_bytes} bytes, "
            f"sha256={m.sha256_checksum[:16]}..."
        )


if __name__ == "__main__":
    main()
