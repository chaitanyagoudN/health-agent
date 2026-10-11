import json
import os
import math
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

EMBEDDINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "rag"
    / "embedded_documents.json"
)


# --------------------------------------------------
# OpenAI setup
# --------------------------------------------------

load_dotenv(ENV_FILE)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        f"OPENAI_API_KEY was not found in: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)


# --------------------------------------------------
# Load embedded documents
# --------------------------------------------------

def load_documents():

    with open(
        EMBEDDINGS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# --------------------------------------------------
# Cosine similarity
# --------------------------------------------------

def cosine_similarity(vector_a, vector_b):

    dot_product = sum(
        a * b
        for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(a * a for a in vector_a)
    )

    magnitude_b = math.sqrt(
        sum(b * b for b in vector_b)
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0

    return dot_product / (
        magnitude_a * magnitude_b
    )


# --------------------------------------------------
# Create embedding for user's question
# --------------------------------------------------

def embed_query(question):

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    )

    return response.data[0].embedding


# --------------------------------------------------
# Get patient IDs
# --------------------------------------------------

def get_patient_ids(documents):

    patient_ids = sorted({
        document["metadata"].get("patient_id")
        for document in documents
        if document["metadata"].get("patient_id")
    })

    return patient_ids


# --------------------------------------------------
# Retrieve relevant records for ONE patient
# --------------------------------------------------

def retrieve_documents(
    question,
    documents,
    patient_id,
    top_k=5
):

    # Filter documents BEFORE semantic search
    patient_documents = [
        document
        for document in documents
        if document["metadata"].get("patient_id") == patient_id
    ]

# Filter medication questions to MedicationRequest resources
    if "medication" in question.lower():
     patient_documents = [
        document
        for document in patient_documents
        if document["metadata"].get("resource_type") == "MedicationRequest"
    ]
    if not patient_documents:
        raise ValueError(
            f"No clinical documents found for patient: {patient_id}"
        )

    print(
        f"Searching {len(patient_documents)} records "
        f"for patient {patient_id}"
    )

    # Create embedding for the user's question
    query_embedding = embed_query(question)

    results = []

    # Compare question against this patient's records only
    for document in patient_documents:

        score = cosine_similarity(
            query_embedding,
            document["embedding"]
        )

        results.append({
            "score": score,
            "text": document["text"],
            "metadata": document["metadata"]
        })

    # Highest similarity first
    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:top_k]


# --------------------------------------------------
# Generate grounded RAG answer
# --------------------------------------------------

def generate_answer(
    question,
    retrieved_documents
):

    context_parts = []

    for index, document in enumerate(
        retrieved_documents,
        start=1
    ):

        metadata = document["metadata"]

        source = metadata.get(
            "source",
            "Unknown"
        )

        resource_type = metadata.get(
            "resource_type",
            "Unknown"
        )

        resource_id = metadata.get(
            "resource_id",
            "Unknown"
        )

        date = metadata.get(
            "date",
            "Unknown"
        )

        citation = (
            f"[{source} {resource_type}: "
            f"{resource_id}]"
        )

        context_parts.append(
            f"""
SOURCE {index}

Text:
{document['text']}

Source System:
{source}

Resource Type:
{resource_type}

Resource ID:
{resource_id}

Date:
{date}

Citation:
{citation}
"""
        )

    context = "\n".join(
        context_parts
    )


    # --------------------------------------------------
    # Instructions for the LLM
    # --------------------------------------------------

    instructions = """
You are a health-chart question-answering assistant.

The supplied records are synthetic clinical data used for a software project.

Rules:

1. Answer ONLY from the supplied clinical records.

2. Do not invent medical information.

3. Do not diagnose new conditions.

4. Do not provide treatment recommendations.

5. Preserve important dates, values, and units.

6. Clearly distinguish documented information from information
   that is not available.

7. Every factual clinical statement should cite the supporting
   clinical record.

8. Use the exact Citation provided with each source.

9. Do not create, modify, shorten, or invent citation IDs.

10. If multiple records support the answer, cite the relevant
    records individually.

11. If the retrieved records do not contain enough information
    to answer the question, clearly say so.

12. Keep the answer concise and clinically clear.
"""


    # --------------------------------------------------
    # Prompt
    # --------------------------------------------------

    prompt = f"""
CLINICAL RECORDS:

{context}


QUESTION:

{question}


Answer the question using ONLY the clinical records above.

Include the exact FHIR citations supplied with the records.
"""


    # --------------------------------------------------
    # Ask OpenAI
    # --------------------------------------------------

    response = client.responses.create(
        model="gpt-6-luna",
        instructions=instructions,
        input=prompt
    )

    return response.output_text


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print()
    print("=" * 70)
    print("HEALTH CHART RAG")
    print("=" * 70)

    print()
    print("Loading embedded clinical documents...")

    documents = load_documents()

    print(
        f"Loaded {len(documents)} documents."
    )


    # --------------------------------------------------
    # Find patients
    # --------------------------------------------------

    patient_ids = get_patient_ids(
        documents
    )

    print()
    print(
        f"Found {len(patient_ids)} patient(s)."
    )

    if not patient_ids:

        print(
            "No patient IDs were found "
            "in the document metadata."
        )

        return


    # --------------------------------------------------
    # Display available patients
    # --------------------------------------------------

    print()
    print("Available Patient IDs:")
    print("-" * 70)

    for index, patient_id in enumerate(
        patient_ids,
        start=1
    ):

        print(
            f"{index}. {patient_id}"
        )


    # --------------------------------------------------
    # Ask user to select patient
    # --------------------------------------------------

    print()

    patient_id = input(
        "Enter patient ID: "
    ).strip()


    # --------------------------------------------------
    # Validate patient
    # --------------------------------------------------

    if patient_id not in patient_ids:

        print()
        print(
            "ERROR: Patient ID was not found."
        )

        print(
            "Please use one of the Patient IDs "
            "shown above."
        )

        return


    # --------------------------------------------------
    # Ask clinical question
    # --------------------------------------------------

    print()

    question = input(
        "Ask a clinical question: "
    ).strip()

    if not question:

        print(
            "ERROR: Question cannot be empty."
        )

        return


    # --------------------------------------------------
    # Retrieval
    # --------------------------------------------------

    print()
    print(
        "Retrieving relevant clinical records..."
    )

    retrieved_documents = retrieve_documents(
        question,
        documents,
        patient_id,
        top_k=5
    )


    # --------------------------------------------------
    # Generate answer
    # --------------------------------------------------

    print()
    print(
        "Generating grounded RAG answer..."
    )

    print()

    answer = generate_answer(
        question,
        retrieved_documents
    )


    # --------------------------------------------------
    # Display RAG answer
    # --------------------------------------------------

    print("=" * 70)
    print("RAG ANSWER")
    print("=" * 70)

    print()

    print(answer)


    # --------------------------------------------------
    # Display retrieved evidence
    # --------------------------------------------------

    print()
    print("=" * 70)
    print("RETRIEVED FHIR SOURCES")
    print("=" * 70)


    for index, document in enumerate(
        retrieved_documents,
        start=1
    ):

        metadata = document["metadata"]

        source = metadata.get(
            "source",
            "Unknown"
        )

        resource_type = metadata.get(
            "resource_type",
            "Unknown"
        )

        resource_id = metadata.get(
            "resource_id",
            "Unknown"
        )

        date = metadata.get(
            "date",
            "Unknown"
        )

        print()
        print(
            f"Source {index}"
        )

        print(
            f"Text: {document['text']}"
        )

        print(
            f"Source System: {source}"
        )

        print(
            f"Resource Type: {resource_type}"
        )

        print(
            f"Resource ID: {resource_id}"
        )

        print(
            f"Date: {date}"
        )

        print(
            f"Similarity: "
            f"{document['score']:.4f}"
        )

        print(
            "FHIR Citation: "
            f"[{source} {resource_type}: "
            f"{resource_id}]"
        )

        print("-" * 70)


# --------------------------------------------------
# Run program
# --------------------------------------------------

if __name__ == "__main__":
    main()