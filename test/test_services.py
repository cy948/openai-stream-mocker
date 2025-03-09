import pytest
import time
import json
import asyncio
from typing import List
import statistics

from app.services import stream_response
from app.models import Message, ModelConfig

async def collect_stream(content: str, model_config: ModelConfig, messages: List[Message]):
    """Helper function to collect streaming response and measure time"""
    # Create a temporary model for the test
    model_name = f"test-model-{int(time.time())}"
    
    # Mock app.config data with our test model
    from app.config import MODEL_CONFIGS
    MODEL_CONFIGS[model_name] = model_config
    
    start_time = time.time()
    chunks = []
    token_count = 0
    
    try:
        # Collect all chunks and measure the time
        async for chunk in stream_response(content, model_name, messages):
            chunks.append(chunk)
            # Count tokens from chunks 
            if "data: {" in chunk:
                data = json.loads(chunk.replace("data: ", "").strip())
                if "choices" in data and data["choices"] and "delta" in data["choices"][0]:
                    delta = data["choices"][0]["delta"]
                    if "content" in delta:
                        # Rough token count based on content
                        token_count += len(delta["content"]) // 4 or 1
    except Exception as e:
        print(f"Error in collect_stream: {e}")
        
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    return {
        "chunks": chunks,
        "elapsed_time": elapsed_time,
        "token_count": token_count,
        "tokens_per_second": token_count / elapsed_time if elapsed_time > 0 else 0
    }

@pytest.mark.asyncio
async def test_stream_speed_fast(fast_model_config, sample_messages, medium_text):
    """Test that a fast model streams at approximately the expected speed"""
    target_speed = fast_model_config.tokens_per_second
    result = await collect_stream(medium_text, fast_model_config, sample_messages)
    
    # We expect the actual speed to be within a reasonable margin of error
    # For a fast model (50 tokens/sec), allow 30% deviation
    margin = 0.30
    min_expected = target_speed * (1 - margin)
    max_expected = target_speed * (1 + margin)
    
    assert result["elapsed_time"] > 0.1  # Should take some time
    print(f"Fast model - Target: {target_speed} t/s, Actual: {result['tokens_per_second']:.2f} t/s")
    assert min_expected <= result["tokens_per_second"] <= max_expected

@pytest.mark.asyncio
async def test_stream_speed_slow(slow_model_config, sample_messages, short_text):
    """Test that a slow model streams at approximately the expected speed"""
    target_speed = slow_model_config.tokens_per_second
    result = await collect_stream(short_text, slow_model_config, sample_messages)
    
    # For a slow model (5 tokens/sec), allow 30% deviation
    margin = 0.30
    min_expected = target_speed * (1 - margin)
    max_expected = target_speed * (1 + margin)
    
    assert result["elapsed_time"] > 0.1  # Should take some time
    print(f"Slow model - Target: {target_speed} t/s, Actual: {result['tokens_per_second']:.2f} t/s")
    assert min_expected <= result["tokens_per_second"] <= max_expected

@pytest.mark.asyncio
async def test_time_limit_enforced(slow_model_config, sample_messages, medium_text):
    """Test that the time limit is enforced for slow models with long content"""
    # Set up a very slow model to ensure it hits the time limit
    very_slow_model = ModelConfig(
        tokens_per_second=1.0,  # Very slow: 1 token per second
        description="Very slow test model",
        parameters=200
    )
    
    # Import time limit settings
    from app.config import MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT
    
    # Skip test if time limits aren't enforced
    if not ENFORCE_TIME_LIMIT:
        pytest.skip("Time limit enforcement is disabled")
    
    start_time = time.time()
    result = await collect_stream(medium_text, very_slow_model, sample_messages)
    elapsed_time = time.time() - start_time
    
    # The elapsed time should be approximately the maximum allowed
    # Allow for a small margin of error due to processing overhead
    margin = 0.3  # 30% margin
    
    print(f"Time limit test - Max allowed: {MAX_STREAM_TIME_SECONDS}s, Actual: {elapsed_time:.2f}s")
    assert elapsed_time <= MAX_STREAM_TIME_SECONDS * (1 + margin)
    
    # Check that we have a truncation message in the final parts
    found_truncation = False
    for chunk in result["chunks"]:
        if "Content truncated" in chunk:
            found_truncation = True
            break
            
    assert found_truncation

@pytest.mark.asyncio
async def test_consistency_of_speed(medium_model_config, sample_messages, medium_text):
    """Test that the streaming speed is consistent across multiple runs"""
    speeds = []
    
    # Run multiple times to check consistency
    for _ in range(3):
        result = await collect_stream(medium_text, medium_model_config, sample_messages)
        speeds.append(result["tokens_per_second"])
        # Small delay between runs
        await asyncio.sleep(0.1)
    
    # Calculate statistics
    mean_speed = statistics.mean(speeds)
    stdev = statistics.stdev(speeds) if len(speeds) > 1 else 0
    
    print(f"Consistency test - Mean speed: {mean_speed:.2f} t/s, StdDev: {stdev:.2f}, CV: {stdev/mean_speed:.2%}")
    
    # The coefficient of variation (CV) should be relatively small
    # indicating consistent speed (stdev < 20% of mean)
    assert stdev / mean_speed < 0.2
