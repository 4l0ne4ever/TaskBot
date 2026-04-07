from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    gmail_interval: int
    drive_interval: int
    google_connected: bool


class SettingsUpdate(BaseModel):
    gmail_interval: int | None = Field(None, ge=5, le=1440)
    drive_interval: int | None = Field(None, ge=5, le=1440)
