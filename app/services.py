import asyncio
import json
import time
import random
import re
from typing import List, AsyncGenerator, Dict, Any
from app.models import Message, ModelConfig
from app.utils import estimate_token_count, calculate_usage
from app.config import MODEL_CONFIGS, DEFAULT_CONFIG, SAMPLE_RESPONSES
from app.config import MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT, TRUNCATION_MESSAGE

async def stream_response(content: str, model: str, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """Stream response with appropriate token generation speed for the model"""
    # Get tokens per second for this model
    model_config = MODEL_CONFIGS.get(model, DEFAULT_CONFIG)
    tokens_per_second = model_config.tokens_per_second
    
    # Check for model-specific time limit override
    model_time_limit = getattr(model_config, "max_stream_time_seconds", MAX_STREAM_TIME_SECONDS)
    effective_time_limit = model_time_limit if model_time_limit else MAX_STREAM_TIME_SECONDS
    
    # Log the current settings
    print(f"Streaming with model: {model}, Speed: {tokens_per_second} tokens/s")
    print(f"Time limit: {effective_time_limit}s (Global: {MAX_STREAM_TIME_SECONDS}s), Enforce limit: {ENFORCE_TIME_LIMIT}")
    
    # Process content to identify paragraph boundaries
    paragraphs = re.split(r'\n\s*\n', content)
    
    # For high-speed models, use larger chunks to reduce overhead
    chunk_size_factor = 1.0
    if tokens_per_second > 50:
        chunk_size_factor = min(3.0, tokens_per_second / 30)  # Scale chunk size with model speed
    
    # Split paragraphs into chunks for streaming
    chunks = []
    for paragraph in paragraphs:
        # Split paragraph into words
        words = paragraph.split()
        current_chunk = []
        
        target_chunk_size = 10 * chunk_size_factor
        
        for word in words:
            current_chunk.append(word)
            # Create chunks of approximately token size, scaled by speed
            if len(' '.join(current_chunk)) >= target_chunk_size:  
                chunks.append(' '.join(current_chunk))
                current_chunk = []
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # Mark paragraph boundaries with a special token
        chunks.append("__PARAGRAPH_BREAK__")
    
    # Remove the last paragraph break
    if chunks and chunks[-1] == "__PARAGRAPH_BREAK__":
        chunks.pop()
    
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
    
    # Start timing from here
    start_time = time.time()
    total_tokens = 0
    current_paragraph_chunks = []
    exceeded_time_limit = False
    
    # Optimize batch processing for high-speed models
    batch_size = 1
    if tokens_per_second > 50:
        # Larger batches for faster models to reduce delay overhead
        batch_size = min(5, int(tokens_per_second / 20))
    
    i = 0
    while i < len(chunks):
        # CHECK TIME LIMIT: Check if we've exceeded time limit
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # If enforcing time limit and we've exceeded it, prepare to complete the current paragraph and stop
        if ENFORCE_TIME_LIMIT and elapsed_time >= effective_time_limit:
            print(f"Time limit reached: {elapsed_time:.2f}s > {effective_time_limit}s")
            exceeded_time_limit = True
            
            # Find the next paragraph break to complete the current paragraph
            next_break = i
            while next_break < len(chunks) and chunks[next_break] != "__PARAGRAPH_BREAK__":
                next_break += 1
                
            # Complete the current paragraph
            for j in range(i, next_break):
                chunk = chunks[j]
                if chunk != "__PARAGRAPH_BREAK__":
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
            
            # Add truncation message if configured
            if TRUNCATION_MESSAGE:
                data = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": "\n\n" + TRUNCATION_MESSAGE,
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(data)}\n\n"
            
            break
        
        # Process current chunk
        chunk = chunks[i]
        
        # If this is a paragraph break marker
        if chunk == "__PARAGRAPH_BREAK__":
            # Add a new line between paragraphs
            if current_paragraph_chunks:
                data = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": "\n\n",
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(data)}\n\n"
                
                # Clear paragraph buffer
                current_paragraph_chunks = []
                
            i += 1
            continue
        
        # Add chunk to current paragraph
        current_paragraph_chunks.append(chunk)
        
        # Calculate tokens and delay for this chunk
        chunk_tokens = max(1, estimate_token_count(chunk))
        total_tokens += chunk_tokens
        delay = chunk_tokens / tokens_per_second
        
        # Apply delay
        await asyncio.sleep(delay)
        
        # Send the chunk
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
        
        i += 1
    
    # Calculate actual token throughput
    end_time = time.time()
    elapsed_time = end_time - start_time
    actual_tokens_per_second = total_tokens / elapsed_time if elapsed_time > 0 else 0
    
    # Determine finish reason
    finish_reason = "stop"
    if exceeded_time_limit:
        finish_reason = "length"
        print(f"Response truncated due to time limit ({effective_time_limit}s)")
    
    # Log actual throughput
    print(f"Model: {model}, Target: {tokens_per_second} t/s, Actual: {actual_tokens_per_second:.2f} t/s, Tokens: {total_tokens}, Time: {elapsed_time:.2f}s")
    
    # Final chunk with usage information
    sent_content = " ".join([c for c in chunks[:i] if c != "__PARAGRAPH_BREAK__"])
    usage = calculate_usage(messages, sent_content)
    
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
        response_length = random.choice([k for k in SAMPLE_RESPONSES.keys() if k not in ["auto"]])
    
    return SAMPLE_RESPONSES.get(response_length, SAMPLE_RESPONSES.get("medium", ""))

def get_response_content_for_duration(duration_seconds, model, tokens_per_second=None):
    """
    Get response content that would take approximately the specified duration to generate
    
    Args:
        duration_seconds: Time in seconds the response should take to generate
        model: Model ID to use for speed calculation
        tokens_per_second: Override for model's token generation speed
    """
    from app.config import MODEL_CONFIGS, DEFAULT_CONFIG
    
    # Get the model's tokens per second rate (or use provided override)
    if tokens_per_second is None:
        model_config = MODEL_CONFIGS.get(model, DEFAULT_CONFIG)
        tokens_per_second = model_config.tokens_per_second
    
    # Calculate how many tokens should be generated in the given duration
    target_token_count = int(duration_seconds * tokens_per_second)
    
    # Ensure we have a reasonable minimum
    target_token_count = max(target_token_count, 10)
    
    # Get sample text that's approximately the right length
    # Estimate about 4 characters per token as a rough conversion
    target_char_length = target_token_count * 4
    
    # Find the closest predefined response or generate a custom one
    from app.config import SAMPLE_RESPONSES
    
    # Check if any standard responses are close to our target
    closest_standard_key = None
    closest_diff = float('inf')
    
    for length, content in SAMPLE_RESPONSES.items():
        try:
            if isinstance(length, str) and length != "auto":
                length_val = int(length)
                diff = abs(length_val - target_char_length)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_standard_key = length
        except ValueError:
            continue
    
    # If we found a close enough standard response (within 20% difference), use it
    if closest_standard_key and closest_diff < (target_char_length * 0.2):
        return SAMPLE_RESPONSES[closest_standard_key]
    
    # Otherwise, generate a custom response of appropriate length
    import lorem
    
    # Generate paragraphs until we reach or exceed the target length
    content = ""
    while len(content) < target_char_length:
        content += lorem.paragraph() + "\n\n"
    
    return content.strip()
