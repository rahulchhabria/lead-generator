"""Tests for Pydantic data models."""

import pytest
from src.models import (
    Account,
    CampaignConfig,
    Contact,
    DomainEntry,
    DomainList,
    DraftEmail,
    ICPDefinition,
    LeadStatus,
    PersonalizationDossier,
    PipelineStage,
)


class TestICPDefinition:
    def test_minimal_icp(self):
        icp = ICPDefinition(description="SaaS companies in the US")
        assert icp.description == "SaaS companies in the US"
        assert icp.max_leads == 50
        assert icp.target_roles == []
        assert icp.exclusions == []

    def test_full_icp(self):
        icp = ICPDefinition(
            description="Developer tools companies",
            target_roles=["CTO", "VP Engineering"],
            company_size="50-500",
            industries=["SaaS", "DevTools"],
            geographies=["US", "EU"],
            technologies=["Python"],
            exclusions=["google.com"],
            max_leads=25,
        )
        assert len(icp.target_roles) == 2
        assert icp.max_leads == 25
        assert "google.com" in icp.exclusions

    def test_max_leads_validation(self):
        with pytest.raises(Exception):
            ICPDefinition(description="test", max_leads=0)
        with pytest.raises(Exception):
            ICPDefinition(description="test", max_leads=501)


class TestDomainList:
    def test_domain_list(self):
        dl = DomainList(
            target_roles=["CTO"],
            domains=[
                DomainEntry(domain="acme.io", company_name="Acme"),
                DomainEntry(domain="beta.com"),
            ],
        )
        assert len(dl.domains) == 2
        assert dl.domains[0].company_name == "Acme"
        assert dl.domains[1].company_name is None


class TestAccount:
    def test_default_values(self):
        account = Account(company_name="Acme", domain="acme.io")
        assert account.status == LeadStatus.DISCOVERED
        assert account.source == "discovered"
        assert account.data_sources == []

    def test_provided_source(self):
        account = Account(company_name="Acme", domain="acme.io", source="provided")
        assert account.source == "provided"


class TestContact:
    def test_auto_full_name(self):
        contact = Contact(first_name="Jane", last_name="Doe")
        assert contact.full_name == "Jane Doe"

    def test_explicit_full_name(self):
        contact = Contact(first_name="Jane", last_name="Doe", full_name="Dr. Jane Doe")
        assert contact.full_name == "Dr. Jane Doe"

    def test_default_status(self):
        contact = Contact(first_name="Jane", last_name="Doe")
        assert contact.status == LeadStatus.CONTACT_FOUND

    def test_email_confidence_bounds(self):
        contact = Contact(first_name="Jane", last_name="Doe", email_confidence=85)
        assert contact.email_confidence == 85

        with pytest.raises(Exception):
            Contact(first_name="Jane", last_name="Doe", email_confidence=101)


class TestPersonalizationDossier:
    def test_empty_dossier(self):
        dossier = PersonalizationDossier()
        assert dossier.github_username is None
        assert dossier.github_repos == []
        assert dossier.interests == []

    def test_populated_dossier(self):
        dossier = PersonalizationDossier(
            github_username="janedoe",
            github_repos=["awesome-cli"],
            github_languages=["Python", "Go"],
            interests=["distributed systems"],
        )
        assert dossier.github_username == "janedoe"
        assert len(dossier.github_repos) == 1


class TestDraftEmail:
    def test_default_values(self):
        email = DraftEmail(subject_line="Hello", body="Body text")
        assert email.status == LeadStatus.EMAIL_DRAFTED
        assert email.tone == "casual"
        assert email.includes_unsubscribe is True

    def test_personalization_hooks(self):
        email = DraftEmail(
            subject_line="Hello",
            body="Body text",
            personalization_hooks=["github project", "blog post"],
        )
        assert len(email.personalization_hooks) == 2


class TestCampaignConfig:
    def test_defaults(self):
        config = CampaignConfig()
        assert config.tone == "casual"
        assert config.max_words == 150
        assert config.daily_send_limit == 100

    def test_serialization_roundtrip(self):
        config = CampaignConfig(sender_name="Test User", tone="professional")
        json_str = config.model_dump_json()
        loaded = CampaignConfig.model_validate_json(json_str)
        assert loaded.sender_name == "Test User"
        assert loaded.tone == "professional"


class TestPipelineStage:
    def test_stage_values(self):
        assert PipelineStage.DISCOVERY.value == "discovery"
        assert PipelineStage.COMPLETED.value == "completed"
