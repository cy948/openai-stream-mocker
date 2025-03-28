# OpenAI Stream Mocker

A simple server that mocks OpenAI's streaming API, allowing you to test applications with configurable token generation speed based on model parameters.

## Introduction

This tool simulates OpenAI's streaming API responses, designed specifically for frontend developers who need to test and optimize UI/UX for AI chat interfaces. It provides a controlled environment to:

- Test the smoothness and responsiveness of typing animations and text rendering
- Benchmark your application's performance with different token streaming speeds
- Debug edge cases in stream handling without incurring API costs
- Validate token usage statistics and speed calculations in your frontend
- Simulate different model response behaviors from fast to slow generation speeds
- Ensure your application gracefully handles variable network conditions

Perfect for developers building chat interfaces, code completion tools, or any application that consumes streaming AI responses.

## Installation

### Using Conda (Recommended)

```bash
# Create and activate conda environment
conda env create -f environment.yml
conda activate openai-stream-mocker
```

### Using Pip

```bash
pip install -r requirements.txt
```

## Usage

### Start the server

```bash
python main.py
```

The server will run at http://localhost:8000

### Configuration

The server is configured using `config.toml` file which includes:

- Model configurations (tokens per second, description, parameters)
- Response templates for various lengths
- Default settings
- Time limit settings
- Auto response length settings

### Auto Response Length Configuration

The system determines which response length to use based on the model's speed. This mapping is configurable in the `config.toml` file:

```toml
# Define auto response length thresholds
[auto_response_length]
# For models with ≤3 tokens per second (slow models)
slow = { max_tokens_per_second = 3.0, response_length = "short" }
# For models with 3-7 tokens per second (medium speed models)
medium = { max_tokens_per_second = 7.0, response_length = "medium" }
# For models with >7 tokens per second (fast models)
fast = { max_tokens_per_second = 999999, response_length = "long" }
```

You can adjust these thresholds and associated response lengths to better match your specific testing needs.

#### Time Limit Configuration

The server can enforce a maximum time limit for streaming responses. This is useful for ensuring that responses don't take too long, even with slow token rates:

```toml
[general]
max_stream_time_seconds = 5    # Maximum time allowed for streaming response
enforce_time_limit = true      # Whether to enforce the time limit
truncation_message = "... [Content truncated due to time limit]"  # Added to responses when truncated
```

If a response would take longer than the time limit, the server will:
1. Pre-calculate which chunks can be sent within the limit
2. Truncate the response to fit within the time limit
3. Add a truncation message (if configured)
4. Set the `finish_reason` to `"length"` instead of `"stop"`

You can modify this file and reload the configuration without restarting the server:

```
POST /config/reload
```

### API Endpoints

#### Chat Completions Endpoint

```
POST /v1/chat/completions
```

This endpoint mimics the OpenAI chat completions API. You can send requests in the same format as you would to OpenAI's API.

Example request:

```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {
      "role": "user",
      "content": "Tell me a story."
    }
  ],
  "stream": true,
  "response_length": "long"
}
```

The `response_length` parameter is optional and can be one of:
- `short`: Brief response (~25 tokens)
- `medium`: Standard response (~100 tokens) - default
- `long`: Extended response (~400 tokens) 
- `very_long`: Comprehensive response (~1500 tokens)
- `random`: Randomly selects one of the above lengths

Example non-streaming response:

```json
{
  "id": "mock-completion-1686779763",
  "object": "chat.completion",
  "created": 1686779763,
  "model": "gpt-3.5-turbo",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Once upon a time..."
      },
      "finish_reason": "stop",
      "index": 0
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 25,
    "total_tokens": 37
  }
}
```

Example of final streaming chunk:

```
data: {"id":"mock-chatcmpl-1741531420","object":"chat.completion.chunk","created":1741531420,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":38,"completion_tokens":8,"total_tokens":46}}
```

#### List Available Response Lengths

```
GET /responses
```

Returns information about available response length options and their approximate token counts.

#### List Available Models

```
GET /v1/models
```

Returns a list of all available models in OpenAI-compatible format.

#### Configure Token Generation Speed

Configure the token generation speed for a specific model:

```
POST /config
```

```json
{
  "model": "gpt-4",
  "tokens_per_second": 3.5
}
```

Add a model with automatic speed calculation based on parameters (in billions):

```json
{
  "model": "my-custom-model",
  "parameters": 25,
  "description": "Custom 25B parameter model"
}
```

To set a default rate for all unspecified models:

```json
{
  "tokens_per_second": 10
}
```

#### Get Configuration

Get configuration for all models:

```
GET /config
```

Get configuration for a specific model:

```
GET /config/{model_name}
```

#### Reload Configuration

Reload the configuration from `config.toml` without restarting the server:

```
POST /config/reload
```

## Parameter-Based Speed Estimation

The server automatically estimates token generation speed based on model parameters using the formula:

```
speed = base_speed * (1 / log(params + 1))^1.5
```

Where:
- `base_speed` is 25 tokens per second (theoretical maximum for tiny models)
- `params` is the number of parameters in billions
- The resulting speed is clamped between 1 and 20 tokens per second

This formula approximates the real-world behavior where larger models tend to generate tokens more slowly.

## Token Usage Calculation

The server provides OpenAI-compatible token usage information in responses:

- `prompt_tokens`: Estimated tokens in the input messages
- `completion_tokens`: Estimated tokens in the generated response
- `total_tokens`: Sum of prompt and completion tokens

This information is included in non-streaming responses and in the final chunk of streaming responses.

## Default Models

### Llama Series Models

| Model | Parameters (B) | Est. Tokens/sec |
|-------|---------------|----------------|
| llama-3-8b | 8B | ~8.5 |
| llama-3-70b | 70B | ~3.7 |
| codellama-13b | 13B | ~7.0 |
| codellama-34b | 34B | ~4.8 |
| deepseek-r1 | 10B | ~7.7 |

### Other Models

- `gpt-3.5-turbo`: 10 tokens/sec (approx. 20B parameters)
- `gpt-3.5-turbo-16k`: 10 tokens/sec (approx. 20B parameters)
- `gpt-4`: 5 tokens/sec (approx. 170B parameters)
- `gpt-4-turbo`: 7 tokens/sec (approx. 140B parameters) 
- `gpt-4-32k`: 5 tokens/sec (approx. 170B parameters)
- `claude-2`: 8 tokens/sec (approx. 100B parameters)
- `claude-instant`: 12 tokens/sec (approx. 60B parameters)

## Features

- Mimics OpenAI's streaming response behavior
- Parameter-based automatic token speed estimation
- Configurable token generation speed per model
- OpenAI-compatible model listing API
- OpenAI-compatible usage statistics
- Support for Llama model series
- Supports both streaming and non-streaming responses
- TOML configuration for easy customization
- Multiple response lengths for comprehensive testing
- Time limit enforcement for streaming responses

## Response Length Modes

The system now supports the following response length modes:

- `auto`: (Default) Automatically selects response length based on model speed and configuration
  - Configured in the `[auto_response_length]` section of `config.toml`
  - Default configuration:
    - Slow models (≤3 tokens/sec): short responses
    - Medium speed models (3-7 tokens/sec): medium responses
    - Fast models (>7 tokens/sec): long responses
- `short`: A brief response
- `medium`: A moderate-length response
- `long`: A detailed response
- `very_long`: An extensive response
- `random`: Randomly chooses from the available length options

Example request using the `auto` response length:
```json
{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true,
  "response_length": "auto"
}
```

## Duration-Based Responses

You can also specify an exact duration for responses:
```json
{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true,
  "duration_seconds": 10
}
```

This will generate a response of appropriate length to take approximately 10 seconds to stream.

