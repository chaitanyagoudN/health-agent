
import json
from pathlib import Path


FHIR_FOLDER = Path("data/fhir")
OUTPUT_FOLDER = Path("data/rag")
OUTPUT_FILE = OUTPUT_FOLDER / "clinical_documents.json"


# --------------------------------------------------
# GET CONDITION / OBSERVATION NAME
# --------------------------------------------------

def get_code_name(resource):

    code = resource.get("code", {})

    if code.get("text"):
        return code["text"]

    coding = code.get("coding", [])

    for item in coding:
        if item.get("display"):
            return item["display"]

    return "Unknown"


# --------------------------------------------------
# GET MEDICATION NAME
# --------------------------------------------------

def get_medication_name(resource, resource_lookup):

    # Step 1: Check medicationCodeableConcept

    medication = resource.get(
        "medicationCodeableConcept",
        {}
    )

    if medication.get("text"):
        return medication["text"]

    for code in medication.get("coding", []):
        if code.get("display"):
            return code["display"]

    # Step 2: Check medicationReference

    medication_reference = resource.get(
        "medicationReference",
        {}
    )

    reference = medication_reference.get("reference")

    # Resolve reference using FHIR Bundle lookup
    if reference:

        referenced_resource = resource_lookup.get(reference)

        if referenced_resource:

            if referenced_resource.get("resourceType") == "Medication":

                medication_code = referenced_resource.get(
                    "code",
                    {}
                )

                if medication_code.get("text"):
                    return medication_code["text"]

                for code in medication_code.get("coding", []):
                    if code.get("display"):
                        return code["display"]

        # If reference cannot be resolved, use display
        if medication_reference.get("display"):
            return medication_reference["display"]

        return "Medication reference: " + reference

    if medication_reference.get("display"):
        return medication_reference["display"]

    # Step 3: Check newer FHIR medication field

    medication = resource.get("medication", {})

    if isinstance(medication, dict):

        concept = medication.get("concept", {})

        if concept.get("text"):
            return concept["text"]

        for code in concept.get("coding", []):
            if code.get("display"):
                return code["display"]

        medication_ref = medication.get("reference", {})

        if isinstance(medication_ref, dict):

            reference = medication_ref.get("reference")

            if reference:

                referenced_resource = resource_lookup.get(reference)

                if referenced_resource:

                    if referenced_resource.get("resourceType") == "Medication":

                        medication_code = referenced_resource.get(
                            "code",
                            {}
                        )

                        if medication_code.get("text"):
                            return medication_code["text"]

                        for code in medication_code.get("coding", []):
                            if code.get("display"):
                                return code["display"]

                if medication_ref.get("display"):
                    return medication_ref["display"]

                return "Medication reference: " + reference

            if medication_ref.get("display"):
                return medication_ref["display"]

    return "Unknown medication"


# --------------------------------------------------
# CREATE CLINICAL DOCUMENTS
# --------------------------------------------------

def create_documents():

    documents = []

    patient_files = [
        file
        for file in FHIR_FOLDER.glob("*.json")
        if not file.name.startswith("hospitalInformation")
        and not file.name.startswith("practitionerInformation")
    ]

    # Work with one patient first
    if not patient_files:
        print("No FHIR patient files found.")
        return

    patient_file = patient_files[0]

    print("Processing patient file:")
    print(patient_file.name)

    with open(
        patient_file,
        "r",
        encoding="utf-8"
    ) as file:
        bundle = json.load(file)

    entries = bundle.get("entry", [])

    # --------------------------------------------------
    # BUILD FHIR RESOURCE LOOKUP
    # --------------------------------------------------

    resource_lookup = {}

    for entry in entries:

        full_url = entry.get("fullUrl")
        resource = entry.get("resource", {})

        if full_url:
            resource_lookup[full_url] = resource

        # Also support relative references like Medication/123
        if resource.get("resourceType") and resource.get("id"):

            relative_reference = (
                resource["resourceType"]
                + "/"
                + resource["id"]
            )

            resource_lookup[relative_reference] = resource

    print(
        "FHIR resource lookup created:",
        len(resource_lookup),
        "entries"
    )

    # --------------------------------------------------
    # FIND PATIENT ID
    # --------------------------------------------------

    patient_id = "Unknown"

    for entry in entries:

        resource = entry.get("resource", {})

        if resource.get("resourceType") == "Patient":

            patient_id = resource.get(
                "id",
                "Unknown"
            )

            break

    # --------------------------------------------------
    # CREATE RAG DOCUMENTS
    # --------------------------------------------------

    for entry in entries:

        resource = entry.get("resource", {})

        resource_type = resource.get(
            "resourceType"
        )

        resource_id = resource.get(
            "id",
            "Unknown"
        )

        # --------------------------------------------------
        # CONDITION
        # --------------------------------------------------

        if resource_type == "Condition":

            name = get_code_name(resource)

            date = resource.get(
                "onsetDateTime"
            )

            text = f"Condition: {name}"

            if date:
                text += f". Onset date: {date}"

            documents.append({
                "text": text,
                "metadata": {
                    "patient_id": patient_id,
                    "source": "FHIR",
                    "source_file": patient_file.name,
                    "resource_type": "Condition",
                    "resource_id": resource_id,
                    "date": date
                }
            })

        # --------------------------------------------------
        # MEDICATION REQUEST
        # --------------------------------------------------

        elif resource_type == "MedicationRequest":

            # Resolve medication name
            name = get_medication_name(
                resource,
                resource_lookup
            )

            status = resource.get(
                "status",
                "Unknown"
            )

            date = resource.get(
                "authoredOn"
            )

            text = (
                f"Medication: {name}. "
                f"Status: {status}"
            )

            if date:
                text += f". Ordered: {date}"

            documents.append({
                "text": text,
                "metadata": {
                    "patient_id": patient_id,
                    "source": "FHIR",
                    "source_file": patient_file.name,
                    "resource_type": "MedicationRequest",
                    "resource_id": resource_id,
                    "date": date
                }
            })

        # --------------------------------------------------
        # OBSERVATION
        # --------------------------------------------------

        elif resource_type == "Observation":

            name = get_code_name(resource)

            date = resource.get(
                "effectiveDateTime"
            )

            value_quantity = resource.get(
                "valueQuantity"
            )

            if value_quantity:

                value = value_quantity.get(
                    "value"
                )

                unit = value_quantity.get(
                    "unit",
                    ""
                )

                text = (
                    f"Observation: {name}. "
                    f"Value: {value} {unit}"
                )

                if date:
                    text += f". Date: {date}"

                documents.append({
                    "text": text,
                    "metadata": {
                        "patient_id": patient_id,
                        "source": "FHIR",
                        "source_file": patient_file.name,
                        "resource_type": "Observation",
                        "resource_id": resource_id,
                        "date": date
                    }
                })

    # --------------------------------------------------
    # SAVE CLINICAL DOCUMENTS
    # --------------------------------------------------

    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            documents,
            file,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("RAG documents created successfully.")
    print(f"Patient ID: {patient_id}")
    print(f"Documents created: {len(documents)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    create_documents()
