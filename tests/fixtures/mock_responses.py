"""Mock API responses for testing."""

SERPER_RESPONSE = {
    "organic": [
        {
            "title": "Acme Corp - Developer Tools",
            "link": "https://acme.io",
            "snippet": "Acme Corp builds developer tools for modern teams.",
        },
        {
            "title": "Beta Inc - Cloud Infrastructure",
            "link": "https://beta.com",
            "snippet": "Beta Inc provides cloud infrastructure solutions.",
        },
    ]
}

HUNTER_DOMAIN_SEARCH_RESPONSE = {
    "data": {
        "domain": "acme.io",
        "pattern": "{first}.{last}",
        "emails": [
            {
                "value": "jane.doe@acme.io",
                "type": "personal",
                "confidence": 92,
                "first_name": "Jane",
                "last_name": "Doe",
                "position": "CTO",
                "department": "engineering",
                "linkedin": "https://linkedin.com/in/janedoe",
            }
        ],
    }
}

HUNTER_EMAIL_FINDER_RESPONSE = {
    "data": {
        "email": "john.smith@acme.io",
        "score": 85,
        "first_name": "John",
        "last_name": "Smith",
        "position": "VP Engineering",
        "linkedin": "https://linkedin.com/in/johnsmith",
        "sources": [{"domain": "acme.io"}],
    }
}

HUNTER_EMAIL_VERIFIER_RESPONSE = {
    "data": {
        "email": "jane.doe@acme.io",
        "status": "valid",
        "result": "deliverable",
        "score": 95,
        "regexp": True,
        "mx_records": True,
        "smtp_server": True,
        "smtp_check": True,
        "accept_all": False,
    }
}

GITHUB_USER_INFO_RESPONSE = {
    "login": "janedoe",
    "name": "Jane Doe",
    "bio": "CTO at Acme Corp. Building dev tools.",
    "company": "@acme",
    "location": "San Francisco, CA",
    "blog": "https://janedoe.dev",
    "twitter_username": "janedoe",
    "public_repos": 42,
    "followers": 150,
    "following": 30,
    "created_at": "2015-03-15T00:00:00Z",
}

GITHUB_USER_REPOS_RESPONSE = [
    {
        "name": "awesome-cli",
        "description": "A CLI framework for building beautiful terminal apps",
        "language": "Python",
        "stargazers_count": 250,
        "forks_count": 30,
        "updated_at": "2025-01-15T00:00:00Z",
        "html_url": "https://github.com/janedoe/awesome-cli",
        "topics": ["cli", "python", "terminal"],
    },
    {
        "name": "k8s-operator",
        "description": "Kubernetes operator for auto-scaling microservices",
        "language": "Go",
        "stargazers_count": 120,
        "forks_count": 15,
        "updated_at": "2025-01-10T00:00:00Z",
        "html_url": "https://github.com/janedoe/k8s-operator",
        "topics": ["kubernetes", "operator", "go"],
    },
]

ACCOUNT_DISCOVERY_RESPONSE = """[
    {
        "company_name": "Acme Corp",
        "domain": "acme.io",
        "industry": "Developer Tools",
        "employee_count": "100-500",
        "location": "San Francisco, CA",
        "description": "Builds developer tools for modern engineering teams.",
        "relevance_reasoning": "Series B SaaS company in developer tools space, matches ICP perfectly."
    },
    {
        "company_name": "Beta Inc",
        "domain": "beta.com",
        "industry": "Cloud Infrastructure",
        "employee_count": "50-200",
        "location": "New York, NY",
        "description": "Cloud infrastructure platform for startups.",
        "relevance_reasoning": "Growing cloud infra company, strong engineering culture."
    }
]"""

CONTACT_EMAIL_RESPONSE = """[
    {
        "first_name": "Jane",
        "last_name": "Doe",
        "title": "CTO",
        "email": "jane.doe@acme.io",
        "email_confidence": 85,
        "email_verified": false,
        "email_source": "pattern_dns",
        "linkedin_url": "https://linkedin.com/in/janedoe"
    }
]"""

RESEARCH_RESPONSE = """{
    "github_username": "janedoe",
    "github_repos": ["awesome-cli: A CLI framework for terminal apps", "k8s-operator: K8s operator for auto-scaling"],
    "github_languages": ["Python", "Go", "TypeScript"],
    "recent_posts": ["Building Resilient Systems - https://janedoe.dev/resilient-systems"],
    "interests": ["distributed systems", "developer experience", "open source"],
    "education": "Stanford University, CS",
    "open_source_contributions": ["awesome-cli (creator)", "kubernetes/kubernetes (contributor)"],
    "speaking_engagements": ["KubeCon 2024: Scaling Microservices"],
    "personal_details": ["Active in SF tech meetup scene", "Mentors at Techstars"],
    "data_sources": ["https://github.com/janedoe", "https://janedoe.dev"],
    "raw_research_notes": "Jane is an active open source contributor with strong opinions on developer tooling."
}"""

EMAIL_COMPOSER_RESPONSE = """{
    "subject_line": "Your awesome-cli project caught my eye",
    "body": "Hi Jane,\\n\\nI noticed your awesome-cli project on GitHub - the approach to terminal rendering is really clever. We're working on something similar for developer workflows at [Company].\\n\\nWould love to pick your brain on CLI design patterns over a quick 15-min chat next week?\\n\\nBest,\\n[Sender]\\n\\nNot interested? Reply 'unsubscribe' and I'll remove you immediately.\\n123 Main St, City, State ZIP",
    "personalization_hooks": ["awesome-cli GitHub project", "terminal rendering approach", "CLI design patterns expertise"]
}"""
