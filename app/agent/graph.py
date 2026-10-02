from langgraph.graph import END, START, StateGraph

from app.analyzers.rules import route_for_review
from app.core.policy import review_policy
from app.core.state import HermesState
from app.schemas.evidence import Evidence


def validate_node(state: HermesState) -> dict:
    evidence = [
        Evidence.model_validate(item).model_dump(mode="json")
        for item in state["evidence"]
    ]
    return {"evidence": evidence, "errors": []}


def triage_node(state: HermesState) -> dict:
    findings = []
    for item in state["evidence"]:
        finding = route_for_review(Evidence.model_validate(item))
        if finding:
            findings.append(finding.model_dump(mode="json"))
    return {"findings": findings}


def policy_node(state: HermesState) -> dict:
    return review_policy(state.get("findings", []))


def build_graph():
    graph = StateGraph(HermesState)
    graph.add_node("validate", validate_node)
    graph.add_node("triage", triage_node)
    graph.add_node("policy", policy_node)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "triage")
    graph.add_edge("triage", "policy")
    graph.add_edge("policy", END)
    return graph.compile()
