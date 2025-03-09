import asyncio
import json
import time
import random
from typing import List, AsyncGenerator, Dict, Any
from app.models import Message, ModelConfig
from app.utils import estimate_token_count, calculate_usage
from app.config import MODEL_CONFIGS, DEFAULT_CONFIG, SAMPLE_RESPONSES
from app.config import MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT, TRUNCATION_MESSAGE

async def stream_response(content: str, model: str, messages: List[Message]) -> AsyncGenerator[str, None]:
    """Stream response with appropriate token generation speed for the model"""
    # Get tokens per second for this model
    model_config = MODEL_CONFIGS.get(model, DEFAULT_CONFIG)
    tokens_per_second = model_config.tokens_per_second
    
    # Split content into words to simulate token chunks
    words = content.split()
    chunks = []
    
    # Group words into chunks roughly representing tokens
    current_chunk = []
    for word in words:
        current_chunk.append(word)
        if len(' '.join(current_chunk)) >= 10:  # Approximate token size
            chunks.append(' '.join(current_chunk))
            current_chunk = []
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    # Calculate estimated streaming time and check if it exceeds limit
    estimated_tokens = sum(max(1, estimate_token_count(chunk)) for chunk in chunks)
    estimated_time = estimated_tokens / tokens_per_second if tokens_per_second > 0 else 0
    
    # Check if we need to truncate content
    will_truncate = ENFORCE_TIME_LIMIT and estimated_time > MAX_STREAM_TIME_SECONDS
    if will_truncate:
        # Calculate how many tokens we can output within the time limit
        max_tokens = int(MAX_STREAM_TIME_SECONDS * tokens_per_second)
        
        # Find the chunks that fit within the time limit
        tokens_so_far = 0
        truncate_index = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk_tokens = max(1, estimate_token_count(chunk))
            if tokens_so_far + chunk_tokens > max_tokens:
                truncate_index = i
                break
            tokens_so_far += chunk_tokens
        
        # Truncate chunks and add truncation message
        if truncate_index < len(chunks):
            chunks = chunks[:truncate_index]
            if TRUNCATION_MESSAGE:
                chunks.append(TRUNCATION_MESSAGE)
    
    # Generate a consistent ID for this response
    response_id = f"mock-chatcmpl-{int(time.time())}"
    
    # First chunk with role
    first_data = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "role": "assistant",
            },
            "finish_reason": None
        }]
    }
    yield f"data: {json.dumps(first_data)}\n\n"
    
    # Stream content chunks
    start_time = time.time()
    total_tokens = 0
    
    for i, chunk in enumerate(chunks):
        # More accurate token counting for each chunk
        chunk_tokens = max(1, estimate_token_count(chunk))
        total_tokens += chunk_tokens
        
        # Calculate proper delay based on tokens_per_second
        # Tokens should be generated at a rate of 'tokens_per_second'
        # So delay is chunk_tokens / tokens_per_second seconds
        delay = chunk_tokens / tokens_per_second
        
        # Check if we're about to exceed time limit
        elapsed_time = time.time() - start_time
        remaining_time = MAX_STREAM_TIME_SECONDS - elapsed_time
        
        # Apply delay, but respect remaining time if enforcing limit
        if ENFORCE_TIME_LIMIT and delay > remaining_time and remaining_time > 0:
            await asyncio.sleep(remaining_time)
        else:
            await asyncio.sleep(delay)
        
        # Check if we've exceeded time limit
        if ENFORCE_TIME_LIMIT and (time.time() - start_time) >= MAX_STREAM_TIME_SECONDS:
            # If this is the last chunk and it's the truncation message, send it
            if i == len(chunks) - 1 and chunk == TRUNCATION_MESSAGE:
                pass  # Continue to send this chunk
            else:
                # Skip remaining chunks
                break
        
        data = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": chunk,
                },
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(data)}\n\n"
    
    # Calculate actual token throughput
    end_time = time.time()
    elapsed_time = end_time - start_time
    actual_tokens_per_second = total_tokens / elapsed_time if elapsed_time > 0 else 0
    
    # Determine finish reason
    finish_reason = "stop"
    if will_truncate or (ENFORCE_TIME_LIMIT and (end_time - start_time) >= MAX_STREAM_TIME_SECONDS):
        finish_reason = "length"
        print(f"Response truncated due to time limit ({MAX_STREAM_TIME_SECONDS}s)")
    
    # Log actual throughput
    print(f"Model: {model}, Target: {tokens_per_second} t/s, Actual: {actual_tokens_per_second:.2f} t/s, Tokens: {total_tokens}, Time: {elapsed_time:.2f}s")
    
    # Calculate usage statistics for what was actually sent
    truncated_content = "".join([chunk for chunk in chunks[:i+1] if chunk != TRUNCATION_MESSAGE])
    usage = calculate_usage(messages, truncated_content)
    
    # Final chunk with usage information
    final_data = {
        "id": response_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": finish_reason
        }],
        "usage": usage
    }
    yield f"data: {json.dumps(final_data)}\n\n"
    yield "data: [DONE]\n\n"

def get_response_content(response_length: str) -> str:
    """Get the appropriate response content based on the requested length"""
    if response_length == "random":
        response_length = random.choice(list(SAMPLE_RESPONSES.keys()))
    
    return SAMPLE_RESPONSES.get(response_length, SAMPLE_RESPONSES.get("medium", ""))
