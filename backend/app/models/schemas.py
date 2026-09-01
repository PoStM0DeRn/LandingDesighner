from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class LandingStatus(str, Enum):
    generating = "generating"
    ready = "ready"
    error = "error"


class LLMProvider(str, Enum):
    local = "local"
    openai = "openai"


class SectionType(str, Enum):
    hero = "hero"
    features = "features"
    about = "about"
    services = "services"
    testimonials = "testimonials"
    pricing = "pricing"
    faq = "faq"
    cta = "cta"
    footer = "footer"


class ImageRequest(BaseModel):
    section_type: str = ""
    section_index: int = 0
    prompt: str = ""
    width: int = 1024
    height: int = 1024
    style: str = "photo"
    seed: int = -1


class Section(BaseModel):
    type: SectionType
    title: str = ""
    subtitle: str = ""
    description: str = ""
    items: list[dict] = Field(default_factory=list)
    button_text: str = ""
    button_url: str = ""
    image_url: str = ""
    image_requests: list[ImageRequest] = Field(default_factory=list)


class Intent(BaseModel):
    topic: str = ""
    style: str = "minimalist"
    tone: str = "professional"
    target_audience: str = ""
    keywords: list[str] = Field(default_factory=list)
    color_preferences: list[str] = Field(default_factory=list)
    sections: list[SectionType] = Field(
        default_factory=lambda: [SectionType.hero, SectionType.features, SectionType.cta, SectionType.footer]
    )


class DesignTokens(BaseModel):
    primary_color: str = "#6366f1"
    secondary_color: str = "#8b5cf6"
    accent_color: str = "#06b6d4"
    bg_color: str = "#ffffff"
    text_color: str = "#1e293b"
    heading_font: str = "Inter"
    body_font: str = "Inter"
    border_radius: str = "0.75rem"


class LandingMeta(BaseModel):
    id: str
    title: str
    description: str
    prompt: str
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    status: LandingStatus = LandingStatus.generating
    error_message: Optional[str] = None
    thumbnail_url: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    owner_nickname: Optional[str] = None
    # None/True = published (legacy landings stay visible), False = draft
    published: Optional[bool] = None


class LandingDetail(LandingMeta):
    html: str = ""
    css: str = ""


class GenerateRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    provider: LLMProvider = LLMProvider.local
    model: str = "llama-3"
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    skill_ids: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    id: str
    status: LandingStatus
    message: str


class PaginatedResponse(BaseModel):
    items: list[LandingMeta]
    total: int
    page: int
    page_size: int
    pages: int


class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    prompt_addition: str
    built_in: bool = False


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    prompt_addition: str


class ValidationReport(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GenerationSkillInfo(BaseModel):
    name: str
    description: str = ""
    prompt_addition: str


class GenerationInfo(BaseModel):
    """Full generation details for reproducibility / transparency."""
    available: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt: str = ""
    use_llm_markup: bool = False
    image_steps: Optional[int] = None
    comfyui_workflow_path: Optional[str] = None
    intent: Optional[dict] = None
    tokens: Optional[dict] = None
    skills: list[GenerationSkillInfo] = Field(default_factory=list)


class AuthRequest(BaseModel):
    nickname: str
    password: str


class UserPublic(BaseModel):
    nickname: str
    created_at: Optional[float] = None


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class PublishRequest(BaseModel):
    published: bool
