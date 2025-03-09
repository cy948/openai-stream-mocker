import tomli
from typing import Dict, Any
from app.models import ModelConfig
from app.utils import estimate_speed_from_parameters

def load_config(config_path='config.toml'):
    """Load configuration from TOML file"""
    try:
        with open(config_path, 'rb') as f:
            return tomli.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

# Global configuration variables
config = load_config()
MODEL_CONFIGS = {}
DEFAULT_CONFIG = None
SAMPLE_RESPONSES = {}
MAX_STREAM_TIME_SECONDS = 5
ENFORCE_TIME_LIMIT = True
TRUNCATION_MESSAGE = "... [Content truncated due to time limit]"

def init_config():
    """Initialize configuration from the loaded config file"""
    global MODEL_CONFIGS, DEFAULT_CONFIG, SAMPLE_RESPONSES
    global MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT, TRUNCATION_MESSAGE
    
    # Initialize model configurations from TOML
    if config and 'models' in config:
        for model_name, model_data in config['models'].items():
            MODEL_CONFIGS[model_name] = ModelConfig(
                tokens_per_second=model_data.get('tokens_per_second', 10),
                description=model_data.get('description', f"Model {model_name}"),
                parameters=model_data.get('parameters')
            )

    # Set default configuration
    default_tps = config.get('general', {}).get('default_tokens_per_second', 10)
    default_desc = config.get('general', {}).get('default_model_description', "Default configuration")
    DEFAULT_CONFIG = ModelConfig(tokens_per_second=default_tps, description=default_desc, parameters=0)

    # Time limit settings
    MAX_STREAM_TIME_SECONDS = config.get('general', {}).get('max_stream_time_seconds', 5)
    ENFORCE_TIME_LIMIT = config.get('general', {}).get('enforce_time_limit', True)
    TRUNCATION_MESSAGE = config.get('general', {}).get('truncation_message', "... [Content truncated due to time limit]")

    # Load sample responses from TOML
    if config and 'responses' in config:
        for length, response_data in config['responses'].items():
            SAMPLE_RESPONSES[length] = response_data.get('content', '')

    # Make sure we have at least one sample response
    if not SAMPLE_RESPONSES:
        SAMPLE_RESPONSES["medium"] = "This is a sample response from the OpenAI Stream Mocker."
    
    return {
        "models": MODEL_CONFIGS,
        "default": DEFAULT_CONFIG,
        "responses": SAMPLE_RESPONSES,
        "time_limit": MAX_STREAM_TIME_SECONDS,
        "enforce_limit": ENFORCE_TIME_LIMIT,
        "truncation_message": TRUNCATION_MESSAGE
    }

def reload_config():
    """Reload configuration from TOML file"""
    global config
    config = load_config()
    return init_config()
