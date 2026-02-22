"""Configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.models import CampaignConfig, DomainEntry, DomainList, ICPDefinition


@dataclass
class APIConfig:
    """Tracks which APIs are available based on .env keys."""

    anthropic_api_key: str = ""
    serper_api_key: str = ""
    hunter_api_key: str = ""
    github_token: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    db_path: str = "data/pipeline.db"

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key) and self.anthropic_api_key != "sk-ant-placeholder"

    @property
    def has_serper(self) -> bool:
        return bool(self.serper_api_key)

    @property
    def has_hunter(self) -> bool:
        return bool(self.hunter_api_key)

    @property
    def has_github(self) -> bool:
        return bool(self.github_token)

    def api_status_line(self) -> dict[str, str]:
        """Return status for each API for display."""
        return {
            "Claude": "active" if self.has_anthropic else "missing (REQUIRED)",
            "Web Search": "Serper" if self.has_serper else "DuckDuckGo (free)",
            "Email": "Hunter.io" if self.has_hunter else "Patterns + DNS (free)",
            "GitHub": "Authenticated" if self.has_github else "Unauthenticated (limited)",
        }


def load_api_config(env_path: str | None = None) -> APIConfig:
    """Load API configuration from .env file."""
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    return APIConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        serper_api_key=os.getenv("SERPER_API_KEY", ""),
        hunter_api_key=os.getenv("HUNTER_API_KEY", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        db_path=os.getenv("DB_PATH", "data/pipeline.db"),
    )


def load_icp(path: str) -> ICPDefinition:
    """Load an ICP definition from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    icp_data = data.get("icp", data)
    return ICPDefinition(**icp_data)


def load_domains(path: str) -> DomainList:
    """Load a domain list from YAML or CSV file."""
    p = Path(path)

    if p.suffix in (".yaml", ".yml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        domains_data = data.get("domains", [])
        target_roles = data.get("target_roles", [])
        entries = [DomainEntry(**d) if isinstance(d, dict) else DomainEntry(domain=d) for d in domains_data]
        return DomainList(target_roles=target_roles, domains=entries)

    elif p.suffix == ".csv":
        import csv

        entries = []
        target_roles = []
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(
                    DomainEntry(
                        domain=row.get("domain", "").strip(),
                        company_name=row.get("company_name", "").strip() or None,
                        notes=row.get("notes", "").strip() or None,
                    )
                )
        return DomainList(target_roles=target_roles, domains=entries)

    else:
        raise ValueError(f"Unsupported domain list format: {p.suffix}. Use .yaml or .csv")


def load_campaign_config(path: str) -> CampaignConfig:
    """Load campaign configuration from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    campaign_data = {}
    if "campaign" in data:
        campaign_data.update(data["campaign"])
    if "email" in data:
        campaign_data.update(data["email"])
    if "pipeline" in data:
        campaign_data.update(data["pipeline"])

    return CampaignConfig(**{k: v for k, v in campaign_data.items() if v is not None})
