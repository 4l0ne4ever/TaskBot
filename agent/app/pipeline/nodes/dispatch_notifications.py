from app.pipeline.state import PipelineState
from app.services.notification_service import dispatch_notifications_sync


def dispatch_notifications(state: PipelineState) -> dict:
    return dispatch_notifications_sync(state)
