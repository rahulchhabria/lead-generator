"""Detect technology stack from HTML content and HTTP headers."""
from __future__ import annotations

from .models import TechStack, TechnographicData

TECH_PATTERNS: dict[str, dict[str, list[str]]] = {
    "frontend_frameworks": {
        "React": ["react", "reactdom", "react-dom", "_react", "__react"],
        "Next.js": ["next.js", "/_next/", "__next", "next/dist"],
        "Vue.js": ["vue.js", "vuejs", "vue@", "/vue/"],
        "Angular": ["angular", "ng-version", "angular/core"],
        "Svelte": ["svelte", "svelte-kit"],
        "Nuxt.js": ["nuxt", "/_nuxt/"],
        "Remix": ["remix.run", "__remix"],
        "Gatsby": ["gatsby", "gatsby-browser"],
    },
    "backend_frameworks": {
        "Node.js": ["node.js", "express", "fastify", "koa"],
        "Django": ["django", "csrfmiddlewaretoken", "django-admin"],
        "Rails": ["rails", "action_cable", "turbolinks"],
        "Laravel": ["laravel", "laravel_session"],
        "FastAPI": ["fastapi", "openapi.json"],
        "Flask": ["flask", "werkzeug"],
        "Spring Boot": ["spring", "x-application-context"],
        "ASP.NET": ["asp.net", "x-aspnet", "x-powered-by: asp.net"],
    },
    "databases": {
        "PostgreSQL": ["postgresql", "postgres", "pg://"],
        "MySQL": ["mysql"],
        "MongoDB": ["mongodb", "mongoose"],
        "Redis": ["redis", "ioredis"],
        "Elasticsearch": ["elasticsearch", "kibana"],
        "DynamoDB": ["dynamodb", "amazonaws.com/dynamodb"],
        "Supabase": ["supabase"],
        "PlanetScale": ["planetscale"],
    },
    "cloud_providers": {
        "AWS": ["amazonaws.com", "cloudfront.net", "s3.amazonaws", "aws-sdk"],
        "Google Cloud": ["googlecloud", "googleapis.com"],
        "Azure": ["azure.com", "azurewebsites"],
        "Vercel": ["vercel.app", "x-vercel", "vercel"],
        "Netlify": ["netlify.app", "x-nf-"],
        "Cloudflare": ["cloudflare", "cf-ray"],
        "Heroku": ["heroku", "herokuapp.com"],
    },
    "analytics": {
        "Google Analytics": ["google-analytics.com", "ga.js", "gtag", "UA-", "G-"],
        "Segment": ["segment.com", "analytics.js", "segment.io"],
        "Mixpanel": ["mixpanel.com", "mixpanel"],
        "Amplitude": ["amplitude.com", "amplitude.js"],
        "PostHog": ["posthog.com", "posthog-js"],
        "Plausible": ["plausible.io"],
        "Heap": ["heapanalytics.com", "heap.js"],
        "Fullstory": ["fullstory.com", "fs.js"],
    },
    "observability": {
        "Sentry": ["sentry.io", "sentry-cdn", "@sentry/", "sentry.browser"],
        "Datadog": ["datadoghq.com", "dd-rum", "datadog"],
        "New Relic": ["newrelic.com", "newrelic.js", "nr-data.net"],
        "LogRocket": ["logrocket.com"],
        "Dynatrace": ["dynatrace.com", "dtrum"],
        "OpenTelemetry": ["opentelemetry", "otel"],
        "Grafana": ["grafana.com", "grafana"],
        "Honeycomb": ["honeycomb.io"],
        "Rollbar": ["rollbar.com"],
        "Bugsnag": ["bugsnag.com"],
    },
    "payments": {
        "Stripe": ["stripe.com", "js.stripe.com", "stripe.js"],
        "PayPal": ["paypal.com", "paypalobjects"],
        "Braintree": ["braintree"],
        "Square": ["squareup.com", "square.js"],
        "Adyen": ["adyen.com"],
    },
    "customer_support": {
        "Intercom": ["intercom.com", "widget.intercom.io", "intercomSettings"],
        "Zendesk": ["zendesk.com", "zdassets.com"],
        "Drift": ["drift.com", "js.driftt.com"],
        "HubSpot Chat": ["hs-scripts"],
        "Crisp": ["crisp.chat"],
        "Help Scout": ["helpscout.net", "beacon-v2"],
    },
    "marketing": {
        "HubSpot": ["hubspot.com", "hs-analytics"],
        "Marketo": ["marketo.com", "munchkin.js"],
        "Pardot": ["pardot.com", "pi.pardot"],
        "Salesforce": ["salesforce.com", "force.com"],
        "Mailchimp": ["mailchimp.com", "list-manage.com"],
        "ActiveCampaign": ["activecampaign.com"],
    },
    "auth": {
        "Auth0": ["auth0.com", "auth0-spa", "auth0.js"],
        "Okta": ["okta.com", "okta-signin"],
        "Firebase Auth": ["firebase.googleapis.com", "firebaseapp.com"],
        "Clerk": ["clerk.dev", "clerk.com"],
        "AWS Cognito": ["cognito", "amazonaws.com/cognito"],
    },
    "cdn": {
        "Cloudflare": ["cfcdn", "cdnjs.cloudflare.com"],
        "CloudFront": ["cloudfront.net"],
        "Fastly": ["fastly.net"],
        "jsDelivr": ["jsdelivr.net"],
    },
    "infrastructure": {
        "Docker": ["docker.com", "dockerfile"],
        "Kubernetes": ["kubernetes", "k8s"],
        "Terraform": ["terraform.io"],
        "GitHub Actions": ["github.com/actions"],
        "Jenkins": ["jenkins"],
        "CircleCI": ["circleci.com"],
    },
}


def detect_technologies(html: str, headers: dict[str, str] | None = None) -> TechnographicData:
    """Detect technologies from HTML content and HTTP response headers."""
    header_vals = " ".join(headers.values()) if headers else ""
    content = (html + " " + header_vals).lower()

    result = TechnographicData()
    all_tech_names: list[str] = []

    category_map = {
        "frontend_frameworks": result.frontend_frameworks,
        "backend_frameworks": result.backend_frameworks,
        "databases": result.databases,
        "cloud_providers": result.cloud_providers,
        "analytics": result.analytics,
        "observability": result.observability,
        "payments": result.payments,
        "customer_support": result.customer_support,
        "marketing": result.marketing,
        "auth": result.auth,
        "cdn": result.cdn,
        "infrastructure": result.infrastructure,
    }

    for category, techs in TECH_PATTERNS.items():
        target_list = category_map[category]
        for tech_name, patterns in techs.items():
            if any(p.lower() in content for p in patterns):
                target_list.append(TechStack(name=tech_name, category=category))
                if tech_name not in all_tech_names:
                    all_tech_names.append(tech_name)

    result.all_technologies = all_tech_names
    return result
