import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "rag"
    / "clinical_documents.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "rag"
    / "embedded_documents.json"
)


# --------------------------------------------------
# Load API key
# --------------------------------------------------

load_dotenv(ENV_FILE)

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        f"OPENAI_API_KEY was not found in: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)


# --------------------------------------------------
# Load clinical documents
# --------------------------------------------------

def load_documents():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# --------------------------------------------------
# Create embeddings
# --------------------------------------------------

def create_embeddings(documents):

    embedded_documents = []

    total = len(documents)

    print(f"Documents to embed: {total}")
    print()

    for index, document in enumerate(documents, start=1):

        text = document["text"]

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )

        embedding = response.data[0].embedding

        embedded_document = {
            "text": text,
            "metadata": document["metadata"],
            "embedding": embedding
        }

        embedded_documents.append(
            embedded_document
        )

        print(
            f"Embedded {index}/{total}"
        )

    return embedded_documents


# --------------------------------------------------
# Save embeddings
# --------------------------------------------------

def save_embeddings(embedded_documents):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            embedded_documents,
            file,
            indent=2,
            ensure_ascii=False
        )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("Loading clinical documents...")

    documents = load_documents()

    print(
        f"Loaded {len(documents)} clinical documents."
    )

    print()
    print("Creating embeddings...")
    print()

    embedded_documents = create_embeddings(
        documents
    )

    save_embeddings(
        embedded_documents
    )

    print()
    print("=" * 60)
    print("EMBEDDING CREATION COMPLETE")
    print("=" * 60)

    print(
        f"Documents embedded: "
        f"{len(embedded_documents)}"
    )

    if embedded_documents:

        dimensions = len(
            embedded_documents[0]["embedding"]
        )

        print(
            f"Embedding dimensions: {dimensions}"
        )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()