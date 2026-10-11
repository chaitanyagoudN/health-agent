import json
from pathlib import Path


FHIR_FOLDER = Path("data/fhir")
OUTPUT_FOLDER = Path("data/normalized")
OUTPUT_FILE = OUTPUT_FOLDER / "patient_summary.json"


def get_code_name(resource):
    code = resource.get("code", {})

    if code.get("text"):
        return code["text"]

    coding = code.get("coding", [])

    if coding:
        return coding[0].get("display", "Unknown")

    return "Unknown"


def get_medication_name(resource):
    medication = resource.get(
        "medicationCodeableConcept",
        {}
    )

    if medication.get("text"):
        return medication["text"]

    coding = medication.get("coding", [])

    if coding:
        return coding[0].get(
            "display",
            "Unknown medication"
        )

    return "Unknown medication"


def get_observation_value(observation):

    if "valueQuantity" in observation:
        quantity = observation["valueQuantity"]

        return {
            "value": quantity.get("value"),
            "unit": quantity.get("unit", "")
        }

    if "valueCodeableConcept" in observation:
        concept = observation["valueCodeableConcept"]

        if concept.get("text"):
            return {
                "value": concept["text"],
                "unit": ""
            }

        coding = concept.get("coding", [])

        if coding:
            return {
                "value": coding[0].get(
                    "display",
                    "Unknown"
                ),
                "unit": ""
            }

    if "valueString" in observation:
        return {
            "value": observation["valueString"],
            "unit": ""
        }

    # Handle blood pressure components
    components = observation.get(
        "component",
        []
    )

    if components:
        results = []

        for component in components:

            name = get_code_name(component)

            quantity = component.get(
                "valueQuantity",
                {}
            )

            value = quantity.get("value")
            unit = quantity.get("unit", "")

            if value is not None:
                results.append({
                    "name": name,
                    "value": value,
                    "unit": unit
                })

        if results:
            return {
                "components": results
            }

    return {
        "value": None,
        "unit": ""
    }


def create_patient_summary():

    files = list(
        FHIR_FOLDER.glob("*.json")
    )

    for file_path in files:

        if file_path.name.startswith(
            "hospitalInformation"
        ):
            continue

        if file_path.name.startswith(
            "practitionerInformation"
        ):
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
        medications = []
        observations = []
        encounters = []

        for entry in entries:

            resource = entry.get(
                "resource",
                {}
            )

            resource_type = resource.get(
                "resourceType"
            )

            if resource_type == "Patient":
                patient = resource

            elif resource_type == "Condition":
                conditions.append(resource)

            elif resource_type == "MedicationRequest":
                medications.append(resource)

            elif resource_type == "Observation":
                observations.append(resource)

            elif resource_type == "Encounter":
                encounters.append(resource)

        if patient is None:
            continue

        # ---------------------------------
        # PATIENT
        # ---------------------------------

        names = patient.get("name", [])

        if names:
            given_names = names[0].get(
                "given",
                []
            )

            family_name = names[0].get(
                "family",
                ""
            )

            full_name = " ".join(
                given_names + [family_name]
            )

        else:
            full_name = "Unknown"

        patient_info = {
            "name": full_name,
            "patient_id": patient.get(
                "id",
                "Unknown"
            ),
            "gender": patient.get(
                "gender",
                "Unknown"
            ),
            "birth_date": patient.get(
                "birthDate",
                "Unknown"
            )
        }

        # ---------------------------------
        # CONDITIONS
        # ---------------------------------

        condition_list = []

        for condition in conditions:

            name = get_code_name(condition)

            if name not in condition_list:
                condition_list.append(name)

        # ---------------------------------
        # ACTIVE MEDICATIONS
        # ---------------------------------

        active_medications = []

        for medication in medications:

            status = medication.get(
                "status",
                ""
            )

            if status == "active":

                name = get_medication_name(
                    medication
                )

                if name not in active_medications:
                    active_medications.append(
                        name
                    )

        # ---------------------------------
        # LATEST HEALTH DATA
        # ---------------------------------

        important_terms = [
            "hemoglobin a1c",
            "glucose",
            "body weight",
            "body mass index",
            "bmi",
            "creatinine",
            "cholesterol",
            "triglyceride",
            "heart rate",
            "blood pressure",
            "smoking status"
        ]

        latest_health_data = {}

        for observation in observations:

            name = get_code_name(
                observation
            )

            if not any(
                term in name.lower()
                for term in important_terms
            ):
                continue

            date = observation.get(
                "effectiveDateTime",
                ""
            )

            result = get_observation_value(
                observation
            )

            if (
                name not in latest_health_data
                or date >
                latest_health_data[name]["date"]
            ):

                latest_health_data[name] = {
                    "date": date,
                    "result": result
                }

        # ---------------------------------
        # RECENT ENCOUNTERS
        # ---------------------------------

        encounter_list = []

        for encounter in encounters:

            encounter_types = encounter.get(
                "type",
                []
            )

            encounter_name = (
                "Unknown encounter"
            )

            if encounter_types:

                encounter_type = (
                    encounter_types[0]
                )

                if encounter_type.get("text"):

                    encounter_name = (
                        encounter_type["text"]
                    )

                else:

                    coding = (
                        encounter_type.get(
                            "coding",
                            []
                        )
                    )

                    if coding:
                        encounter_name = (
                            coding[0].get(
                                "display",
                                "Unknown encounter"
                            )
                        )

            period = encounter.get(
                "period",
                {}
            )

            start_date = period.get(
                "start",
                ""
            )

            if start_date:

                encounter_list.append({
                    "date": start_date,
                    "type": encounter_name
                })

        encounter_list.sort(
            key=lambda item: item["date"]
        )

        recent_encounters = (
            encounter_list[-5:]
        )

        # ---------------------------------
        # FINAL STRUCTURED SUMMARY
        # ---------------------------------

        summary = {
            "patient": patient_info,
            "conditions": condition_list,
            "active_medications":
                active_medications,
            "latest_health_data":
                latest_health_data,
            "recent_encounters":
                recent_encounters
        }

        # Create output folder
        OUTPUT_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )

        # Save JSON
        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as output_file:

            json.dump(
                summary,
                output_file,
                indent=4,
                ensure_ascii=False
            )

        print()
        print("=" * 70)
        print("STRUCTURED PATIENT SUMMARY CREATED")
        print("=" * 70)

        print()
        print(f"Patient: {full_name}")

        print(
            f"Conditions: "
            f"{len(condition_list)}"
        )

        print(
            f"Active medications: "
            f"{len(active_medications)}"
        )

        print(
            f"Latest health measurements: "
            f"{len(latest_health_data)}"
        )

        print(
            f"Recent encounters: "
            f"{len(recent_encounters)}"
        )

        print()
        print(
            f"Saved to: {OUTPUT_FILE}"
        )

        print("=" * 70)

        return


if __name__ == "__main__":
    create_patient_summary()