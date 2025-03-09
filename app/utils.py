import math
from typing import List, Dict
from app.models import Message

def estimate_speed_from_parameters(params_billions: float) -> float:
    """
    Estimate token generation speed based on model parameter size.
    Larger models generally generate tokens slower.
    
    Formula: base_speed * (1 / log(params + 1))^1.5
    This gives reasonable estimates across parameter scales.
    """
    base_speed = 25  # Base tokens per second for a very small model
    if params_billions <= 0:
        return base_speed
    
    # Scale down speed as parameters increase
    # Using logarithmic scale to reflect diminishing impact of parameter count
    speed = base_speed * (1 / math.log(params_billions + 1)) ** 1.5
    
    # Keep speed within reasonable bounds
    return max(1.0, min(20.0, speed))

def estimate_token_count(text: str) -> int:
    """
    Estimate the number of tokens in a text.
    This is a simple approximation - about 4 characters per token for English.
    """
    if not text:
        return 0
    # Count characters and divide by 4 (rough approximation for English text)
    return max(1, int(len(text) / 4))

def calculate_usage(prompt_messages: List[Message], completion_text: str) -> Dict[str, int]:
    """
    Calculate token usage statistics for the request and response.
    """
    prompt_text = " ".join([msg.content for msg in prompt_messages])
    prompt_tokens = estimate_token_count(prompt_text)
    completion_tokens = estimate_token_count(completion_text)
    
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens
    }
