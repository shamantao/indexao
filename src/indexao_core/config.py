from pydantic import BaseModel, Field
from typing import List, Optional
import toml
from pathlib import Path

class VolumeConfig(BaseModel):
    path: str
    scan_images: bool = False
    exclude: List[str] = []
    include_extensions: List[str] = [] # If empty, use defaults

class CoreConfig(BaseModel):
    cjk_threshold: float = 0.05
    # Do we generate sidecar for text-based files?
    sidecar_for_text_files: bool = False 

class MeiliConfig(BaseModel):
    url: str = "http://localhost:7700"
    api_key: str = "masterKey"

class LLMConfig(BaseModel):
    provider: str = "gemini"
    api_key: Optional[str] = None
    api_keys: List[str] = []
    # Using the latest stable alias which is confirmed working (v2.0 was hitting limit 0)
    model: str = "gemini-flash-latest" 
    rpm: int = 15
    daily_limit: int = 1500

class AppConfig(BaseModel):
    core: CoreConfig
    meilisearch: MeiliConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    volumes: List[VolumeConfig]

def load_config(config_path: str = "config.toml") -> AppConfig:
    if not Path(config_path).exists():
        # Return default config if no file
        return AppConfig(
            core=CoreConfig(),
            meilisearch=MeiliConfig(),
            volumes=[]
        )
    
    with open(config_path, "r") as f:
        data = toml.load(f)
    
    return AppConfig(**data)
