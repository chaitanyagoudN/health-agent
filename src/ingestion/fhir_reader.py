import json
from pathlib import Path


FHIR_FOLDER = Path("data/fhir")


def get_code_name(resource):
    code = resource.get("code", {})

    if code.get("text"):
        return code["text"]

    coding = code.get("coding", [])

    if coding:
        return coding[0].get("display", "Unknown")

    return "Unknown"


def get_medication_name(resource):
    medication = resource.get("medicationCodeableConcept", {})

    if medication.get("text"):
        return medication["text"]

    coding = medication.get("coding", [])

    if coding:
        return coding[0].get("display", "Unknown medication")

    return "Unknown medication"


def get_observation_value(observation):

    if "valueQuantity" in observation:
        quantity = observation["valueQuantity"]

        value = quantity.get("value", "")
        unit = quantity.get("unit", "")

        return f"{value} {unit}".strip()

    if "valueCodeableConcept" in observation:
        concept = observation["valueCodeableConcept"]

        if concept.get("text"):
            return concept["text"]

        coding = concept.get("coding", [])

        if coding:
            return coding[0].get("display", "Unknown")

    if "valueString" in observation:
        return observation["valueString"]

    return "No simple value"


def get_encounter_type(encounter):

    encounter_types = encounter.get("type", [])

    if encounter_types:
        encounter_type = encounter_types[0]

        if encounter_type.get("text"):
            return encounter_type["text"]

        coding = encounter_type.get("coding", [])

        if coding:
            return coding[0].get(
                "display",
                "Unknown encounter"
            )

    encounter_class = encounter.get("class", {})

    if encounter_class.get("display"):
        return encounter_class["display"]

    return "Unknown encounter"


def extract_patient_chart():

    files = list(FHIR_FOLDER.glob("*.json"))

    for file_path in files:

        if file_path.name.startswith("hospitalInformation"):
            continue

        if file_path.name.startswith("practitionerInformation"):
            continue

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        entries = data.get("entry", [])

        patient = None
        conditions = []
        medication_requests = []
        observations = []
        encounters = []

        # Collect resources
        for entry in entries:

            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")

            if resource_type == "Patient":
                patient = resource

            elif resource_type == "Condition":
                conditions.append(resource)

            elif resource_type == "MedicationRequest":
                medication_requests.append(resource)

            elif resource_type == "Observation":
                observations.append(resource)

            elif resource_type == "Encounter":
                encounters.append(resource)

        if patient:

            # =====================================
            # PATIENT INFORMATION
            # =====================================

            names = patient.get("name", [])

            if names:
                given_names = names[0].get("given", [])
                family_name = names[0].get("family", "")
                full_name = " ".join(
                    given_names + [family_name]
                )
            else:
                full_name = "Unknown"

            patient_id = patient.get("id", "Unknown")
            gender = patient.get("gender", "Unknown")
            birth_date = patient.get(
                "birthDate",
                "Unknown"
            )

            print("=" * 60)
            print("PATIENT INFORMATION")
            print("=" * 60)

            print(f"Name: {full_name}")
            print(f"Patient ID: {patient_id}")
            print(f"Gender: {gender}")
            print(f"Date of Birth: {birth_date}")

            # =====================================
            # CONDITIONS
            # =====================================

            print()
            print("=" * 60)
            print("CONDITIONS / DIAGNOSES")
            print("=" * 60)

            print(
                f"Total conditions: {len(conditions)}"
            )

            print()

            for number, condition in enumerate(
                conditions,
                start=1
            ):

                condition_name = get_code_name(
                    condition
                )

                onset_date = condition.get(
                    "onsetDateTime",
                    "Date not available"
                )

                print(
                    f"{number}. {condition_name} | "
                    f"Onset: {onset_date}"
                )

            # =====================================
            # MEDICATIONS
            # =====================================

            print()
            print("=" * 60)
            print("MEDICATION REQUESTS")
            print("=" * 60)

            print(
                f"Total medication requests: "
                f"{len(medication_requests)}"
            )

            print()

            for number, medication in enumerate(
                medication_requests,
                start=1
            ):

                medication_name = get_medication_name(
                    medication
                )

                status = medication.get(
                    "status",
                    "Unknown"
                )

                authored_date = medication.get(
                    "authoredOn",
                    "Date not available"
                )

                print(f"{number}. {medication_name}")
                print(f"   Status: {status}")
                print(f"   Ordered: {authored_date}")
                print()

            # =====================================
            # OBSERVATIONS / LABS
            # =====================================

            print()
            print("=" * 60)
            print("OBSERVATIONS / LABS")
            print("=" * 60)

            print(
                f"Total observations: "
                f"{len(observations)}"
            )

            print()

            important_terms = [
                "glucose",
                "hemoglobin a1c",
                "glycated hemoglobin",
                "cholesterol",
                "triglyceride",
                "creatinine",
                "hemoglobin",
                "sodium",
                "potassium",
                "chloride",
                "carbon dioxide",
                "body mass index",
                "bmi",
                "body weight",
                "heart rate",
                "systolic blood pressure",
                "diastolic blood pressure",
                "smoking status"
            ]

            important_observations = []

            for observation in observations:

                observation_name = get_code_name(
                    observation
                )

                name_lower = observation_name.lower()

                if any(
                    term in name_lower
                    for term in important_terms
                ):
                    important_observations.append(
                        observation
                    )

            print(
                f"Important observations found: "
                f"{len(important_observations)}"
            )

            print()

            for number, observation in enumerate(
                important_observations[-30:],
                start=1
            ):

                observation_name = get_code_name(
                    observation
                )

                observation_value = get_observation_value(
                    observation
                )

                observation_date = observation.get(
                    "effectiveDateTime",
                    "Date not available"
                )

                print(f"{number}. {observation_name}")
                print(
                    f"   Value: {observation_value}"
                )
                print(
                    f"   Date: {observation_date}"
                )
                print()

            # =====================================
            # ENCOUNTERS
            # =====================================

            print()
            print("=" * 60)
            print("ENCOUNTERS")
            print("=" * 60)

            print(
                f"Total encounters: {len(encounters)}"
            )

            print()

            # Show latest 15 encounters
            latest_encounters = encounters[-15:]

            for number, encounter in enumerate(
                latest_encounters,
                start=1
            ):

                encounter_type = get_encounter_type(
                    encounter
                )

                status = encounter.get(
                    "status",
                    "Unknown"
                )

                period = encounter.get(
                    "period",
                    {}
                )

                start_date = period.get(
                    "start",
                    "Date not available"
                )

                end_date = period.get(
                    "end",
                    "Date not available"
                )

                print(
                    f"{number}. {encounter_type}"
                )

                print(
                    f"   Status: {status}"
                )

                print(
                    f"   Start: {start_date}"
                )

                print(
                    f"   End: {end_date}"
                )

                print()

            print("=" * 60)

            return


if __name__ == "__main__":
    extract_patient_chart()