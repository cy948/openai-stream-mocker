import time
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.models import CompletionRequest, ModelConfig
from app.services import stream_response, get_response_content, get_response_content_for_duration
from app.utils import calculate_usage, estimate_speed_from_parameters
from app.config import MODEL_CONFIGS, DEFAULT_CONFIG, SAMPLE_RESPONSES, reload_config

router = APIRouter()

# Function to add CORS middleware to the app
def add_cors_middleware(app):
    """Add CORS middleware to the application"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

# Function to add CORS headers to all responses
def add_cors_headers_middleware(app):
    """Add middleware to add CORS headers to all responses"""
    @app.middleware("http")
    async def add_cors_headers(request, call_next):
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return response

# Add a dependency to ensure configuration is loaded
async def ensure_config_loaded():
    """Ensure configuration is loaded before handling requests"""
    if not MODEL_CONFIGS:
        try:
            reload_config()
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to initialize configuration: {str(e)}"
            )

# Add a dependency to handle API key validation but always pass
async def ignore_api_key(authorization: str = Header(None)):
    """Accept any API key or no API key at all"""
    # This function always passes, effectively removing API key restrictions
    return True

@router.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str):
    # Handle OPTIONS requests for CORS preflight
    response = JSONResponse(content={})
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return response

@router.get("/", dependencies=[Depends(ensure_config_loaded), Depends(ignore_api_key)])
def read_root():
    return {"message": "OpenAI Stream Mocker", "version": "1.0.0"}

@router.options("/v1/chat/completions")
def get_options():
    response = JSONResponse(content={})
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return response

@router.post("/v1/chat/completions", dependencies=[Depends(ensure_config_loaded), Depends(ignore_api_key)])
async def create_chat_completion(request: CompletionRequest):
    # Check if model exists
    model = request.model
    if model not in MODEL_CONFIGS and ":" not in model:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "message": f"Model '{model}' does not exist",
                    "type": "invalid_request_error",
                    "code": "model_not_found"
                }
            }
        )
    
    # Get model configuration
    model_config = MODEL_CONFIGS.get(model, DEFAULT_CONFIG)
    
    # Get response content based on requested length, duration, or model speed
    if request.duration_seconds is not None:
        # Pass the model's tokens_per_second to ensure correct content length for duration
        response_content = get_response_content_for_duration(
            request.duration_seconds, 
            model,
            tokens_per_second=model_config.tokens_per_second
        )
    elif request.response_length == "auto":
        # Use model's speed to determine appropriate response length from configuration
        from app.config import get_auto_response_length
        auto_length = get_auto_response_length(model_config.tokens_per_second)
        response_content = get_response_content(auto_length)
    else:
        response_content = get_response_content(request.response_length)

    # Calculate usage statistics
    usage = calculate_usage(request.messages, response_content)

    if not request.stream:
        # Non-streaming response
        return {
            "id": f"mock-completion-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": response_content,
                },
                "finish_reason": "stop",
                "index": 0
            }],
            "usage": usage
        }
    else:
        # Streaming response
        return StreamingResponse(
            stream_response(response_content, model, request.messages),
            media_type="text/event-stream"
        )

@router.get("/v1/models", dependencies=[Depends(ensure_config_loaded), Depends(ignore_api_key)])
def list_models():
    """Return a list of available models in OpenAI-compatible format"""
    models_list = []
    for model_id, config in MODEL_CONFIGS.items():
        models_list.append({
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "openai-stream-mocker",
            "permission": [{
                "id": f"modelperm-{model_id}",
                "object": "model_permission",
                "created": int(time.time()),
                "organization": "*",
                "group": None,
                "is_blocking": False,
                "allow_create_engine": False,
                "allow_sampling": True,
                "allow_logprobs": True,
                "allow_search_indices": False,
                "allow_view": True,
                "allow_fine_tuning": False,
                "allowed_to_use": True,
            }],
            "root": model_id,
            "parent": None,
            "description": config.description
        })
    
    # Return in the format expected by OpenAI clients
    return {
        "object": "list",
        "data": models_list
    }

@router.post("/config", dependencies=[Depends(ignore_api_key)])
async def update_config(request: Request):
    data = await request.json()
    
    # Update specific model config
    if "model" in data and "tokens_per_second" in data:
        model = data["model"]
        tokens_per_second = float(data["tokens_per_second"])
        
        if model in MODEL_CONFIGS:
            MODEL_CONFIGS[model].tokens_per_second = tokens_per_second
            return {"message": f"Tokens per second for model {model} updated to {tokens_per_second}"}
        else:
            # Add new model
            description = data.get("description", f"Custom model {model}")
            parameters = data.get("parameters", 0)
            MODEL_CONFIGS[model] = ModelConfig(
                tokens_per_second=tokens_per_second, 
                description=description,
                parameters=parameters
            )
            return {"message": f"Added new model {model} with {tokens_per_second} tokens per second"}
    
    # Update model with parameter-based speed estimation
    elif "model" in data and "parameters" in data:
        model = data["model"]
        parameters = float(data["parameters"])
        
        if model in MODEL_CONFIGS:
            MODEL_CONFIGS[model].parameters = parameters
            new_speed = estimate_speed_from_parameters(parameters)
            MODEL_CONFIGS[model].tokens_per_second = new_speed
            return {
                "message": f"Updated {model} with {parameters}B parameters, estimated speed: {new_speed:.2f} tokens/sec"
            }
        else:
            # Add new model based on parameters
            description = data.get("description", f"Model with {parameters}B parameters")
            new_speed = estimate_speed_from_parameters(parameters)
            MODEL_CONFIGS[model] = ModelConfig(
                tokens_per_second=new_speed,
                description=description,
                parameters=parameters
            )
            return {
                "message": f"Added model {model} with {parameters}B parameters, estimated speed: {new_speed:.2f} tokens/sec"
            }
    
    # Update default config
    elif "tokens_per_second" in data:
        tokens_per_second = float(data["tokens_per_second"])
        DEFAULT_CONFIG.tokens_per_second = tokens_per_second
        return {"message": f"Default tokens per second updated to {tokens_per_second}"}
        
    return {"message": "No changes made"}

@router.get("/config", dependencies=[Depends(ignore_api_key)])
def get_config():
    """Get current configuration for all models"""
    config_data = {
        "default": DEFAULT_CONFIG.dict(),
        "models": {model: config.dict() for model, config in MODEL_CONFIGS.items()}
    }
    return config_data

@router.get("/config/{model}", dependencies=[Depends(ignore_api_key)])
def get_model_config(model: str):
    """Get configuration for a specific model"""
    if model in MODEL_CONFIGS:
        return MODEL_CONFIGS[model].dict()
    elif model == "default":
        return DEFAULT_CONFIG.dict()
    else:
        raise HTTPException(status_code=404, detail=f"Model {model} not found")

@router.get("/responses", dependencies=[Depends(ignore_api_key)])
def list_response_options():
    """Get available response length options and preview"""
    response_options = {}
    for length, content in SAMPLE_RESPONSES.items():
        token_count = estimate_token_count(content)
        preview = content[:50] + "..." if len(content) > 50 else content
        response_options[length] = {
            "token_estimate": token_count,
            "preview": preview
        }
    
    # Add information about duration-based responses
    response_options["duration"] = {
        "description": "You can specify a duration in seconds with the 'duration_seconds' parameter",
        "example": "Send a request with {'duration_seconds': 10} for a 10-second response"
    }
    
    return response_options

@router.post("/config/reload", dependencies=[Depends(ignore_api_key)])
def reload_configuration():
    """Reload configuration from TOML file"""
    new_config = reload_config()
    return {"message": "Configuration reloaded successfully"}

def estimate_token_count(text: str) -> int:
    """Estimate token count for a given text"""
    # Simple approximation: ~4 characters per token
    return len(text) // 4

@router.post("/config/time-limit", dependencies=[Depends(ignore_api_key)])
async def update_time_limit(request: Request):
    """Update time limit settings"""
    data = await request.json()
    
    global MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT
    
    if "max_seconds" in data:
        from app.config import MAX_STREAM_TIME_SECONDS
        old_value = MAX_STREAM_TIME_SECONDS
        MAX_STREAM_TIME_SECONDS = int(data["max_seconds"])
        return {
            "message": f"Time limit updated from {old_value} to {MAX_STREAM_TIME_SECONDS} seconds",
            "enforce": ENFORCE_TIME_LIMIT
        }
        
    if "enforce" in data:
        from app.config import ENFORCE_TIME_LIMIT
        old_value = ENFORCE_TIME_LIMIT
        ENFORCE_TIME_LIMIT = bool(data["enforce"])
        return {
            "message": f"Time limit enforcement changed from {old_value} to {ENFORCE_TIME_LIMIT}",
            "limit_seconds": MAX_STREAM_TIME_SECONDS
        }
    
    # Return current settings if no changes
    return {
        "max_seconds": MAX_STREAM_TIME_SECONDS,
        "enforce": ENFORCE_TIME_LIMIT
    }

@router.post("/config/time-control", dependencies=[Depends(ignore_api_key)])
async def set_time_control(request: Request):
    """Fine-grained control of time limit settings"""
    data = await request.json()
    
    # For global settings
    from app.config import MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT
    updates = {}
    
    if "enforce" in data:
        old_value = ENFORCE_TIME_LIMIT
        ENFORCE_TIME_LIMIT = bool(data["enforce"])
        updates["enforce"] = f"Changed from {old_value} to {ENFORCE_TIME_LIMIT}"
        
    if "global_seconds" in data:
        old_value = MAX_STREAM_TIME_SECONDS
        MAX_STREAM_TIME_SECONDS = int(data["global_seconds"])
        updates["global_seconds"] = f"Changed from {old_value} to {MAX_STREAM_TIME_SECONDS}"
    
    # For model-specific settings
    if "model_settings" in data and isinstance(data["model_settings"], dict):
        model_settings = data["model_settings"]
        for model_id, seconds in model_settings.items():
            if model_id in MODEL_CONFIGS:
                old_value = getattr(MODEL_CONFIGS[model_id], "max_stream_time_seconds", None)
                MODEL_CONFIGS[model_id].max_stream_time_seconds = int(seconds)
                updates[f"model_{model_id}"] = f"Changed from {old_value} to {seconds} seconds"
    
    if not updates:
        # Return current settings
        model_settings = {
            model: getattr(config, "max_stream_time_seconds", MAX_STREAM_TIME_SECONDS) 
            for model, config in MODEL_CONFIGS.items()
        }
        return {
            "enforce_time_limit": ENFORCE_TIME_LIMIT,
            "global_seconds": MAX_STREAM_TIME_SECONDS,
            "model_settings": model_settings
        }
    
    return {
        "message": "Time control settings updated",
        "updates": updates,
        "current": {
            "enforce": ENFORCE_TIME_LIMIT,
            "global_seconds": MAX_STREAM_TIME_SECONDS
        }
    }

@router.get("/debug/settings", dependencies=[Depends(ignore_api_key)])
def get_debug_settings():
    """Get current debug settings including time limits"""
    from app.config import MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT, MODEL_CONFIGS, DEFAULT_CONFIG
    
    return {
        "time_limit_seconds": MAX_STREAM_TIME_SECONDS,
        "enforce_time_limit": ENFORCE_TIME_LIMIT,
        "default_tokens_per_second": DEFAULT_CONFIG.tokens_per_second,
        "model_count": len(MODEL_CONFIGS),
        "models": {model: config.tokens_per_second for model, config in MODEL_CONFIGS.items()}
    }
