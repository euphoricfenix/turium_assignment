"""Request and response models for the public API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SourceType = Literal["note", "url"]


class IngestRequest(BaseModel):
    source_type: SourceType
    content: str = Field(min_length=1, max_length=50_000)

    @field_validator("content")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def check_content_matches_source_type(self) -> "IngestRequest":
        if not self.content:
            raise ValueError("content must not be blank")
        if self.source_type == "url" and not self.content.startswith(("http://", "https://")):
            raise ValueError("content must be an http(s) URL when source_type is 'url'")
        return self


class IngestResponse(BaseModel):
    id: int
    source_type: SourceType
    title: str
    chunk_count: int


class ItemSummary(BaseModel):
    id: int
    source_type: SourceType
    source_url: str | None
    title: str
    preview: str
    chunk_count: int
    created_at: str


class Turn(BaseModel):
    """One earlier message in the conversation, as the client remembers it."""

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4_000)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1_000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    # Capped server side: the client decides how much to send, the server
    # decides how much it will accept.
    history: list[Turn] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        return value.strip()


class Source(BaseModel):
    citation: int
    item_id: int
    title: str
    source_url: str | None
    heading_path: str
    snippet: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
