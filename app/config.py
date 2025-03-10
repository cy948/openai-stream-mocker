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
# Set defaults that will be used if not overridden by config file
MAX_STREAM_TIME_SECONDS = 60
ENFORCE_TIME_LIMIT = False
TRUNCATION_MESSAGE = "\n\nI've reached the response time limit, but I hope this information helps. Let me know if you need more details."
DEFAULT_RESPONSE_MODE = "auto"  # Use auto by default to adapt to model speed

# Response length settings for auto mode
AUTO_RESPONSE_LENGTH_CONFIG = {
    "slow": {"max_tokens_per_second": 3.0, "response_length": "short"},
    "medium": {"max_tokens_per_second": 37.0, "response_length": "medium"},
    "long": {"max_tokens_per_second": 77.0, "response_length": "long"},
    "fast": {"max_tokens_per_second": float('inf'), "response_length": "very_long"}
}

def init_config():
    """Initialize configuration from the loaded config file"""
    global MODEL_CONFIGS, DEFAULT_CONFIG, SAMPLE_RESPONSES
    global MAX_STREAM_TIME_SECONDS, ENFORCE_TIME_LIMIT, TRUNCATION_MESSAGE, DEFAULT_RESPONSE_MODE
    global AUTO_RESPONSE_LENGTH_CONFIG
    
    # Initialize model configurations from TOML
    if config and 'models' in config:
        for model_name, model_data in config['models'].items():
            MODEL_CONFIGS[model_name] = ModelConfig(
                tokens_per_second=model_data.get('tokens_per_second', 10),
                description=model_data.get('description', f"Model {model_name}"),
                parameters=model_data.get('parameters'),
                max_stream_time_seconds=model_data.get('max_stream_time_seconds')
            )

    # Set default configuration
    default_tps = config.get('general', {}).get('default_tokens_per_second', 10)
    default_desc = config.get('general', {}).get('default_model_description', "Default configuration")
    DEFAULT_CONFIG = ModelConfig(tokens_per_second=default_tps, description=default_desc, parameters=0)

    # Time limit settings - use our defaults if not in config
    MAX_STREAM_TIME_SECONDS = config.get('general', {}).get('max_stream_time_seconds', MAX_STREAM_TIME_SECONDS)
    ENFORCE_TIME_LIMIT = config.get('general', {}).get('enforce_time_limit', ENFORCE_TIME_LIMIT)
    TRUNCATION_MESSAGE = config.get('general', {}).get('truncation_message', TRUNCATION_MESSAGE)
    
    # Print the actual time limit settings that are being used
    print(f"Configured MAX_STREAM_TIME_SECONDS: {MAX_STREAM_TIME_SECONDS}")
    print(f"Configured ENFORCE_TIME_LIMIT: {ENFORCE_TIME_LIMIT}")
    
    # Default response mode setting
    DEFAULT_RESPONSE_MODE = config.get('general', {}).get('default_response_mode', "auto")
    
    # Auto response length configuration
    auto_config = config.get('auto_response_length', {})
    if auto_config:
        for speed_category, settings in auto_config.items():
            if speed_category in AUTO_RESPONSE_LENGTH_CONFIG and isinstance(settings, dict):
                if 'max_tokens_per_second' in settings:
                    AUTO_RESPONSE_LENGTH_CONFIG[speed_category]['max_tokens_per_second'] = float(settings['max_tokens_per_second'])
                if 'response_length' in settings:
                    AUTO_RESPONSE_LENGTH_CONFIG[speed_category]['response_length'] = settings['response_length']

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
        "truncation_message": TRUNCATION_MESSAGE,
        "auto_response_length": AUTO_RESPONSE_LENGTH_CONFIG
    }

def reload_config():
    """Reload configuration from TOML file"""
    global config
    config = load_config()
    return init_config()

def get_auto_response_length(tokens_per_second):
    """Determine response length based on model speed using configuration"""
    # Sort speed categories from slowest to fastest
    sorted_categories = sorted(
        AUTO_RESPONSE_LENGTH_CONFIG.items(), 
        key=lambda x: x[1]['max_tokens_per_second'],
        reverse=True,
    )
    
    # Find the appropriate category based on tokens_per_second
    for category, config in sorted_categories:
        if tokens_per_second >= config['max_tokens_per_second']:
            return config['response_length']
            
    # Default to medium if no match (should not happen with infinity as max)
    return "medium"
