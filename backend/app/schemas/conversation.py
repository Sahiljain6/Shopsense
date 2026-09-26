from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class TokenUsage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class MessageMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    annotations: list[Any] = Field(default_factory=list)
    sources: list[Any] = Field(default_factory=list)
    tool_calls: list[Any] = Field(default_factory=list)
    revision: int = 1
    status: str = "completed"


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    conversation_id: str
    sequence_number: int
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    tokens_total: int = 0
    created_at: datetime
    edited_at: datetime | None = None
    is_deleted: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=16000)
    role: Literal["user", "assistant", "system", "tool"] = "user"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=16000)
    revision: int = Field(..., description="Optimistic locking revision number")


class ConversationMetadata(BaseModel):
    tags: list[str] = Field(default_factory=list)
    folder: str = "default"
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    pinned: bool = False


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    model_used: str = Field(default="gpt-4o")
    system_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    model_used: str | None = None
    system_prompt: str | None = None
    is_flagged: bool | None = None
    metadata: dict[str, Any] | None = None


class ConversationSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    conversation_id: str
    summary_text: str
    summary_version: int
    message_range: dict[str, Any]
    start_sequence_number: int
    end_sequence_number: int
    source_token_count: int
    summary_token_count: int
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: int | None
    title: str
    model_used: str
    system_prompt: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    total_messages: int
    total_tokens_used: int
    total_cost_usd: float
    version: int
    is_flagged: bool
    parent_conversation_id: str | None
    branch_point_message_id: str | None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ConversationBranchRequest(BaseModel):
    branch_from_message_id: str
    title: str | None = None
    model_used: str | None = None


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[MessageRead]
    summary: ConversationSummaryRead | None = None
    total_count: int
    has_more: bool = False
    next_cursor: str | None = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationRead]
    total: int
    limit: int
    offset: int


class ConversationSearchQuery(BaseModel):
    query: str
    limit: int = 10
    include_archived: bool = False
    tag: str | None = None


class ConversationExportResponse(BaseModel):
    conversation_id: str
    format: Literal["json", "markdown", "csv"]
    exported_at: datetime
    content: str
