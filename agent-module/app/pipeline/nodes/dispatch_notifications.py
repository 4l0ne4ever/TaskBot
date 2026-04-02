from app.pipeline.state import PipelineState


def dispatch_notifications(state: PipelineState) -> dict:
    _ = state
    return {"notifications_sent": []}
