from langgraph.graph import END, StateGraph
from app.services.agents.nodes import compare_node, guardrail_node, orchestrator_node, recommend_node, review_node, search_node
from app.services.agents.state import ShopSenseState


def _route(state: ShopSenseState) -> str:
    intent = state.get("intent", "recommend")
    if intent == "compare":
        return "compare"
    if intent == "review":
        return "review"
    return "recommend"


def build_graph():
    graph = StateGraph(ShopSenseState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("search", search_node)
    graph.add_node("recommend", recommend_node)
    graph.add_node("compare", compare_node)
    graph.add_node("review", review_node)
    graph.add_node("guardrail", guardrail_node)
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "search")
    graph.add_conditional_edges("search", _route, {"recommend": "recommend", "compare": "compare", "review": "review"})
    graph.add_edge("recommend", "guardrail")
    graph.add_edge("compare", "guardrail")
    graph.add_edge("review", "guardrail")
    graph.add_edge("guardrail", END)
    return graph.compile()


def run_graph(state: ShopSenseState) -> ShopSenseState:
    return build_graph().invoke(state)
