"""Runtime information for the AI assistant foundation."""

import platform

APP_NAME: str = "ai-assistant"
APP_VERSION: str = "0.1.0"


def get_system_info() -> dict[str, str]:
    # Only non-sensitive, static values are exposed here; environment variables,
    # paths, usernames and hostnames must never be added to this payload.
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "python_version": platform.python_version(),
    }
