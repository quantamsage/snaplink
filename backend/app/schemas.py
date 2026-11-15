"""Pydantic models: every request and response shape, matching docs/openapi.yaml."""
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

CODE_PATTERN = r"^[A-Za-z0-9_-]{3,32}$"
MAX_URL_LENGTH = 2048
Code = Annotated[str, Field(pattern=CODE_PATTERN)]
MaxClicks = Annotated[int, Field(ge=1, le=1_000_000)]


def _future(value: datetime | None) -> datetime | None:
    if value is not None and value <= datetime.now(timezone.utc):
        raise ValueError("must be in the future")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are rejected, not silently ignored


class Credentials(StrictModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class User(BaseModel):
    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class LinkCreate(StrictModel):
    # HttpUrl only accepts http/https, so javascript:, data:, file: etc. are rejected.
    target_url: HttpUrl
    custom_code: Code | None = None
    # Optional limits. AwareDatetime: the time must include a timezone (e.g. "Z").
    expires_at: AwareDatetime | None = None
    max_clicks: MaxClicks | None = None

    @field_validator("expires_at")
    @classmethod
    def expires_in_future(cls, value):
        return _future(value)

    @field_validator("target_url")
    @classmethod
    def limit_url_length(cls, value: HttpUrl) -> HttpUrl:
        # Checked after normalisation, to match the database CHECK (<= 2048) exactly.
        if len(str(value)) > MAX_URL_LENGTH:
            raise ValueError(f"URL must be {MAX_URL_LENGTH} characters or fewer")
        return value


class LinkUpdate(StrictModel):
    """Change or remove a link's limits. Send null to remove a limit."""
    expires_at: AwareDatetime | None = None
    max_clicks: MaxClicks | None = None

    @field_validator("expires_at")
    @classmethod
    def expires_in_future(cls, value):
        return _future(value)

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.model_fields_set:
            raise ValueError("send expires_at and/or max_clicks")
        return self


class Link(BaseModel):
    id: int
    code: str
    short_url: str
    target_url: str
    created_at: datetime
    click_count: int
    expires_at: datetime | None
    max_clicks: int | None
    active: bool  # false once expired or out of clicks
    inactive_reason: Literal["expired", "click_limit"] | None


class LinkList(BaseModel):
    items: list[Link]
    total: int


class DailyClicks(BaseModel):
    date: date
    clicks: int


class ReferrerClicks(BaseModel):
    referrer: str
    clicks: int


class LinkStats(BaseModel):
    link_id: int
    total_clicks: int
    window_clicks: int
    days: int
    daily: list[DailyClicks]
    top_referrers: list[ReferrerClicks]
