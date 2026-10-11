import json
import os
import math
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

EMBEDDINGS_FILE = (
    PROJECT_ROOT
    / "data"
    / "rag"
    / "embedded_documents.json"
)


# Load API key
load_dotenv(ENV_FILE)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        f"OPENAI_API_KEY was not found in: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)


# Load embedded clinical documents
def load_documents():

    with open(
        EMBEDDINGS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# Cosine similarity
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


# Convert question into an embedding
def embed_query(question):

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    )

    return response.data[0].embedding


# Search for relevant clinical records
def semantic_search(
    question,
    documents,
    top_k=5
):

    query_embedding = embed_query(question)

    results = []

    for document in documents:

        score = cosine_similarity(
            query_embedding,
            document["embedding"]
        )

        results.append({
            "score": score,
            "text": document["text"],
            "metadata": document["metadata"]
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:top_k]


def main():

    print("Loading embedded documents...")

    documents = load_documents()

    print(
        f"Loaded {len(documents)} documents."
    )

    print()

    question = input(
        "Ask a clinical question: "
    )

    print()
    print("Searching...")
    print()

    results = semantic_search(
        question,
        documents
    )

    print("=" * 70)
    print("TOP RELEVANT CLINICAL RECORDS")
    print("=" * 70)

    for index, result in enumerate(
        results,
        start=1
    ):

        print()
        print(f"RESULT {index}")
        print(
            f"Similarity: "
            f"{result['score']:.4f}"
        )

        print(
            f"Text: {result['text']}"
        )

        metadata = result["metadata"]

        print(
            f"Resource Type: "
            f"{metadata.get('resource_type')}"
        )

        print(
            f"Resource ID: "
            f"{metadata.get('resource_id')}"
        )

        print(
            f"Date: "
            f"{metadata.get('date')}"
        )

        print("-" * 70)


if __name__ == "__main__":
    main()