import pytest
from app.utils import estimate_token_count, calculate_usage, estimate_speed_from_parameters
from app.models import Message

def test_estimate_token_count():
    """Test the token counting function"""
    # Empty text should return 0
    assert estimate_token_count("") == 0
    
    # Short text should have some tokens
    assert estimate_token_count("Hello world") > 0
    
    # Longer text should have more tokens
    short = "This is a short sentence."
    long = "This is a much longer sentence that should have more tokens than the shorter sentence."
    assert estimate_token_count(long) > estimate_token_count(short)
    
    # Check approximate values (using ~4 chars per token)
    text = "This is exactly twenty chars"  # 24 chars
    assert 5 <= estimate_token_count(text) <= 7  # Should be about 6 tokens

def test_calculate_usage():
    """Test the usage calculation function"""
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Tell me a story.")
    ]
    completion = "Once upon a time, there was a robot."
    
    usage = calculate_usage(messages, completion)
    
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0

def test_estimate_speed_from_parameters():
    """Test the parameter-based speed estimation function"""
    # Check boundary conditions
    assert estimate_speed_from_parameters(0) == 25.0  # Base speed for 0 params
    
    # Check that larger models are slower
    small = estimate_speed_from_parameters(7)  # 7B model
    medium = estimate_speed_from_parameters(20)  # 20B model
    large = estimate_speed_from_parameters(70)  # 70B model
    xlarge = estimate_speed_from_parameters(170)  # 170B model
    
    assert small > medium > large > xlarge
    
    # Check a specific value for consistency
    speed_7b = estimate_speed_from_parameters(7)
    # The value should be consistent between runs
    assert 8.0 <= speed_7b <= 9.0
