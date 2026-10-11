import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Explicitly load .env from project root
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# Check whether key was loaded
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError(
        f"OPENAI_API_KEY was not found. Expected .env file at: {ENV_FILE}"
    )

client = OpenAI(api_key=api_key)

DOCUMENT_FILE = PROJECT_ROOT / "data" / "rag" / "clinical_documents.json"

with open(DOCUMENT_FILE, "r", encoding="utf-8") as f:
    documents = json.load(f)

first_document = documents[0]

print("Clinical document:")
print(first_document["text"])

response = client.embeddings.create(
    model="text-embedding-3-small",
    input=first_document["text"]
)

embedding = response.data[0].embedding

print("\nEmbedding created successfully!")
print("Embedding dimensions:", len(embedding))
print("First 10 numbers:")
print(embedding[:10])