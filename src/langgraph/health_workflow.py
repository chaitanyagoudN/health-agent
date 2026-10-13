# import sys
# from pathlib import Path

# # Allow importing modules from src/rag
# RAG_FOLDER = Path(__file__).resolve().parents[1] / "RAG"
# sys.path.insert(0, str(RAG_FOLDER))

# from src.RAG.rag_answer import (
#     load_documents,
#     retrieve_documents,
#     generate_answer,
#     generate_json_summary
# )
# from typing import TypedDict
# from langgraph.graph import StateGraph, START, END


# # Shared information passed between nodes
# class HealthState(TypedDict):
#     patient_id: str
#     question: str
#     records: list
#     summary: str
#     json_summary: dict
#     validation: str
# # Node 1: Retrieve records
# def retrieve_records(state: HealthState):
#     print("Step 1: Retrieving real FHIR records")

#     documents = load_documents()

#     retrieved = retrieve_documents(
#         question=state["question"],
#         documents=documents,
#         patient_id=state["patient_id"],
#         top_k=5
#     )

#     print(f"Retrieved {len(retrieved)} clinical documents")

#     return {
#         "records": retrieved
#     }

# # Node 2: Generate summary

# def generate_summary(state: HealthState):
#     print("Step 2: Generating AI summary using OpenAI")

#     records = state["records"]

#     if not records:
#         return {
#             "summary": "No clinical records were retrieved."
#         }

#     answer = generate_answer(
#         question=state["question"],
#         retrieved_documents=records
#     )

#     print("AI summary generated successfully.")

#     return {
#         "summary": answer
#     }

# def generate_structured_summary(state: HealthState):
#     print("Step 3: Generating structured JSON summary")

#     records = state["records"]

#     if not records:
#         return {
#             "json_summary": {}
#         }

#     result = generate_json_summary(
#         question=state["question"],
#         retrieved_documents=records
#     )

#     result["patient_id"] = state["patient_id"]

#     print("Structured JSON summary generated.")

#     return {
#         "json_summary": result
#     }



# # Node 3: Validate summary

# def validate_summary(state: HealthState):
#     print("Step 3: Checking AI summary citations")

#     import re

#     records = state["records"]
#     summary = state["summary"]

#     # Build a set of citations from retrieved FHIR records
#     valid_citations = set()

#     for document in records:
#         metadata = document["metadata"]

#         citation = (
#             f'[{metadata.get("source", "FHIR")} '
#             f'{metadata["resource_type"]}: '
#             f'{metadata["resource_id"]}]'
#         )

#         valid_citations.add(citation)

#     # Extract citations from AI-generated summary
#     used_citations = re.findall(
#         r"\[FHIR (?:Condition|MedicationRequest|Observation): [^\[\]]+\]",
#         summary
#     )

#     invalid_citations = [
#         citation
#         for citation in used_citations
#         if citation not in valid_citations
#     ]

#     if invalid_citations:
#         result = "FAILED: Invalid FHIR citations found"
#         print(result)
#         print("Invalid citations:", invalid_citations)

#     elif not used_citations:
#         result = "FAILED: No FHIR citations found"
#         print(result)

#     else:
#         result = f"PASSED: {len(used_citations)} citations verified"
#         print(result)

#     return {
#         "validation": result
#     }



# # Create workflow
# workflow = StateGraph(HealthState)

# # Add nodes
# workflow.add_node("retrieve", retrieve_records)
# workflow.add_node("summarize", generate_summary)
# workflow.add_node("validate", validate_summary)
# workflow.add_node(
#     "structured_summary",
#     generate_structured_summary
# )
# # Connect nodes
# workflow.add_edge(START, "retrieve")
# workflow.add_edge("retrieve", "summarize")
# workflow.add_edge("summarize", "structured_summary")
# workflow.add_edge("structured_summary", "validate")
# workflow.add_edge("validate", END)
# # Compile workflow
# app = workflow.compile()


# if __name__ == "__main__":

#     result = app.invoke({
#         "patient_id": "73c1537e-544a-dc37-2f2c-55f53a1496cd",
#         "question": "Summarize this patient's medical history, medications, and laboratory results.",
#         "records": [],
#         "summary": "",
#         "json_summary": {},
#         "validation": ""
#     })

#     print("\nFINAL RESULT")
#     print(result)
"""Health chart RAG workflow: retrieve, summarize, validate, then save."""
import json
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from src.RAG.rag_answer import (
    load_documents, retrieve_documents, generate_answer, generate_json_summary
)
from src.RAG.validate_summary import validate_chart_summary

OUTPUT = Path("data/normalized/patient_chart_summary.json")


class HealthState(TypedDict):
    patient_id: str
    question: str
    records: list
    summary: str
    json_summary: dict
    validation: str
    validation_errors: list


def retrieve_records(state: HealthState):
    print("Step 1: Retrieving real FHIR records")
    records = retrieve_documents(
        question=state["question"],
        documents=load_documents(),
        patient_id=state["patient_id"],
        top_k=5,
    )
    print(f"Retrieved {len(records)} clinical documents")
    return {"records": records}


def generate_summary(state: HealthState):
    print("Step 2: Generating text summary")
    if not state["records"]:
        return {"summary": "No clinical records were retrieved."}
    return {"summary": generate_answer(state["question"], state["records"])}


def generate_structured_summary(state: HealthState):
    print("Step 3: Generating JSON summary")
    if not state["records"]:
        return {"json_summary": {}}
    summary = generate_json_summary(state["question"], state["records"])
    summary["patient_id"] = state["patient_id"]
    return {"json_summary": summary}


def validate_summary(state: HealthState):
    
    print("Step 4: Validating JSON against retrieved FHIR documents")
    errors, verified = validate_chart_summary(state["json_summary"], state["records"])
    
    result = f"FAILED: {len(errors)} errors" if errors else f"PASSED: {verified} citations and values verified"
    print(result)
    if errors:
        print("\nVALIDATION ERROR DETAILS:")
        

    for index, error in enumerate(errors, start=1):
        print(f"{index}. {error}")
    # for error in errors:
    #     print(" -", error)
    return {"validation": result, "validation_errors": errors}


def route_after_validation(state: HealthState):
    return "reject" if state["validation_errors"] else "save"


def save_summary(state: HealthState):
    print("Step 5: Saving validated JSON")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(state["json_summary"], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {OUTPUT}")
    return {}


def reject_summary(state: HealthState):
    print("JSON NOT SAVED because validation failed")
    return {}


workflow = StateGraph(HealthState)
workflow.add_node("retrieve", retrieve_records)
workflow.add_node("summarize", generate_summary)
workflow.add_node("structured_summary", generate_structured_summary)
workflow.add_node("validate", validate_summary)
workflow.add_node("save", save_summary)
workflow.add_node("reject", reject_summary)
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "summarize")
workflow.add_edge("summarize", "structured_summary")
workflow.add_edge("structured_summary", "validate")
workflow.add_conditional_edges("validate", route_after_validation, {"save": "save", "reject": "reject"})
workflow.add_edge("save", END)
workflow.add_edge("reject", END)
app = workflow.compile()


if __name__ == "__main__":
    result = app.invoke({
        
        "patient_id": "73c1537e-544a-dc37-2f2c-55f53a1496cd",
        "question": "Summarize this patient's medical history, medications, and laboratory results.",
        "records": [], "summary": "", "json_summary": {},
        "validation": "", "validation_errors": [],
    })
    
    history = result.get("json_summary", {}).get("medical_history", [])

    if history:
        first_condition = history[0]

        print("\nGENERATED CONDITION:")
        print(first_condition)

        for citation in first_condition.get("citations", []):
            for document in result.get("records", []):
                metadata = document["metadata"]

                source_citation = (
                    f'[FHIR {metadata["resource_type"]}: '
                    f'{metadata["resource_id"]}]'
                )

                if citation == source_citation:
                    print("\nMATCHING SOURCE CONDITION:")
                    print(document["text"])
                    break

    # Debug the first laboratory result
    labs = result.get("json_summary", {}).get("laboratory_results", [])

    if labs:
        first_lab = labs[0]

        print("\nFIRST GENERATED LAB RESULT:")
        print(first_lab)

        citations = first_lab.get("citations", [])

        if citations:
            citation = citations[0]

            for document in result.get("records", []):
                metadata = document["metadata"]

                source_citation = (
                    f'[FHIR {metadata["resource_type"]}: '
                    f'{metadata["resource_id"]}]'
                )

                if source_citation == citation:
                    print("\nMATCHING SOURCE DOCUMENT:")
                    print(document["text"])

                    print("\nSOURCE DATE:")
                    print(metadata.get("date"))
                    break

    print("\nFINAL VALIDATION:", result["validation"])
    print("\nTEXT SUMMARY:\n", result["summary"])
