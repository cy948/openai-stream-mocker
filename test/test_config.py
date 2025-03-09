import pytest
import os
import tempfile
from app.config import load_config, init_config, reload_config
from app.models import ModelConfig

def test_load_config():
    """Test that the configuration loads correctly"""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.toml', delete=False) as tmp:
        tmp.write(b"""
[general]
default_tokens_per_second = 15
default_model_description = "Test configuration"
max_stream_time_seconds = 3
enforce_time_limit = true
truncation_message = "...truncated..."

[models.test-model]
tokens_per_second = 25
description = "Test model for config testing"
parameters = 12

[responses.test]
content = "This is a test response."
""")
        tmp_path = tmp.name

    try:
        # Load the config
        config = load_config(tmp_path)
        
        # Check that values are loaded correctly
        assert config["general"]["default_tokens_per_second"] == 15
        assert config["general"]["max_stream_time_seconds"] == 3
        assert config["models"]["test-model"]["tokens_per_second"] == 25
        assert config["responses"]["test"]["content"] == "This is a test response."
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_init_and_reload_config():
    """Test initializing and reloading configuration"""
    # This test relies on the actual config file, but we can verify it works properly
    
    # Start with a fresh configuration
    result = init_config()
    
    # Verify that the config contains expected keys
    assert "models" in result
    assert "default" in result
    assert "responses" in result
    assert "time_limit" in result
    
    # Verify that the default config was created
    assert isinstance(result["default"], ModelConfig)
    
    # Test reloading
    reload_result = reload_config()
    
    # Verify reload result
    assert "models" in reload_result
    assert "default" in reload_result
