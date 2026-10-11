import json
from pathlib import Path


FHIR_FOLDER = Path("data/fhir")
OUTPUT_FOLDER = Path("data/rag")
OUTPUT_FILE = OUTPUT_FOLDER / "clinical_documents.json"


def get_code_name(resource):
    code = resource.get("code", {})
    print(f"Resource code: {code}")  # Debugging line to check the content of 'code'
    if code.get("text"):
        return code["text"]

    coding = code.get("coding", [])

    if coding:
        return coding[0].get("display", "Unknown")

    return "Unknown"


def get_medication_name(resource):

    # Step 1: Check medicationCodeableConcept
    medication = resource.get(
        "medicationCodeableConcept",
        {}
    )

    if medication.get("text"):
        return medication["text"]

    coding = medication.get("coding", [])

    for code in coding:
        if code.get("display"):
            return code["display"]

    # Step 2: Check medicationReference
    medication_reference = resource.get(
        "medicationReference",
        {}
    )

    if medication_reference.get("display"):
        return medication_reference["display"]

    if medication_reference.get("reference"):
        return (
            "Medication reference: "
            + medication_reference["reference"]
        )

    # Step 3: Check newer FHIR medication field
    medication = resource.get("medication", {})

    if isinstance(medication, dict):

        concept = medication.get(
            "concept",
            {}
        )

        if concept.get("text"):
            return concept["text"]

        for code in concept.get("coding", []):
            if code.get("display"):
                return code["display"]

        reference = medication.get(
            "reference",
            {}
        )

        if isinstance(reference, dict):
            if reference.get("display"):
                return reference["display"]

            if reference.get("reference"):
                return (
                    "Medication reference: "
                    + reference["reference"]
                )

    return "Unknown medication"

def create_documents():

    documents = []

    patient_files = [
        file
        for file in FHIR_FOLDER.glob("*.json")
        if not file.name.startswith("hospitalInformation")
        and not file.name.startswith("practitionerInformation")
    ]

    # IMPORTANT:
    # Work with only ONE patient first.
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

    patient_id = "Unknown"

    # First find patient ID
    for entry in entries:

        resource = entry.get("resource", {})

        if resource.get("resourceType") == "Patient":
            patient_id = resource.get(
                "id",
                "Unknown"
            )
            break

    # Create RAG documents
    for entry in entries:

        resource = entry.get("resource", {})

        resource_type = resource.get(
            "resourceType"
        )

        resource_id = resource.get(
            "id",
            "Unknown"
        )

        # ---------------------------
        # CONDITION
        # ---------------------------

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

        # ---------------------------
        # MEDICATION
        # ---------------------------

        elif resource_type == "MedicationRequest":

            name = get_medication_name(
                resource
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
                    "resource_type":
                        "MedicationRequest",
                    "resource_id": resource_id,
                    "date": date
                }
            })

        # ---------------------------
        # OBSERVATION
        # ---------------------------

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
                        "source_file":
                            patient_file.name,
                        "resource_type":
                            "Observation",
                        "resource_id":
                            resource_id,
                        "date": date
                    }
                })

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