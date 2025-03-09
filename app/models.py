from typing import Optional, List, Dict
from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str

class CompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    max_tokens: Optional[int] = 1000
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    response_length: Optional[str] = "medium"  # Options: short, medium, long, very_long, random

class ModelConfig(BaseModel):
    tokens_per_second: float
    description: str
    parameters: Optional[float] = None  # Parameters in billions
