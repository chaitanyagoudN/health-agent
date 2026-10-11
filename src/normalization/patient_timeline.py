import json
from pathlib import Path
from datetime import datetime


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

    # Normal numeric values
    if "valueQuantity" in observation:
        quantity = observation["valueQuantity"]

        value = quantity.get("value", "")
        unit = quantity.get("unit", "")

        return f"{value} {unit}".strip()

    # Coded values
    if "valueCodeableConcept" in observation:
        concept = observation["valueCodeableConcept"]

        if concept.get("text"):
            return concept["text"]

        coding = concept.get("coding", [])

        if coding:
            return coding[0].get(
                "display",
                "Unknown"
            )

    # Text values
    if "valueString" in observation:
        return observation["valueString"]

    # Component values such as blood pressure
    components = observation.get(
        "component",
        []
    )

    if components:

        component_results = []

        for component in components:

            component_name = get_code_name(
                component
            )

            quantity = component.get(
                "valueQuantity",
                {}
            )

            value = quantity.get(
                "value",
                ""
            )

            unit = quantity.get(
                "unit",
                ""
            )

            if value != "":

                component_results.append(
                    f"{component_name}: "
                    f"{value} {unit}"
                )

        if component_results:
            return " | ".join(
                component_results
            )

    return "No value available"


def get_encounter_type(encounter):

    encounter_types = encounter.get(
        "type",
        []
    )

    if encounter_types:

        encounter_type = encounter_types[0]

        if encounter_type.get("text"):
            return encounter_type["text"]

        coding = encounter_type.get(
            "coding",
            []
        )

        if coding:
            return coding[0].get(
                "display",
                "Unknown encounter"
            )

    encounter_class = encounter.get(
        "class",
        {}
    )

    if encounter_class.get("display"):
        return encounter_class["display"]

    return "Unknown encounter"


def parse_date(date_string):

    if not date_string:
        return datetime.min

    try:
        return datetime.fromisoformat(
            date_string
        )

    except ValueError:
        return datetime.min


def build_timeline():

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

        entries = data.get(
            "entry",
            []
        )

        patient = None
        timeline = []

        for entry in entries:

            resource = entry.get(
                "resource",
                {}
            )

            resource_type = resource.get(
                "resourceType"
            )

            # =================================
            # PATIENT
            # =================================

            if resource_type == "Patient":

                patient = resource

            # =================================
            # CONDITIONS
            # =================================

            elif resource_type == "Condition":

                condition_name = get_code_name(
                    resource
                )

                date = resource.get(
                    "onsetDateTime"
                )

                if date:

                    timeline.append({
                        "date": date,
                        "type": "Condition",
                        "description": condition_name
                    })

            # =================================
            # MEDICATIONS
            # =================================

            elif resource_type == "MedicationRequest":

                medication_name = (
                    get_medication_name(
                        resource
                    )
                )

                date = resource.get(
                    "authoredOn"
                )

                status = resource.get(
                    "status",
                    "Unknown"
                )

                if date:

                    timeline.append({
                        "date": date,
                        "type": "Medication",
                        "description":
                            f"{medication_name} "
                            f"({status})"
                    })

            # =================================
            # OBSERVATIONS / LABS
            # =================================

            elif resource_type == "Observation":

                observation_name = (
                    get_code_name(
                        resource
                    )
                )

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
                    "blood pressure",
                    "smoking status"
                ]

                name_lower = (
                    observation_name.lower()
                )

                if any(
                    term in name_lower
                    for term in important_terms
                ):

                    date = resource.get(
                        "effectiveDateTime"
                    )

                    value = (
                        get_observation_value(
                            resource
                        )
                    )

                    if date:

                        timeline.append({
                            "date": date,
                            "type": "Observation",
                            "description":
                                f"{observation_name}: "
                                f"{value}"
                        })

            # =================================
            # ENCOUNTERS
            # =================================

            elif resource_type == "Encounter":

                encounter_name = (
                    get_encounter_type(
                        resource
                    )
                )

                period = resource.get(
                    "period",
                    {}
                )

                date = period.get(
                    "start"
                )

                if date:

                    timeline.append({
                        "date": date,
                        "type": "Encounter",
                        "description":
                            encounter_name
                    })

        # =====================================
        # PRINT TIMELINE
        # =====================================

        if patient:

            names = patient.get(
                "name",
                []
            )

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
                    given_names +
                    [family_name]
                )

            else:
                full_name = "Unknown"

            timeline.sort(
                key=lambda event:
                    parse_date(
                        event["date"]
                    )
            )

            print("=" * 70)
            print("PATIENT CLINICAL TIMELINE")
            print("=" * 70)

            print(
                f"Patient: {full_name}"
            )

            print(
                f"Patient ID: "
                f"{patient.get('id', 'Unknown')}"
            )

            print(
                f"Total timeline events: "
                f"{len(timeline)}"
            )

            print()

            # Show latest 40 events
            latest_events = timeline[-40:]

            for event in latest_events:

                date = event["date"][:10]

                print(
                    f"{date} | "
                    f"{event['type']} | "
                    f"{event['description']}"
                )

            print()
            print("=" * 70)

            return


if __name__ == "__main__":
    build_timeline()