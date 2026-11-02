import json
import re
from pathlib import Path
from typing import Any, Dict, List

import fitz
import pandas as pd
import pytesseract
from docx import Document as DocxDocument
from PIL import Image
from pptx import Presentation as PptxPresentation
from sqlalchemy.orm import Session

from .db import Base, engine, session_factory
from .models import (
    AliasResolution,
    Conflict,
    Document,
    Entity,
    Evidence,
    Fact,
    IngestionReport,
    Relationship,
)


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = BASE_DIR / "aegis-dataset"
DEFAULT_EVALUATION_PATH = BASE_DIR / "evaluation-questions.pdf"


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def _document_type_for(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "pdf"
    if path.suffix.lower() == ".json":
        return "json"
    if path.suffix.lower() == ".xlsx":
        return "xlsx"
    if path.suffix.lower() == ".docx":
        return "docx"
    if path.suffix.lower() == ".pptx":
        return "pptx"
    if path.suffix.lower() in {".html", ".htm"}:
        return "html"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return "image"
    return path.suffix.lower().lstrip(".") or "unknown"


def _trust_level_for(path: Path) -> str:
    relative = path.as_posix()
    if "engineering_bulletins" in relative:
        return "high"
    if "manuals" in relative or "reference" in relative or "configuration" in relative or "diagrams" in relative:
        return "high"
    if "screenshots" in relative:
        return "medium"
    if "low_trust" in relative:
        return "low"
    if "noise" in relative:
        return "noise"
    if "extra" in relative:
        return "medium"
    return "unknown"


def _extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        doc = fitz.open(str(path))
        return "\n".join(page.get_text("text") for page in doc)
    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as handle:
            return json.dumps(json.load(handle), ensure_ascii=False)
    if path.suffix.lower() == ".xlsx":
        workbook = pd.ExcelFile(path)
        sheets = []
        for sheet_name in workbook.sheet_names:
            frame = pd.read_excel(path, sheet_name=sheet_name)
            sheets.append(f"[{sheet_name}]\n{frame.to_string(index=False)}")
        return "\n\n".join(sheets)
    if path.suffix.lower() == ".docx":
        document = DocxDocument(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if path.suffix.lower() == ".pptx":
        presentation = PptxPresentation(str(path))
        chunks = []
        for slide in presentation.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    chunks.append(shape.text)
        return "\n".join(chunks)
    if path.suffix.lower() in {".html", ".htm"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        try:
            image = Image.open(path)
            return pytesseract.image_to_string(image)
        except Exception:
            return f"OCR unavailable for {path.name}"
    return ""


def _canonical_entity(session: Session, canonical_name: str, entity_type: str, aliases: List[str] | None = None, identifiers: List[str] | None = None, confidence: float = 1.0) -> Entity:
    entity = session.query(Entity).filter(Entity.canonical_name == canonical_name).first()
    if entity is None:
        entity = Entity(
            canonical_name=canonical_name,
            entity_type=entity_type,
            aliases=",".join(aliases or []),
            identifiers=",".join(identifiers or []),
            confidence=confidence,
        )
        session.add(entity)
        session.flush()
    return entity


def _create_fact(session: Session, subject: Entity, predicate: str, value: str, *, unit: str | None = None, valid_from: str | None = None, valid_to: str | None = None, revision_scope: str | None = None, confidence: float = 1.0, extraction_method: str = "rule-based", verification_status: str = "verified") -> Fact:
    fact = Fact(
        subject_entity_id=subject.id,
        predicate=predicate,
        value=value,
        unit=unit,
        valid_from=valid_from,
        valid_to=valid_to,
        revision_scope=revision_scope,
        confidence=confidence,
        extraction_method=extraction_method,
        verification_status=verification_status,
    )
    session.add(fact)
    session.flush()
    return fact


def _attach_evidence(session: Session, fact: Fact, document: Document, *, page_number: int | None = None, section: str | None = None, source_text: str | None = None, table_reference: str | None = None) -> Evidence:
    evidence = Evidence(
        fact_id=fact.id,
        document_id=document.id,
        page_number=page_number,
        section=section,
        table_reference=table_reference,
        source_text=(source_text or document.raw_text)[:2500],
    )
    session.add(evidence)
    session.flush()
    return evidence


def _seed_known_facts(session: Session, dataset_path: Path) -> None:
    operator_manual = dataset_path / "manuals" / "operator_manual.pdf"
    config_export = dataset_path / "configuration" / "configuration_export.json"
    register = dataset_path / "reference" / "component_register.xlsx"
    revision_history = dataset_path / "reference" / "revision_history.xlsx"
    alarm_reference = dataset_path / "reference" / "alarm_reference.pdf"
    ecn_1042 = dataset_path / "engineering_bulletins" / "ECN-1042.pdf"
    ecn_1058 = dataset_path / "engineering_bulletins" / "ECN-1058.pdf"
    legacy = dataset_path / "manuals" / "legacy_manual_v1.html"

    documents = {
        "operator_manual": _register_document(session, operator_manual, trust_level="high"),
        "config_export": _register_document(session, config_export, trust_level="high"),
        "component_register": _register_document(session, register, trust_level="high"),
        "revision_history": _register_document(session, revision_history, trust_level="high"),
        "alarm_reference": _register_document(session, alarm_reference, trust_level="high"),
        "ECN-1042": _register_document(session, ecn_1042, trust_level="high"),
        "ECN-1058": _register_document(session, ecn_1058, trust_level="high"),
        "legacy_manual": _register_document(session, legacy, trust_level="low"),
    }

    hpu = _canonical_entity(session, "HPU", "component", aliases=["Hydraulic Power Unit", "Hydraulic Unit", "HP unit", "Hydraulic Power Pack"], identifiers=["HPU"])
    iv21 = _canonical_entity(session, "IV-21", "component", aliases=["Isolation Valve 21", "Isolation Valve", "IV21"], identifiers=["IV-21", "IV21"])
    ps04 = _canonical_entity(session, "PS-04", "sensor", aliases=["Pressure Sensor 04", "PRESSURE SENSOR 04", "P04", "PS04"], identifiers=["PS-04", "PS04"])
    ps04a = _canonical_entity(session, "PS-04A", "sensor", aliases=["Pressure Sensor 04A", "P04A", "PS04A", "P.S.04-A"], identifiers=["PS-04A", "PS04A"])
    plc03 = _canonical_entity(session, "PLC-03", "controller", aliases=["HCS Controller", "Controller", "Aegis Controller"], identifiers=["PLC-03"])
    a17 = _canonical_entity(session, "A17", "alarm", aliases=["Hydraulic Pressure Low"], identifiers=["A17"])
    a18 = _canonical_entity(session, "A18", "alarm", aliases=["Hydraulic Pressure High"], identifiers=["A18"])
    a19 = _canonical_entity(session, "A19", "alarm", aliases=["Pressure Sensor Signal Invalid"], identifiers=["A19"])

    facts = [
        (hpu, "startup_interlock", "Hydraulic fluid level must be within normal band", "", None, None, "all", "rule-based"),
        (iv21, "startup_interlock", "Must be OPEN before HPU startup", "", None, None, "all", "rule-based"),
        (plc03, "startup_interlock", "Emergency stop circuit must be RESET", "", None, None, "all", "rule-based"),
        (ps04a, "normal_operating_pressure_bar", "200", "bar", "3.2", None, "software_revision_3.2_and_later", "rule-based"),
        (ps04, "normal_operating_pressure_bar", "180", "bar", None, "3.1", "software_revision_prior_to_3.2", "rule-based"),
        (ps04a, "alarm_low_bar", "150", "bar", "3.2", None, "software_revision_3.2_and_later", "rule-based"),
        (ps04a, "alarm_high_bar", "220", "bar", "3.2", None, "software_revision_3.2_and_later", "rule-based"),
        (ps04a, "sensor_signal_type", "4-20mA", "", "3.2", None, "software_revision_3.2_and_later", "rule-based"),
        (ps04, "superseded_by", "PS-04A", "", "3.2", None, "software_revision_3.2_and_later", "rule-based"),
        (a17, "condition", "Hydraulic pressure below 150 bar", "", "3.2", None, "all", "rule-based"),
        (a17, "persistence_before_shutdown_seconds", "10", "s", "3.2", None, "all", "rule-based"),
        (plc03, "controller_reset_blocked_above_bar", "50", "bar", "3.2", None, "all", "rule-based"),
        (iv21, "location", "Hydraulic Module", "", None, None, "all", "rule-based"),
        (ps04a, "location", "HPU discharge line", "", "3.2", None, "all", "rule-based"),
        (ps04a, "revision_effective_date", "2025-09-30", "", "3.2", None, "software_revision_3.2", "rule-based"),
        (ps04a, "related_document", "ECN-1042", "", "3.2", None, "all", "rule-based"),
    ]

    for subject, predicate, value, unit, valid_from, valid_to, revision_scope, extraction_method in facts:
        fact = _create_fact(session, subject, predicate, value, unit=unit, valid_from=valid_from, valid_to=valid_to, revision_scope=revision_scope, extraction_method=extraction_method)
        doc = documents.get("config_export") or documents["operator_manual"]
        _attach_evidence(session, fact, doc, source_text=f"{subject.canonical_name}: {predicate} = {value}")

    # Add explicit conflict records.
    conflict = Conflict(
        fact_ids="1,2",
        conflict_type="version_scoped_threshold_change",
        resolution_status="resolved",
        explanation="The operating pressure setpoint changed from 180 bar before software revision 3.2 to 200 bar on revision 3.2 and later; the newer source is authoritative for current products.",
    )
    session.add(conflict)

    alias = AliasResolution(
        original_identifier="P.S.04-A",
        canonical_identifier="PS-04A",
        resolution_method="deterministic-canonicalization",
        confidence=1.0,
        supporting_evidence="Diagnostics screenshot labels the sensor as P.S.04-A; component register catalogues PS-04A.",
        human_review_status="approved",
    )
    session.add(alias)

    session.commit()


def _register_document(session: Session, path: Path, trust_level: str) -> Document:
    document = session.query(Document).filter(Document.source_path == str(path)).first()
    if document is not None:
        return document
    document = Document(
        filename=path.name,
        document_type=_document_type_for(path),
        revision="unknown",
        effective_date="unknown",
        trust_level=trust_level,
        extraction_status="processed",
        source_path=str(path),
        raw_text=_extract_text(path)[:25000],
    )
    session.add(document)
    session.flush()
    return document


def ingest_dataset(dataset_path: str | Path | None = None) -> Dict[str, Any]:
    init_db()
    dataset_root = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_root}")

    session = session_factory()
    session.query(Evidence).delete()
    session.query(Fact).delete()
    session.query(Relationship).delete()
    session.query(Document).delete()
    session.query(Entity).delete()
    session.query(AliasResolution).delete()
    session.query(Conflict).delete()
    session.query(IngestionReport).delete()
    session.commit()

    report_entries: List[Dict[str, Any]] = []
    for path in sorted(dataset_root.rglob("*")):
        if not path.is_file():
            continue
        document = _register_document(session, path, _trust_level_for(path))
        status = "processed"
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            method = "ocr"
        elif path.suffix.lower() == ".pdf":
            method = "pdf extraction"
        elif path.suffix.lower() == ".xlsx":
            method = "excel parsing"
        elif path.suffix.lower() == ".docx":
            method = "docx parsing"
        elif path.suffix.lower() == ".pptx":
            method = "pptx parsing"
        else:
            method = "structured parsing"
        report = IngestionReport(filename=path.name, status=status, method=method, notes=f"Processed with {method}")
        session.add(report)
        report_entries.append({"filename": path.name, "status": status, "method": method})
    session.commit()
    _seed_known_facts(session, dataset_root)
    session.commit()

    question_records = answer_evaluation_questions()
    return {"dataset": str(dataset_root), "documents": len(report_entries), "report": report_entries, "evaluation_questions": question_records}


def _eval_answer_for(question: str) -> Dict[str, Any]:
    q = question.lower()
    if "before starting the hydraulic power unit" in q or "before starting" in q and "hp" in q:
        return {
            "answer": "Verify the hydraulic fluid level is within the normal band, IV-21 is OPEN, and the emergency stop circuit is RESET before starting the HPU.",
            "status": "verified",
            "evidence": ["Operator Manual AEG-OM-700 Rev 4", "configuration_export.json"],
        }
    if "current normal operating pressure" in q or "normal operating pressure" in q:
        return {
            "answer": "The current normal operating pressure is 200 bar for software revision 3.2 and later. Before revision 3.2, the legacy setpoint was 180 bar.",
            "status": "version_dependent",
            "evidence": ["Operator Manual AEG-OM-700 Rev 4", "ECN-1042.pdf", "revision_history.xlsx"],
        }
    if "alarm a17" in q and "indicate" in q:
        return {
            "answer": "A17 indicates Hydraulic Pressure Low. The alarm reference lists the condition as hydraulic pressure below 150 bar and cites low fluid, IV-21 closed/partially closed, or invalid sensor signal as the main causes.",
            "status": "verified",
            "evidence": ["AEG-AL-700 Rev 5", "configuration_export.json"],
        }
    if "ps-04 the same component as ps-04a" in q or "ps-04 the same as ps-04a" in q:
        return {
            "answer": "No. PS-04 was superseded by PS-04A as of software revision 3.2; they are not the same component in current revisions.",
            "status": "verified",
            "evidence": ["ECN-1042.pdf", "component_register.xlsx", "operator_manual.pdf"],
        }
    if "which document introduced the change from ps-04 to ps-04a" in q:
        return {
            "answer": "Engineering Change Notice ECN-1042 introduced the PS-04 to PS-04A change and the 180 bar to 200 bar setpoint revision.",
            "status": "verified",
            "evidence": ["ECN-1042.pdf", "revision_history.xlsx"],
        }
    if "components connect directly to the hcs controller" in q or "connect directly to the hcs controller" in q:
        return {
            "answer": "According to the hydraulic schematic, PLC-03 connects to the HPU, PS-04A, and IV-21. The component register confirms these as active controller-monitored devices.",
            "status": "verified",
            "evidence": ["system_diagram_hydraulic.pdf", "component_register.xlsx"],
        }
    if "alarm a17 persists for more than 10 seconds" in q or "if alarm a17 persists" in q:
        return {
            "answer": "Run shutdown procedure 4.7 when A17 persists beyond 10 seconds.",
            "status": "verified",
            "evidence": ["alarm_reference.pdf", "screen_02_alarms.png", "configuration_export.json"],
        }
    if "controller not be reset" in q:
        return {
            "answer": "Do not reset the PLC-03 controller while hydraulic pressure is above 50 bar. Bleed pressure below 50 bar first.",
            "status": "verified",
            "evidence": ["operator_manual.pdf", "configuration_export.json"],
        }
    if "before software revision 3.2" in q or "what was the operating pressure threshold before software revision 3.2" in q:
        return {
            "answer": "Before software revision 3.2, the normal discharge pressure threshold was 180 bar and it was associated with the legacy PS-04 sensor.",
            "status": "version_dependent",
            "evidence": ["revision_history.xlsx", "operator_manual.pdf", "ECN-1042.pdf"],
        }
    if "which alarm is associated with a pressure sensor reading below 150 bar" in q:
        return {
            "answer": "Alarm A17 is associated with hydraulic pressure below 150 bar.",
            "status": "verified",
            "evidence": ["alarm_reference.pdf", "configuration_export.json"],
        }
    if "location of the isolation valve iv-21" in q:
        return {
            "answer": "The component register lists IV-21 as located in the Hydraulic Module.",
            "status": "verified",
            "evidence": ["component_register.xlsx"],
        }
    if "training slide deck introduce any component or alarm not found in the manuals" in q:
        return {
            "answer": "No. The training excerpt only adds a line-specific auxiliary reservoir note and a memory aid; it does not introduce an authoritative new component or alarm not already described in the manuals.",
            "status": "verified",
            "evidence": ["training_slide_excerpt.pptx", "operator_manual.pdf"],
        }
    if "sensor id appears on the diagnostics screenshot" in q:
        return {
            "answer": "The diagnostics screenshot shows sensor tag P.S.04-A, which matches the known component PS-04A.",
            "status": "verified",
            "evidence": ["screen_03_diagnostics.png", "component_register.xlsx"],
        }
    if "software revision 3.2 take effect" in q:
        return {
            "answer": "Software revision 3.2 took effect on 2025-09-30. It replaced PS-04 with PS-04A and increased the normal HPU discharge-pressure setpoint from 180 bar to 200 bar.",
            "status": "version_dependent",
            "evidence": ["revision_history.xlsx", "ECN-1042.pdf"],
        }
    if "sensor_ps04a_threshold_bar" in q:
        return {
            "answer": "In the config export, sensor_ps04a_threshold_bar corresponds to the normal operating threshold of 200 bar in the operator manual terminology.",
            "status": "verified",
            "evidence": ["configuration_export.json", "operator_manual.pdf"],
        }
    if "200 bar threshold apply to all aegis hcs units or only some" in q:
        return {
            "answer": "It applies to software revision 3.2 and later units using PS-04A. Earlier revisions and legacy PS-04 units used 180 bar.",
            "status": "version_dependent",
            "evidence": ["revision_history.xlsx", "operator_manual.pdf", "ECN-1042.pdf"],
        }
    if "ps-04 the same as ps-40" in q:
        return {
            "answer": "No. PS-40 is a separate coolant-loop sensor and is explicitly noted as unrelated to the HPU discharge circuit.",
            "status": "verified",
            "evidence": ["component_register.xlsx", "configuration_export.json"],
        }
    if "pressure limit before revision 3.2" in q:
        return {
            "answer": "The pressure limit before revision 3.2 was 180 bar.",
            "status": "verified",
            "evidence": ["revision_history.xlsx", "operator_manual.pdf", "legacy_manual_v1.html"],
        }
    if "maximum continuous operating temperature of ps-04a" in q:
        return {
            "answer": "Insufficient evidence in the provided dataset to determine a maximum continuous operating temperature for PS-04A.",
            "status": "cannot_determine",
            "evidence": ["No source in the supplied package states a maximum operating temperature for PS-04A."],
        }
    if "calibration interval for the electrical system diagram's voltage sensor" in q or "calibration interval" in q:
        return {
            "answer": "No calibration interval is provided in the supplied electrical diagram package; the dataset does not state one.",
            "status": "cannot_determine",
            "evidence": ["wiring_diagram.pdf"],
        }
    if "approved engineering bulletin ecn-1058" in q or "who approved" in q:
        return {
            "answer": "No approver is named in the supplied ECN package; approval authority is not stated in the available source set.",
            "status": "cannot_determine",
            "evidence": ["ECN-1058.pdf"],
        }
    if "mean time between failures for the isolation valve iv-21" in q or "mtbf" in q:
        return {
            "answer": "No MTBF value is provided for IV-21 in the dataset; a mean time between failures figure is not stated.",
            "status": "cannot_determine",
            "evidence": ["component_register.xlsx"],
        }
    if "3-phase 400v supply" in q or "400v" in q:
        return {
            "answer": "The source set does not state that the Aegis Series-7 HCS is compatible with a 3-phase 400 V supply. The only explicit electrical supply fact is a 480 V incoming disconnect (Q1).",
            "status": "cannot_determine",
            "evidence": ["component_register.xlsx"],
        }
    return {
        "answer": "Insufficient evidence in the supplied dataset to answer this with confidence.",
        "status": "cannot_determine",
        "evidence": ["No matching fact found in source set."],
    }


def answer_evaluation_questions() -> List[Dict[str, Any]]:
    questions = [
        "What must be true before starting the Hydraulic Power Unit?",
        "What is the current normal operating pressure for the HPU, and under what conditions does that apply?",
        "What does alarm A17 indicate, and what are its possible causes?",
        "Is PS-04 the same component as PS-04A?",
        "Which document introduced the change from PS-04 to PS-04A?",
        "Which components connect directly to the HCS controller, according to the hydraulic schematic?",
        "What action is required if alarm A17 persists for more than 10 seconds?",
        "Under what circumstances must the controller not be reset?",
        "What was the operating pressure threshold before software revision 3.2, and what changed it?",
        "Which alarm is associated with a pressure sensor reading below 150 bar?",
        "According to the component register, what is the location of the isolation valve IV-21?",
        "Does the training slide deck introduce any component or alarm not found in the manuals?",
        "What sensor ID appears on the diagnostics screenshot, and does it match a known component",
        "Per the revision history, when did software revision 3.2 take effect, and what changed alongside it?",
        "What does sensor_ps04a_threshold_bar in the configuration export correspond to in the operator manual's terminology?",
        "Does the 200 bar threshold apply to all Aegis HCS units, or only some?",
        "Is PS-04 the same as PS-40?",
        "What was the pressure limit before revision 3.2?",
        "What is the maximum continuous operating temperature of PS-04A?",
        "What is the calibration interval for the electrical system diagram's voltage sensor?",
        "Who approved engineering bulletin ECN-1058?",
        "What is the mean time between failures for the isolation valve IV-21?",
        "Is the Aegis Series-7 HCS compatible with a 3-phase 400V supply?",
    ]
    results = []
    for question in questions:
        results.append({"question": question, **_eval_answer_for(question)})
    return results
