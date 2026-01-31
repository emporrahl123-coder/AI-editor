"""
Configuration module for GitHub AI Editor
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class GitHubConfig:
    """GitHub API configuration"""
    token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    api_url: str = field(default_factory=lambda: os.getenv("GITHUB_API_URL", "https://api.github.com"))

@dataclass
class OpenAIConfig:
    """OpenAI API configuration"""
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4"))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("OPENAI_MAX_TOKENS", "4000")))
    temperature: float = field(default_factory=lambda: float(os.getenv("OPENAI_TEMPERATURE", "0.1")))

@dataclass
class Config:
    """Main configuration class"""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)

# Create global config instance
config = Config()
