"""Tests for agent response parsing and orchestration."""



from src.models import Account, CampaignConfig, Contact, ICPDefinition
from tests.fixtures.mock_responses import (
    ACCOUNT_DISCOVERY_RESPONSE,
    CONTACT_EMAIL_RESPONSE,
    EMAIL_COMPOSER_RESPONSE,
    RESEARCH_RESPONSE,
)


class TestAccountDiscoveryParsing:
    def test_parse_valid_response(self):
        from src.agents.account_discovery import parse_accounts

        icp = ICPDefinition(description="test", exclusions=["excluded.com"])
        accounts = parse_accounts(ACCOUNT_DISCOVERY_RESPONSE, icp)

        assert len(accounts) == 2
        assert accounts[0].company_name == "Acme Corp"
        assert accounts[0].domain == "acme.io"
        assert accounts[0].industry == "Developer Tools"
        assert accounts[0].source == "discovered"

    def test_parse_with_exclusions(self):
        from src.agents.account_discovery import parse_accounts

        icp = ICPDefinition(description="test", exclusions=["acme.io"])
        accounts = parse_accounts(ACCOUNT_DISCOVERY_RESPONSE, icp)

        assert len(accounts) == 1
        assert accounts[0].domain == "beta.com"

    def test_parse_markdown_fenced(self):
        from src.agents.account_discovery import parse_accounts

        icp = ICPDefinition(description="test")
        fenced = f"```json\n{ACCOUNT_DISCOVERY_RESPONSE}\n```"
        accounts = parse_accounts(fenced, icp)

        assert len(accounts) == 2

    def test_parse_invalid_json(self):
        from src.agents.account_discovery import parse_accounts

        icp = ICPDefinition(description="test")
        accounts = parse_accounts("not json at all", icp)
        assert accounts == []

    def test_parse_empty_domain(self):
        from src.agents.account_discovery import parse_accounts

        icp = ICPDefinition(description="test")
        response = '[{"company_name": "Acme", "domain": ""}]'
        accounts = parse_accounts(response, icp)
        assert accounts == []

    def test_build_user_message(self):
        from src.agents.account_discovery import build_user_message

        icp = ICPDefinition(
            description="SaaS companies",
            target_roles=["CTO"],
            company_size="50-200",
            industries=["SaaS"],
            geographies=["US"],
            max_leads=10,
        )
        msg = build_user_message(icp)

        assert "SaaS companies" in msg
        assert "CTO" in msg
        assert "50-200" in msg
        assert "10" in msg


class TestContactEmailParsing:
    def test_parse_valid_response(self):
        from src.agents.contact_email import parse_contacts

        account = Account(company_name="Acme", domain="acme.io")
        contacts = parse_contacts(CONTACT_EMAIL_RESPONSE, account)

        assert len(contacts) == 1
        assert contacts[0].first_name == "Jane"
        assert contacts[0].last_name == "Doe"
        assert contacts[0].email == "jane.doe@acme.io"
        assert contacts[0].email_confidence == 85

    def test_parse_missing_name(self):
        from src.agents.contact_email import parse_contacts

        account = Account(company_name="Acme", domain="acme.io")
        response = '[{"first_name": "", "last_name": "Doe", "email": "test@acme.io"}]'
        contacts = parse_contacts(response, account)
        assert contacts == []

    def test_parse_invalid_json(self):
        from src.agents.contact_email import parse_contacts

        account = Account(company_name="Acme", domain="acme.io")
        contacts = parse_contacts("garbage response", account)
        assert contacts == []


class TestResearchParsing:
    def test_parse_valid_response(self):
        from src.agents.research import parse_dossier

        contact = Contact(first_name="Jane", last_name="Doe")
        dossier = parse_dossier(RESEARCH_RESPONSE, contact)

        assert dossier.github_username == "janedoe"
        assert len(dossier.github_repos) > 0
        assert "Python" in dossier.github_languages
        assert dossier.education == "Stanford University, CS"

    def test_parse_invalid_json(self):
        from src.agents.research import parse_dossier

        contact = Contact(first_name="Jane", last_name="Doe")
        dossier = parse_dossier("not json", contact)

        # Should return a dossier with raw notes containing the response
        assert dossier.raw_research_notes != ""

    def test_parse_empty_dossier(self):
        from src.agents.research import parse_dossier

        contact = Contact(first_name="Jane", last_name="Doe")
        dossier = parse_dossier("{}", contact)

        assert dossier.github_username is None
        assert dossier.github_repos == []


class TestEmailComposerParsing:
    def test_parse_valid_response(self):
        from src.agents.email_composer import parse_email

        config = CampaignConfig()
        email = parse_email(EMAIL_COMPOSER_RESPONSE, config)

        assert "awesome-cli" in email.subject_line
        assert email.body != ""
        assert len(email.personalization_hooks) > 0

    def test_parse_invalid_json(self):
        from src.agents.email_composer import parse_email

        config = CampaignConfig()
        email = parse_email("not json", config)

        assert "[PARSE ERROR]" in email.subject_line

    def test_parse_detects_unsubscribe(self):
        from src.agents.email_composer import parse_email

        config = CampaignConfig(
            unsubscribe_text="Not interested? Reply 'unsubscribe'",
            physical_address="123 Main St, City, State ZIP",
        )
        email = parse_email(EMAIL_COMPOSER_RESPONSE, config)

        assert email.includes_unsubscribe is True
        assert email.includes_physical_address is True
