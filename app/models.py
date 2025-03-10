from typing import Optional, List, Dict
from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str

class CompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    response_length: Optional[str] = "auto"  # Options: short, medium, long, very_long, random, auto
    duration_seconds: Optional[float] = None

class ModelConfig(BaseModel):
    """Configuration for a specific model"""
    tokens_per_second: float
    description: str = None
    parameters: Optional[float] = None
    max_stream_time_seconds: Optional[int] = None  # Model-specific time limit override
