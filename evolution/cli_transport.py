"""Fixed child-only OpenAI HTTP transport for prospective matched campaigns.

These settings suppress ordinary request/stream/connection retries. They do
not constrain authentication recovery, successful tool-turn sampling, or
establish billing coverage for a failed partial response. No host config or
authentication material is accessed here.
"""
import json


def profile_configuration():
    """Return independent copies; callers cannot choose an endpoint or retries."""
    return {
        "model_provider": "upg_openai_http",
        "model_provider_profile": {
            "name": "OpenAI", "wire_api": "responses",
            "requires_openai_auth": True, "supports_websockets": False,
            "request_max_retries": 0, "stream_max_retries": 0},
        "transport_features": {"unbounded_connection_retries": False}}


def profile_overrides():
    """Generate the identical TOML overrides consumed by both experiment arms."""
    config = profile_configuration()
    provider = config["model_provider"]
    values = ["model_provider=" + json.dumps(provider)]
    values.extend("model_providers." + provider + "." + key + "=" + json.dumps(value)
                  for key, value in config["model_provider_profile"].items())
    values.extend("features." + key + "=" + json.dumps(value)
                  for key, value in config["transport_features"].items())
    return values
