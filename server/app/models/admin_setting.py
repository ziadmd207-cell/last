from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class AdminSetting(SQLModel, table=True):
    __tablename__ = "admin_settings"

    id: str = Field(default="default", primary_key=True)
    # Pricing configuration (single source of truth)
    starter_price: float = Field(default=99.0)
    pro_price: float = Field(default=199.0)
    prime_price: float = Field(default=399.0)
    currency: str = Field(default="EGP")

    # AI Model API configuration
    active_ai_provider: str = Field(default="auto")  # auto, groq, gemini, openai, pollinations
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = Field(default="openai/gpt-oss-20b")
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = Field(default="gemini-1.5-flash")
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = Field(default="gpt-4o-mini")
    hf_token: Optional[str] = None
    hf_model: Optional[str] = Field(default="meta-llama/Llama-3.1-8B-Instruct")

    # YouTube API configuration (Only external service actively used)
    youtube_api_key: Optional[str] = None

    # Deprecated/unused placeholders kept optional for backward compatibility
    search_api_key: Optional[str] = None
    job_search_api_key: Optional[str] = None

    updated_date: datetime = Field(default_factory=datetime.utcnow)
