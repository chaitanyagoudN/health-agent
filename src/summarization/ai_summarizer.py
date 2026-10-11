import json
from pathlib import Path
from openai import OpenAI


INPUT_FILE = Path("data/normalized/patient_summary.json")
OUTPUT_FILE = Path("data/normalized/ai_summary.txt")


def load_patient_data():
    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def create_ai_summary(patient_data):
    from dotenv import load_dotenv

    load_dotenv()

    client = OpenAI()
    instructions = """
You are a health-chart summarization assistant.

The data provided is SYNTHETIC patient data generated for a software project.

Rules:
1. Use ONLY information contained in the provided JSON.
2. Do not invent diagnoses, medications, laboratory values, or encounters.
3. Clearly distinguish documented conditions from current medications.
4. Do not assume that every historical condition is currently active.
5. Preserve important numeric values and units.
6. Mention the dates of important recent measurements when useful.
7. Do not provide treatment recommendations.
8. Do not diagnose new medical conditions.
9. If information is unavailable, do not guess.
10. Produce a concise, easy-to-read health chart summary.

Use these sections:

PATIENT OVERVIEW
DOCUMENTED CONDITIONS
ACTIVE MEDICATIONS
RECENT VITALS AND LABS
RECENT ENCOUNTERS
CLINICAL SUMMARY
"""

    patient_json = json.dumps(
        patient_data,
        indent=2,
    )

    response = client.responses.create(
        model="gpt-6-luna",
        instructions=instructions,
        input=(
            "Summarize the following synthetic patient chart.\n\n"
            + patient_json
        ),
    )

    return response.output_text


def main():

    print("Loading structured patient data...")

    patient_data = load_patient_data()

    print("Sending structured data to AI...")

    summary = create_ai_summary(patient_data)

    print()
    print("=" * 70)
    print("AI HEALTH CHART SUMMARY")
    print("=" * 70)
    print()
    print(summary)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(summary)

    print()
    print("=" * 70)
    print(f"AI summary saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()