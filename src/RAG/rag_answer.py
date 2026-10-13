import json
import os
import math
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / '.env'
EMBEDDINGS_FILE = PROJECT_ROOT / 'data' / 'rag' / 'embedded_documents.json'

load_dotenv(ENV_FILE)
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError(f'OPENAI_API_KEY was not found in: {ENV_FILE}')
client = OpenAI(api_key=api_key)


def load_documents():
    with open(EMBEDDINGS_FILE, 'r', encoding='utf-8') as file:
        return json.load(file)


def cosine_similarity(vector_a, vector_b):
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    magnitude_a = math.sqrt(sum(a * a for a in vector_a))
    magnitude_b = math.sqrt(sum(b * b for b in vector_b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


def embed_query(question):
    response = client.embeddings.create(
        model='text-embedding-3-small',
        input=question
    )
    return response.data[0].embedding


def get_patient_ids(documents):
    return sorted({
        document['metadata']['patient_id']
        for document in documents
        if document.get('metadata', {}).get('patient_id')
    })


def is_medication_inventory_question(question):
    question = question.lower()
    medication_terms = ('medication', 'medications', 'medicine', 'medicines', 'prescriptions', 'drugs')
    inventory_terms = ('what', 'which', 'all', 'list', 'documented', 'history', 'taking', 'prescribed')
    return (any(term in question for term in medication_terms)
            and any(term in question for term in inventory_terms)
            and not any(term in question for term in ('side effect', 'interaction', 'why ', 'dose change')))


def is_condition_inventory_question(question):
    question = question.lower()
    condition_terms = ('condition', 'conditions', 'diagnos', 'medical history', 'health problems')
    inventory_terms = ('what', 'which', 'all', 'list', 'documented', 'history', 'have', 'has')
    return (any(term in question for term in condition_terms)
            and any(term in question for term in inventory_terms))


def is_full_chart_question(question):
    q = question.lower()
    broad = any(term in q for term in (
        'summarize', 'summary', 'overview', 'complete chart', 'full chart',
        'medical history, medications', 'patient chart'
    ))
    sections = sum(any(term in q for term in group) for group in (
        ('history', 'condition', 'diagnos'),
        ('medication', 'medicine', 'prescription'),
        ('lab', 'observation', 'result', 'glucose', 'a1c')
    ))
    return broad and (sections >= 2 or 'chart' in q)


def retrieve_full_chart(patient_documents):
    # Include all condition and medication evidence. Keep a manageable,
    # chronological sample of clinically useful observations for trend analysis.
    conditions = [d for d in patient_documents
                  if d['metadata'].get('resource_type') == 'Condition']
    medications = [d for d in patient_documents
                   if d['metadata'].get('resource_type') == 'MedicationRequest']
    observations = [d for d in patient_documents
                    if d['metadata'].get('resource_type') == 'Observation']

    # Keep up to three dated values per relevant observation name: earliest,
    # middle, and latest. This is a sample, not the full lab history.
    keywords = ('a1c', 'hemoglobin a1c', 'glucose', 'blood pressure',
                'systolic', 'diastolic', 'bmi', 'body mass index',
                'weight', 'cholesterol', 'hdl', 'ldl', 'triglyceride',
                'creatinine')
    groups = {}
    for d in observations:
        label = d['text'].split('. Value:')[0].casefold()
        if any(k in label for k in keywords):
            groups.setdefault(label, []).append(d)

    selected_observations = []
    for group in groups.values():
        group.sort(key=lambda d: d['metadata'].get('date') or '')
        indices = sorted({0, len(group) // 2, len(group) - 1})
        selected_observations.extend(group[i] for i in indices)

    combined = conditions + medications + selected_observations
    print(f'Full chart: {len(conditions)} conditions, '
          f'{len(medications)} medication orders, '
          f'{len(selected_observations)} selected observations '
          f'(from {len(observations)} total observations).')
    return [{'score': None, 'text': d['text'], 'metadata': d['metadata']}
            for d in combined]


def retrieve_documents(question, documents, patient_id, top_k=5):
    patient_documents = [
        document for document in documents
        if document.get('metadata', {}).get('patient_id') == patient_id
    ]
    if not patient_documents:
        raise ValueError(f'No clinical documents found for patient: {patient_id}')

    # Check broad chart requests FIRST, before medication/condition keywords.
    if is_full_chart_question(question):
        return retrieve_full_chart(patient_documents)

    # Inventory questions need comprehensive coverage, not just the five nearest vectors.
    if is_medication_inventory_question(question):
        medication_documents = [
            document for document in patient_documents
            if document['metadata'].get('resource_type') == 'MedicationRequest'
        ]
        if not medication_documents:
            return []
        medication_documents.sort(key=lambda doc: doc['metadata'].get('date') or '')
        print(f'Retrieving all {len(medication_documents)} medication orders for patient {patient_id}')
        return [
            {'score': None, 'text': document['text'], 'metadata': document['metadata']}
            for document in medication_documents
        ]

    # For broad condition questions, include all Condition resources so that
    # repeated care-related entries do not crowd out other conditions.
    if is_condition_inventory_question(question):
        condition_documents = [
            document for document in patient_documents
            if document['metadata'].get('resource_type') == 'Condition'
        ]
        condition_documents.sort(key=lambda doc: (
            doc['text'].split('. Onset date:')[0].casefold(),
            doc['metadata'].get('date') or ''
        ))
        print(f'Retrieving all {len(condition_documents)} condition records for patient {patient_id}')
        return [
            {'score': None, 'text': document['text'], 'metadata': document['metadata']}
            for document in condition_documents
        ]

    # Retain the existing resource filter for other medication questions.
    if 'medication' in question.lower():
        patient_documents = [
            document for document in patient_documents
            if document['metadata'].get('resource_type') == 'MedicationRequest'
        ]
    if not patient_documents:
        return []

    print(f'Searching {len(patient_documents)} records for patient {patient_id}')
    query_embedding = embed_query(question)
    results = []
    for document in patient_documents:
        score = cosine_similarity(query_embedding, document['embedding'])
        results.append({
            'score': score,
            'text': document['text'],
            'metadata': document['metadata']
        })
    results.sort(key=lambda item: item['score'], reverse=True)
    return results[:top_k]


def generate_answer(question, retrieved_documents):
    if not retrieved_documents:
        return 'No matching clinical records were found for this patient.'

    context_parts = []
    for index, document in enumerate(retrieved_documents, start=1):
        metadata = document['metadata']
        source = metadata.get('source', 'Unknown')
        resource_type = metadata.get('resource_type', 'Unknown')
        resource_id = metadata.get('resource_id', 'Unknown')
        citation = f'[{source} {resource_type}: {resource_id}]'
        context_parts.append(
            f'SOURCE {index}\n'
            f'Text: {document["text"]}\n'
            f'Date: {metadata.get("date", "Unknown")}\n'
            f'Citation: {citation}'
        )
    context = '\n\n'.join(context_parts)

    instructions = '''You are a health-chart question-answering assistant.
The supplied records are synthetic clinical data used for a software project.
Answer ONLY from supplied records. Do not invent clinical information, diagnose,
or recommend treatments. Preserve dates, values, units, and status.
Every factual clinical statement must cite the exact supplied citation.
Do not alter or invent citation IDs. If information is missing, say so.
For medication inventory questions, identify distinct medication names and
separate active orders from completed orders. A completed order is historical,
not evidence of current use. Do not assume an active order proves adherence.
Avoid repeating identical medication names unnecessarily; summarize their
order history and cite relevant records.
For condition inventory questions, group repeated condition names and distinguish
recorded disorders, clinical findings, and social/care-related situations.
A Condition resource is not proof that the condition is currently active,
confirmed, or ongoing. The available documents do not include clinicalStatus
or verificationStatus, so do not claim a condition is active or confirmed.
Do not treat care-related situations (such as medication review due) as diagnoses.
Cite the exact relevant FHIR Condition records.
For complete chart summaries, organize the answer into medical history,
medication orders, and laboratory/measurement trends. Distinguish observed
values from diagnoses, and never claim that selected observations are a
complete laboratory history. Do not imply an order proves medication use.
Keep the answer clear and concise.'''

    response = client.responses.create(
        model='gpt-6-luna',  # Kept from your existing script; change only if your API rejects this model.
        instructions=instructions,
        input=f'CLINICAL RECORDS:\n{context}\n\nQUESTION:\n{question}\n\nUse exact citations.'
    )
    return response.output_text

# --------------------------------------------------
# Generate structured JSON patient summary
# --------------------------------------------------

def generate_json_summary(question, retrieved_documents):
    

    if not retrieved_documents:
        return {
            "medical_history": [],
            "medications": [],
            "laboratory_results": []
        }

    context_parts = []

    for document in retrieved_documents:

        metadata = document["metadata"]

        citation = (
            f'[{metadata.get("source", "FHIR")} '
            f'{metadata.get("resource_type", "Unknown")}: '
            f'{metadata.get("resource_id", "Unknown")}]'
        )

        context_parts.append({
            "text": document["text"],
            "date": metadata.get("date"),
            "resource_type": metadata.get("resource_type"),
            "citation": citation
        })

    instructions = """
You are a structured clinical data extraction assistant.

The records are synthetic FHIR patient records.

Return a JSON object with exactly these three arrays:
medical_history, medications, laboratory_results.

Each medical_history item must contain:
condition, status, citations.

Each medications item must contain:
name, order_status, citations.

Each laboratory_results item must contain:
test, value, unit, date, citations.

Use only supplied records.
Do not invent medical information.
Do not infer diagnoses or treatment.
Preserve the exact FHIR citations.
Do not assume medication orders prove actual use.
Do not assume historical conditions are currently active.
Use "unknown" for unavailable condition status.
Include only observations supplied in the context.
Return valid JSON only.


IMPORTANT RULES FOR MEDICAL HISTORY:

1. Copy each condition name EXACTLY as it appears in the source FHIR document.

2. Do not remove words, parentheses, or qualifiers.

3. For example:
   Source: Condition: Medication review due (situation).
   JSON: "condition": "Medication review due (situation)"

4. If multiple FHIR records have the exact same condition name,
   they may be grouped into one JSON item with multiple citations.

5. If condition status is not available in the source,
   use "status": "unknown".

6. Do not invent or change condition names.

"""

    response = client.responses.create(
        model="gpt-6-luna",
        instructions=instructions,
        input=(
            "CLINICAL RECORDS:\n"
            + json.dumps(context_parts, indent=2)
            + "\n\nQUESTION:\n"
            + question
        )
    )

    return json.loads(response.output_text)


def main():
    print('\n' + '=' * 70)
    print('HEALTH CHART RAG')
    print('=' * 70)
    print('\nLoading embedded clinical documents...')
    documents = load_documents()
    print(f'Loaded {len(documents)} documents.')

    patient_ids = get_patient_ids(documents)
    print(f'\nFound {len(patient_ids)} patient(s).')
    if not patient_ids:
        print('No patient IDs were found in the document metadata.')
        return

    print('\nAvailable Patient IDs:')
    print('-' * 70)
    for index, patient_id in enumerate(patient_ids, start=1):
        print(f'{index}. {patient_id}')

    patient_id = input('\nEnter patient ID: ').strip()
    if patient_id not in patient_ids:
        print('ERROR: Patient ID was not found. Please select an ID shown above.')
        return

    question = input('\nAsk a clinical question: ').strip()
    if not question:
        print('ERROR: Question cannot be empty.')
        return

    print('\nRetrieving relevant clinical records...')
    retrieved_documents = retrieve_documents(question, documents, patient_id, top_k=5)
    if not retrieved_documents:
        print('No matching clinical records were found for this patient.')
        return

    print('\nGenerating grounded RAG answer...\n')
    answer = generate_answer(question, retrieved_documents)
    
    # Generate and save structured JSON for full-chart questions
    if is_full_chart_question(question):
        print('\nGenerating structured JSON patient summary...')

        try:
            summary = generate_json_summary(question, retrieved_documents)

            # Include the selected patient ID
            summary["patient_id"] = patient_id

            # Create output directory if needed
            output_dir = Path("data/normalized")
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / "patient_chart_summary.json"

            with open(output_file, "w", encoding="utf-8") as file:
                json.dump(summary, file, indent=4, ensure_ascii=False)

            print(f'\nJSON summary saved to: {output_file}')

        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as error:
            print(f'\nCould not save JSON summary: {error}')
            print('Continuing with the regular RAG answer.')

    print('=' * 70)
    print('RAG ANSWER')
    print('=' * 70)
    print('\n' + answer)

    print('\n' + '=' * 70)
    print('RETRIEVED FHIR SOURCES')
    print('=' * 70)
    for index, document in enumerate(retrieved_documents, start=1):
        metadata = document['metadata']
        source = metadata.get('source', 'Unknown')
        resource_type = metadata.get('resource_type', 'Unknown')
        resource_id = metadata.get('resource_id', 'Unknown')
        print(f'\nSource {index}')
        print(f'Text: {document["text"]}')
        print(f'Source System: {source}')
        print(f'Resource Type: {resource_type}')
        print(f'Resource ID: {resource_id}')
        print(f'Date: {metadata.get("date", "Unknown")}')
        if document['score'] is None:
            print('Retrieval: Selected chart evidence (no similarity ranking)')
        else:
            print(f'Similarity: {document["score"]:.4f}')
        print(f'FHIR Citation: [{source} {resource_type}: {resource_id}]')
        print('-' * 70)


if __name__ == '__main__':
    main()
