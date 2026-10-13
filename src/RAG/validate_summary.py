
# import json
# import re
# from pathlib import Path

# summary_path = Path("data/normalized/patient_chart_summary.json")
# documents_path = Path("data/rag/clinical_documents.json")

# with open(documents_path, "r", encoding="utf-8") as file:
#     clinical_documents = json.load(file)

# resource_lookup = {}

# for document in clinical_documents:
#     metadata = document["metadata"]

#     key = (
#         metadata["resource_type"],
#         metadata["resource_id"]
#     )

#     resource_lookup[key] = document

# print(f"Loaded {len(resource_lookup)} clinical resources for verification.")

# with open(summary_path, "r", encoding="utf-8") as file:
#     summary = json.load(file)

# expected_fields = {
#     "medical_history": {"condition", "status", "citations"},
#     "medications": {"name", "order_status", "citations"},
#     "laboratory_results": {"test", "value", "unit", "date", "citations"}
# }

# expected_types = {
#     "medical_history": "Condition",
#     "medications": "MedicationRequest",
#     "laboratory_results": "Observation"
# }

# errors = []


# if not summary.get("patient_id"):
#     errors.append("Missing patient_id")

# for section, fields in expected_fields.items():
#     items = summary.get(section)

#     if not isinstance(items, list):
#         errors.append(f"{section} must be a list")
#         continue

#     for index, item in enumerate(items, start=1):
#         if not isinstance(item, dict):
#             errors.append(f"{section} item {index} is not an object")
#             continue

#         missing = fields - item.keys()
#         if missing:
#             errors.append(f"{section} item {index}: missing {missing}")

#         citations = item.get("citations", [])
#         if not isinstance(citations, list) or not citations:
#             errors.append(f"{section} item {index}: missing citations")
#             continue

#         for citation in citations:
#             pattern = (
#                 r"\[FHIR "
#                 + expected_types[section]
#                 + r": [^\[\]]+\]"
#             )

#             if not isinstance(citation, str) or not re.fullmatch(pattern, citation):
#                 errors.append(f"Invalid citation in {section} item {index}")

# # --------------------------------------------------
# # VERIFY FHIR CITATIONS AGAINST SOURCE DOCUMENTS
# # --------------------------------------------------

# citation_pattern = re.compile(
#     r"^\[FHIR (Condition|MedicationRequest|Observation): ([^\[\]]+)\]$"
# )

# verified_citations = 0

# for section in expected_fields:

#     items = summary.get(section, [])

#     if not isinstance(items, list):
#         continue

#     for index, item in enumerate(items, start=1):

#         if not isinstance(item, dict):
#             continue

#         for citation in item.get("citations", []):

#             if not isinstance(citation, str):
#                 continue

#             match = citation_pattern.fullmatch(citation)

#             if not match:
#                 continue

#             resource_type = match.group(1)
#             resource_id = match.group(2)

#             key = (resource_type, resource_id)

#             document = resource_lookup.get(key)

#             if document is None:
#                 errors.append(
#                     f"{section} item {index}: "
#                     f"FHIR source not found: {citation}"
#                 )
#                 continue

#             source_patient_id = document["metadata"].get("patient_id")

#             if source_patient_id != summary["patient_id"]:
#                 errors.append(
#                     f"{section} item {index}: "
#                     f"Patient ID mismatch: {citation}"
#                 )
#                 continue

#             verified_citations += 1

# # --------------------------------------------------
# # VERIFY CLINICAL VALUES AGAINST SOURCE DOCUMENTS
# # --------------------------------------------------

# verified_values = 0

# for section, expected_type in expected_types.items():

#     for index, item in enumerate(summary.get(section, []), start=1):

#         if not isinstance(item, dict):
#             continue

#         citations = item.get("citations", [])

#         if not isinstance(citations, list):
#             continue

#         for citation in citations:

#             if not isinstance(citation, str):
#                 continue

#             match = citation_pattern.fullmatch(citation)

#             if not match:
#                 continue

#             resource_type, resource_id = match.groups()

#             if resource_type != expected_type:
#                 errors.append(
#                     f"{section} item {index}: Wrong resource type"
#                 )
#                 continue

#             document = resource_lookup.get(
#                 (resource_type, resource_id)
#             )

#             if document is None:
#                 continue

#             if document["metadata"].get("patient_id") != summary.get("patient_id"):
#                 continue

#             source_text = document["text"]

#             if section == "medical_history":

#                 condition = item.get("condition", "")

#                 if source_text.startswith(f"Condition: {condition}"):
#                     verified_values += 1
#                 else:
#                     errors.append(
#                         f"Condition mismatch: {condition}"
#                     )

#             elif section == "medications":

#                 name = item.get("name", "")
#                 status = item.get("order_status", "")

#                 expected_prefix = (
#                     f"Medication: {name}. Status: {status}"
#                 )

#                 if source_text.startswith(expected_prefix):
#                     verified_values += 1
#                 else:
#                     errors.append(
#                         f"Medication mismatch: {name}, {status}"
#                     )

#             elif section == "laboratory_results":

#                 test = item.get("test", "")
#                 value = item.get("value")
#                 unit = item.get("unit", "")
#                 date = item.get("date")

#                 expected_text = (
#                     f"Observation: {test}. Value: {value} {unit}"
#                 )

#                 source_date = document["metadata"].get("date")

#                 if (
#                     source_text.startswith(expected_text)
#                     and date == source_date
#                 ):
#                     verified_values += 1
#                 else:
#                     errors.append(
#                         f"Lab mismatch: {test}, {value}, {unit}, {date}"
#                     )

# print(f"Verified clinical values: {verified_values}")

# print(f"\nVerified FHIR citations: {verified_citations}")

# if errors:
    
#     print("VALIDATION FAILED")
#     for error in errors:
#         print("-", error)
# else:
#     print("VALIDATION PASSED")
#     print("Patient ID:", summary["patient_id"])
#     for section in expected_fields:
#         print(section, ":", len(summary[section]))
"""Validate a generated chart summary against patient-specific RAG documents."""
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

SECTIONS = {
    "medical_history": ("Condition", {"condition", "status", "citations"}),
    "medications": ("MedicationRequest", {"name", "order_status", "citations"}),
    "laboratory_results": ("Observation", {"test", "value", "unit", "date", "citations"}),
}
CITATION = re.compile(r"\[FHIR (Condition|MedicationRequest|Observation): ([^\[\]]+)\]")


def _same_number(first, second):
    """Compare numeric strings and JSON numbers without rounding."""
    if isinstance(first, bool) or isinstance(second, bool):
        return False
    try:
        return Decimal(str(first)) == Decimal(str(second))
    except (InvalidOperation, TypeError, ValueError):
        return False


def validate_chart_summary(summary, documents):
    """Return (errors, verified_count). Does not read or save summary files."""
    errors = []
    verified = 0
    if not isinstance(summary, dict):
        return ["Summary must be a JSON object"], 0
    patient_id = summary.get("patient_id")
    if not isinstance(patient_id, str) or not patient_id.strip():
        errors.append("Missing patient_id")
    if not isinstance(documents, list):
        return errors + ["Documents must be a list"], 0

    lookup = {}
    for document in documents:
        if not isinstance(document, dict):
            errors.append("Source document is not an object")
            continue
        metadata = document.get("metadata", {})
        key = (metadata.get("resource_type"), metadata.get("resource_id"))
        if key in lookup:
            errors.append(f"Duplicate source resource key: {key}")
        lookup[key] = document

    for section, (resource_type, required_fields) in SECTIONS.items():
        items = summary.get(section)
        if not isinstance(items, list):
            errors.append(f"{section} must be a list")
            continue
        if not items:
            errors.append(f"{section} is empty; completeness must be reviewed")
        for index, item in enumerate(items, 1):
            prefix = f"{section} item {index}"
            if not isinstance(item, dict):
                errors.append(f"{prefix}: not an object")
                continue
            missing = required_fields - item.keys()
            if missing:
                errors.append(f"{prefix}: missing {sorted(missing)}")
                continue
            citations = item["citations"]
            if not isinstance(citations, list) or not citations:
                errors.append(f"{prefix}: citations must be a nonempty list")
                continue
            for citation in citations:
                citation_match = CITATION.fullmatch(citation) if isinstance(citation, str) else None
                if not citation_match or citation_match.group(1) != resource_type:
                    errors.append(f"{prefix}: invalid citation {citation!r}")
                    continue
                document = lookup.get((resource_type, citation_match.group(2)))
                if document is None:
                    errors.append(f"{prefix}: source not found: {citation}")
                    continue
                metadata = document.get("metadata", {})
                if metadata.get("patient_id") != patient_id:
                    errors.append(f"{prefix}: patient mismatch: {citation}")
                    continue
                source = document.get("text", "")
                valid = False
                if section == "medical_history":
                    actual = source.removeprefix("Condition: ").split(". Onset date: ", 1)[0]
                    valid = (source.startswith("Condition: ") and
                             item["condition"] == actual and item["status"] == "unknown")
                elif section == "medications":
                    match_med = re.fullmatch(
                        r"Medication: (.*?)\. Status: (.*?)(?:\. Ordered: (.*))?", source
                    )
                    valid = (match_med is not None and
                             item["name"] == match_med.group(1) and
                             item["order_status"] == match_med.group(2))
                elif section == "laboratory_results":
                    # Source convention: Observation: NAME. Value: VALUE UNIT. Date: DATE
                    match_obs = re.fullmatch(
                        r"Observation: (.*?)\. Value: (.*?) (.*?)\. Date: (.*)", source
                    )
                    if match_obs:
                        test, raw_value, unit, date = match_obs.groups()
                        valid = (item["test"] == test and
                                 _same_number(item["value"], raw_value) and
                                 item["unit"] == unit and
                                 item["date"] == date == metadata.get("date"))
                if valid:
                    verified += 1
                else:
                    errors.append(f"{prefix}: clinical value mismatch: {citation}")
    return errors, verified


if __name__ == "__main__":
    summary = json.loads(Path("data/normalized/patient_chart_summary.json").read_text(encoding="utf-8"))
    documents = json.loads(Path("data/rag/clinical_documents.json").read_text(encoding="utf-8"))
    errors, count = validate_chart_summary(summary, documents)
    print(f"Verified clinical citations and values: {count}")
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print("-", error)
        raise SystemExit(1)
    print("VALIDATION PASSED")

