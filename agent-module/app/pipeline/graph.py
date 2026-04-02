from langgraph.graph import END, StateGraph

from app.pipeline.nodes.dispatch_notifications import dispatch_notifications
from app.pipeline.nodes.extract_tasks import extract_tasks
from app.pipeline.nodes.normalize_tasks import normalize_tasks
from app.pipeline.nodes.parse_input import parse_input
from app.pipeline.nodes.save_tasks import save_tasks
from app.pipeline.nodes.validate_tasks import validate_tasks
from app.pipeline.state import PipelineState


def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("parse_input", parse_input)
    graph.add_node("extract_tasks", extract_tasks)
    graph.add_node("normalize_tasks", normalize_tasks)
    graph.add_node("validate_tasks", validate_tasks)
    graph.add_node("save_tasks", save_tasks)
    graph.add_node("dispatch_notifications", dispatch_notifications)

    graph.set_entry_point("parse_input")

    graph.add_conditional_edges(
        "parse_input",
        lambda s: "save_tasks" if s.get("should_stop") else "extract_tasks",
        {"extract_tasks": "extract_tasks", "save_tasks": "save_tasks"},
    )

    graph.add_conditional_edges(
        "extract_tasks",
        lambda s: "save_tasks" if (s.get("should_stop") or not s.get("extracted_tasks")) else "normalize_tasks",
        {"normalize_tasks": "normalize_tasks", "save_tasks": "save_tasks"},
    )

    graph.add_edge("normalize_tasks", "validate_tasks")
    graph.add_edge("validate_tasks", "save_tasks")
    graph.add_edge("save_tasks", "dispatch_notifications")
    graph.add_edge("dispatch_notifications", END)
    return graph.compile()


pipeline = build_pipeline()
