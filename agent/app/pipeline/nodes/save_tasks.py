from app.pipeline.state import PipelineState
from app.services.save_tasks_service import save_tasks_sync


def save_tasks(state: PipelineState) -> dict:
    return save_tasks_sync(state)
