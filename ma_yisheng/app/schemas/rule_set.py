"""Rule set request/response schemas."""
from pydantic import BaseModel, field_validator
from typing import Optional, List


class RuleSetCreate(BaseModel):
    name: str
    description: str = ""
    lang: str = "python"
    scene: str = "full"

    @field_validator("lang")
    @classmethod
    def lang_must_be_supported(cls, v):
        if v not in ("python", "java", "go", "js", "php", "c"):
            raise ValueError(f"Unsupported language: {v}")
        return v

    @field_validator("scene")
    @classmethod
    def scene_must_be_valid(cls, v):
        if v not in ("minimal", "full"):
            raise ValueError(f"Invalid scene: {v}")
        return v


class RuleSetCloneOfficial(BaseModel):
    lang: str = "python"
    scene: str = "full"


class RuleToggle(BaseModel):
    rule_id: int
    is_enabled: bool


class CVESearchRequest(BaseModel):
    language: str = "python"
    vuln_type: str = ""
    count: int = 10
    source: str = "github"  # github | nvd
    keyword: str = ""


class CVEIngestRequest(BaseModel):
    ghsa_ids: List[str]  # selected advisories to ingest
    rule_set_id: int     # target rule set
    provider: str = "deepseek"
    model: Optional[str] = None
