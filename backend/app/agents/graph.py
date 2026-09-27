"""
Wires the Quorum agent graph: Planner -> Retriever -> Analyst -> Verifier,
with a conditional short-circuit for out-of-scope questions and a
conditional single retry back to the Retriever when the Verifier's
confidence comes back low.

    START -> planner --(out_of_scope)--> out_of_scope -> END
               |--(else)--> retriever -> analyst --(first pass)--> verifier
                                              |--(retry pass)--> skip_reverification -> END
                                  verifier --(confidence=low, first pass)--> retriever
                                  verifier --(else)--> END
"""
from langgraph.graph import END, START, StateGraph

from app.agents.analyst import analyze
from app.agents.planner import plan
from app.agents.retriever import retrieve
from app.agents.state import QuorumState
from app.agents.verifier import skip_reverification, verify


def _out_of_scope_reply(state: QuorumState) -> dict:
    return {
        "final_answer": (
            "I couldn't find anything relevant to that in the selected "
            "document(s). Try asking about their content, or select a "
            "different document."
        ),
        "confidence": "high",
        "citations": [],
    }


def _route_after_planner(state: QuorumState) -> str:
    return "out_of_scope" if state.get("plan") == "out_of_scope" else "retriever"


def _route_after_analyst(state: QuorumState) -> str:
    return "skip_reverification" if state.get("retry_count", 0) > 0 else "verifier"


def _route_after_verifier(state: QuorumState) -> str:
    return END if "final_answer" in state else "retriever"


def build_graph():
    graph = StateGraph(QuorumState)

    graph.add_node("planner", plan)
    graph.add_node("out_of_scope", _out_of_scope_reply)
    graph.add_node("retriever", retrieve)
    graph.add_node("analyst", analyze)
    graph.add_node("verifier", verify)
    graph.add_node("skip_reverification", skip_reverification)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", _route_after_planner, ["out_of_scope", "retriever"])
    graph.add_edge("out_of_scope", END)
    graph.add_edge("retriever", "analyst")
    graph.add_conditional_edges("analyst", _route_after_analyst, ["verifier", "skip_reverification"])
    graph.add_conditional_edges("verifier", _route_after_verifier, ["retriever", END])
    graph.add_edge("skip_reverification", END)

    return graph.compile()


quorum_graph = build_graph()
