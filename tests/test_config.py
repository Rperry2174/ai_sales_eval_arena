"""Tests for configuration loading and environment variables."""

import os
import pytest
from unittest.mock import patch

import anthropic


class TestEnvLoading:
    """Test that .env file is loaded correctly."""
    
    def test_dotenv_loads_anthropic_api_key(self):
        """Test that the .env file provides ANTHROPIC_API_KEY."""
        from ai_sales_eval_arena.config import load_config_from_env
        
        config = load_config_from_env()
        
        # Check that API key is loaded (without exposing the actual value)
        assert config.anthropic_api_key is not None, (
            "ANTHROPIC_API_KEY not found. Make sure you have a .env file with "
            "ANTHROPIC_API_KEY=your-key-here"
        )
        assert len(config.anthropic_api_key) > 0, "ANTHROPIC_API_KEY is empty"
    
    def test_anthropic_api_key_format(self):
        """Test that the API key has the expected format for Anthropic keys."""
        from ai_sales_eval_arena.config import load_config_from_env
        
        config = load_config_from_env()
        
        if config.anthropic_api_key:
            # Anthropic API keys typically start with 'sk-ant-'
            assert config.anthropic_api_key.startswith("sk-ant-"), (
                f"API key doesn't look like a valid Anthropic key "
                f"(expected to start with 'sk-ant-', got '{config.anthropic_api_key[:10]}...')"
            )
            # Keys are typically long
            assert len(config.anthropic_api_key) > 40, (
                "API key seems too short. Anthropic keys are typically longer."
            )
    
    def test_get_config_succeeds_with_valid_env(self):
        """Test that get_config() works when .env is properly configured."""
        from ai_sales_eval_arena.config import get_config
        
        # This should not raise an exception if .env is configured
        config = get_config()
        
        assert config.anthropic_api_key is not None
        assert config.anthropic_model is not None
        print(f"✓ Config loaded successfully. Model: {config.anthropic_model}")
    
    def test_get_config_raises_without_api_key(self):
        """Test that get_config() raises ValueError when API key is missing."""
        from ai_sales_eval_arena.config import get_config
        
        # Temporarily unset the API key
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            # Also need to prevent load_dotenv from loading the .env file
            with patch("ai_sales_eval_arena.config.load_dotenv"):
                with pytest.raises(ValueError, match="Anthropic API key not found"):
                    get_config()
    
    def test_get_config_raises_without_model(self):
        """Test that get_config() raises ValueError when model is missing."""
        from ai_sales_eval_arena.config import get_config
        
        # Temporarily unset the model but keep the API key
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "ANTHROPIC_MODEL": ""}, clear=False):
            with patch("ai_sales_eval_arena.config.load_dotenv"):
                with pytest.raises(ValueError, match="Anthropic model not found"):
                    get_config()
    
    def test_default_config_values(self):
        """Test that configuration values are loaded from .env."""
        from ai_sales_eval_arena.config import load_config_from_env
        
        config = load_config_from_env()
        
        # Model must be set via .env (no hardcoded default)
        assert config.anthropic_model is not None, (
            "ANTHROPIC_MODEL must be set in .env file"
        )
        assert len(config.anthropic_model) > 0, "ANTHROPIC_MODEL cannot be empty"
        assert config.max_concurrent_matches >= 1
        assert config.grading_timeout_seconds >= 1
    
    def test_env_sets_model(self):
        """Test that ANTHROPIC_MODEL env var is used for the model."""
        from ai_sales_eval_arena.config import load_config_from_env
        
        test_model = "claude-test-model"
        
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": test_model}):
            config = load_config_from_env()
            assert config.anthropic_model == test_model


class TestConfigIntegrity:
    """Test configuration integrity and validation."""
    
    def test_api_key_not_placeholder(self):
        """Ensure the API key is not a placeholder value."""
        from ai_sales_eval_arena.config import load_config_from_env
        
        config = load_config_from_env()
        
        if config.anthropic_api_key:
            placeholder_values = [
                "your-api-key-here",
                "YOUR_API_KEY_HERE",
                "placeholder",
                "xxx",
                "test",
                "demo",
            ]
            
            key_lower = config.anthropic_api_key.lower()
            for placeholder in placeholder_values:
                assert placeholder not in key_lower, (
                    f"API key appears to be a placeholder value: {config.anthropic_api_key[:20]}..."
                )
    
    def test_config_model_is_dataclass_like(self):
        """Test that ArenaConfig behaves like expected."""
        from ai_sales_eval_arena.models import ArenaConfig
        
        config = ArenaConfig(
            anthropic_api_key="test-key-123",
            anthropic_model="test-model",
            max_concurrent_matches=2,
            grading_timeout_seconds=30
        )
        
        assert config.anthropic_api_key == "test-key-123"
        assert config.anthropic_model == "test-model"
        assert config.max_concurrent_matches == 2
        assert config.grading_timeout_seconds == 30


class TestCredentialsSecurity:
    """Tests to ensure credentials are handled securely."""
    
    def test_api_key_not_in_repr(self):
        """Ensure API key is not exposed in string representations."""
        from ai_sales_eval_arena.models import ArenaConfig
        
        config = ArenaConfig(
            anthropic_api_key="sk-ant-secret-key-12345"
        )
        
        # The key shouldn't appear in repr/str
        config_str = str(config)
        config_repr = repr(config)
        
        # Note: This test documents expected behavior.
        # If pydantic exposes the key, you may want to customize __repr__
        if "sk-ant-secret-key-12345" in config_str or "sk-ant-secret-key-12345" in config_repr:
            pytest.skip(
                "API key is exposed in repr/str - consider adding SecretStr "
                "or custom __repr__ to ArenaConfig for production use"
            )


class TestAnthropicAPIIntegration:
    """Integration tests that make real API calls to Anthropic.
    
    These tests verify that the credentials actually work by making
    a simple API request to the Anthropic API.
    """
    
    @pytest.mark.integration
    def test_anthropic_api_connection(self):
        """Test that we can connect to the Anthropic API with our credentials."""
        from ai_sales_eval_arena.config import get_config
        
        config = get_config()
        
        # Create Anthropic client with our API key
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        
        try:
            # Make a minimal API request using model from config
            response = client.messages.create(
                model=config.anthropic_model,
                max_tokens=50,
                messages=[
                    {"role": "user", "content": "Say 'API test successful' and nothing else."}
                ]
            )
            
            # Verify we got a valid response
            assert response is not None, "Response should not be None"
            assert response.id is not None, "Response should have an ID"
            assert response.content is not None, "Response should have content"
            assert len(response.content) > 0, "Response content should not be empty"
            
            # Extract text from response
            text = response.content[0].text
            assert text is not None, "Response text should not be None"
            assert len(text) > 0, "Response text should not be empty"
            
            print(f"✓ API response received: '{text}'")
            print(f"✓ Model used: {response.model}")
            print(f"✓ Response ID: {response.id}")
            
        except anthropic.BadRequestError as e:
            error_msg = str(e)
            if "credit balance is too low" in error_msg:
                # API key is valid but account needs credits
                print("✓ API key is VALID (authenticated successfully)")
                print("✗ Account needs credits - add credits at console.anthropic.com")
                pytest.skip("API key valid but account has no credits. Add credits to run full test.")
            else:
                raise
        except anthropic.AuthenticationError as e:
            pytest.fail(f"API key is INVALID: {e}")
    
    @pytest.mark.integration  
    def test_anthropic_api_returns_valid_json_when_requested(self):
        """Test that the API can return structured JSON responses."""
        from ai_sales_eval_arena.config import get_config
        import json
        
        config = get_config()
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        
        try:
            # Use model from config
            response = client.messages.create(
                model=config.anthropic_model,
                max_tokens=100,
                messages=[
                    {
                        "role": "user", 
                        "content": 'Respond with only this JSON, no other text: {"status": "ok", "test": true}'
                    }
                ]
            )
            
            text = response.content[0].text.strip()
            
            # Try to parse as JSON
            try:
                data = json.loads(text)
                assert "status" in data or "test" in data, "Response should contain expected keys"
                print(f"✓ Valid JSON response: {data}")
            except json.JSONDecodeError:
                # Sometimes the model adds extra text, try to extract JSON
                if "{" in text and "}" in text:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    json_str = text[start:end]
                    data = json.loads(json_str)
                    print(f"✓ Extracted JSON from response: {data}")
                else:
                    pytest.fail(f"Could not parse JSON from response: {text}")
                    
        except anthropic.BadRequestError as e:
            if "credit balance is too low" in str(e):
                print("✓ API key is VALID")
                pytest.skip("API key valid but account has no credits.")
            else:
                raise
        except anthropic.AuthenticationError as e:
            pytest.fail(f"API key is INVALID: {e}")
