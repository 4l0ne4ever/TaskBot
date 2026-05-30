from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    gmail_interval: int
    drive_interval: int
    sync_profile: str
    google_connected: bool
    # Account mode (Round 11, 2026-05-30):
    #   "single" — personal inbox only; /team route hidden; no sent-folder sync
    #   "team"   — Lead persona; also syncs "in:sent" folder; /team route visible;
    #              sent-context tasks aggregate by extracted assignee in /team and
    #              are NOT shown in /tasks (current user is the assignor, not the
    #              assignee, so they fall out of the user-as-assignee filter).
    # Default is "single" for backward compatibility — existing users keep their
    # current behaviour with no migration. Stored in users.sync_config["mode"].
    mode: str


class SettingsUpdate(BaseModel):
    gmail_interval: int | None = Field(None, ge=5, le=1440)
    drive_interval: int | None = Field(None, ge=5, le=1440)
    sync_profile: str | None = Field(None, pattern=r"^(strict_work|balanced|broad)$")
    # Forward-only switching: data backfill is NOT performed when going from
    # single → team. Sent emails from the switch onwards will sync; historical
    # sent emails are not retroactively pulled. This avoids quota blowup and
    # surprising historical delegations from re-surfacing in /team. The pattern
    # itself accepts either direction.
    mode: str | None = Field(None, pattern=r"^(single|team)$")
