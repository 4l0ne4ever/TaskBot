from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    gmail_interval: int
    drive_interval: int
    sync_profile: str
    google_connected: bool


class SettingsUpdate(BaseModel):
    gmail_interval: int | None = Field(None, ge=5, le=1440)
    drive_interval: int | None = Field(None, ge=5, le=1440)
    sync_profile: str | None = Field(None, pattern=r"^(strict_work|balanced|broad)$")
