import pytest
import time
import json
import asyncio
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_streaming_endpoint():
    """Test that the streaming endpoint returns the expected format"""
    # Prepare a request to the streaming API
    request_data = {
        "model": "gpt-3.5-turbo",  # Use a predefined model
        "messages": [
            {"role": "user", "content": "Tell me a short story."}
        ],
        "stream": True,
        "response_length": "short"  # Use a short response for quicker testing
    }
    
    # Make the request
    start_time = time.time()
    response = client.post("/v1/chat/completions", json=request_data)
    
    # Check that response is successful
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"
    
    # Process the chunks
    chunks = []
    content = ""
    
    for line in response.iter_lines():
        if line:
            # Remove b' prefix and ' suffix from bytes and decode
            line_text = line.decode('utf-8')
            chunks.append(line_text)
            
            if line_text.startswith("data: {"):
                data = json.loads(line_text[6:])  # Skip the "data: " prefix
                if "choices" in data and data["choices"] and "delta" in data["choices"][0]:
                    delta = data["choices"][0]["delta"]
                    if "content" in delta:
                        content += delta["content"]
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Verify response format
    assert len(chunks) > 2  # Should have at least first chunk, content, and [DONE]
    assert chunks[-1] == "data: [DONE]"
    
    # Check content and timing
    assert len(content) > 0
    assert elapsed_time > 0.1  # Should take some time
    
    # Check that the last chunk includes usage information
    for i in range(len(chunks) - 2, -1, -1):
        if chunks[i].startswith("data: {"):
            last_data = json.loads(chunks[i][6:])
            if "usage" in last_data:
                usage = last_data["usage"]
                assert "prompt_tokens" in usage
                assert "completion_tokens" in usage
                assert "total_tokens" in usage
                break

def test_model_speed_update():
    """Test that updating a model's speed affects the streaming rate"""
    model_name = "test-speed-update-model"
    
    # First, create a new model
    client.post("/config", json={
        "model": model_name,
        "tokens_per_second": 10,
        "description": "Test model for speed updates"
    })
    
    # Test streaming with initial speed
    request_data = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Test message"}
        ],
        "stream": True,
        "response_length": "medium"
    }
    
    start_time = time.time()
    response1 = client.post("/v1/chat/completions", json=request_data)
    
    # Consume response to completion
    chunks = list(response1.iter_lines())
    elapsed_time1 = time.time() - start_time
    
    # Update model speed to be much faster
    client.post("/config", json={
        "model": model_name,
        "tokens_per_second": 50
    })
    
    # Test streaming with updated speed
    start_time = time.time()
    response2 = client.post("/v1/chat/completions", json=request_data)
    
    # Consume response to completion
    chunks = list(response2.iter_lines())
    elapsed_time2 = time.time() - start_time
    
    # The second response should be significantly faster
    assert elapsed_time1 > elapsed_time2 * 1.5
