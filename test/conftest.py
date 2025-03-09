import pytest
import sys
import os
import asyncio

# Add the project root to Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Message, ModelConfig
from app.config import init_config

@pytest.fixture(scope="session", autouse=True)
def initialize_config():
    """Initialize the app configuration for testing"""
    init_config()

@pytest.fixture
def sample_message():
    """Return a simple test message"""
    return Message(role="user", content="Test message")

@pytest.fixture
def sample_messages():
    """Return a list of sample messages"""
    return [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Tell me a story about a robot.")
    ]

@pytest.fixture
def fast_model_config():
    """Return a model config for a fast model"""
    return ModelConfig(
        tokens_per_second=50,
        description="Fast test model",
        parameters=5
    )

@pytest.fixture
def slow_model_config():
    """Return a model config for a slow model"""
    return ModelConfig(
        tokens_per_second=5,
        description="Slow test model",
        parameters=100
    )

@pytest.fixture
def medium_model_config():
    """Return a model config for a medium speed model"""
    return ModelConfig(
        tokens_per_second=20,
        description="Medium test model",
        parameters=20
    )

@pytest.fixture
def short_text():
    """Return a short text for testing"""
    return "This is a short test message for streaming."

@pytest.fixture
def medium_text():
    """Return a medium-length text for testing"""
    return """This is a medium-length test message for streaming.
    It contains multiple sentences and should produce several chunks 
    when processed by the streaming function. The goal is to test
    the token generation speed accurately."""

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
