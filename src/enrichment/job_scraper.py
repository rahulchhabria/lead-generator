"""Scrape job listings from major job boards and company career pages."""
from __future__ import annotations

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import DepartmentHiring, HiringData, JobPosting

logger = logging.getLogger(__name__)

DEPT_KEYWORDS = {
    "engineering": [
        "engineer", "developer", "software", "frontend", "backend", "fullstack",
        "devops", "sre", "data", "ml", "ai", "architect", "platform", "infrastructure",
    ],
    "sales": ["sales", "account executive", "ae", "bdr", "sdr", "business development"],
    "marketing": ["marketing", "growth", "demand", "content", "seo", "brand"],
    "customer_success": ["customer success", "csm", "support", "implementation", "onboarding"],
    "operations": ["operations", "finance", "legal", "hr", "people", "recruiting", "talent"],
}

_NAV_WORDS = {
    "login", "log in", "log out", "sign up", "sign in", "signup", "signin",
    "contact", "pricing", "about", "home", "blog", "docs", "documentation",
    "open app", "download", "resources", "customers", "product", "features",
    "company", "terms", "privacy", "press", "newsletter", "get started",
    "book a demo", "request a demo", "see how", "learn more", "view all",
    "read more", "click here", "back", "next", "previous", "search",
    "changelog", "status", "help", "support", "security", "enterprise",
    "try for free", "start for free", "get a demo", "contact us",
}

_JOB_TITLE_WORDS = [
    "engineer", "developer", "designer", "manager", "director", "analyst",
    "scientist", "researcher", "lead", "head of", "vp ", "vice president",
    "coordinator", "specialist", "associate", "consultant", "architect",
    "recruiter", "sales", "marketing", "product manager", "ux ", "ui ",
    "data ", "security", "finance", "legal", "writer", "editor",
    "account executive", "sdr", "bdr", "devops", "sre", "backend",
    "frontend", "fullstack", "full stack", "full-stack", "software", "mobile",
    "ios", "android", "ml ", "ai ", "infrastructure", "platform",
    "operations", "ops ", "people", "talent", "customer success",
    "implementation", "onboarding", "intern", "administrative", "counsel",
]

SKILL_PATTERNS = [
    r"\b(python|javascript|typescript|react|node\.?js|golang|rust|java|kotlin|swift|ruby|php)\b",
    r"\b(aws|gcp|azure|kubernetes|docker|terraform)\b",
    r"\b(postgresql|mysql|mongodb|redis|elasticsearch|kafka)\b",
    r"\b(machine learning|deep learning|llm|nlp|pytorch|tensorflow)\b",
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; enrichment-bot/1.0)"})


def _get_html(url: str, timeout: int = 8) -> Optional[str]:
    try:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def _classify_department(title: str) -> str:
    title_lower = title.lower()
    for dept, keywords in DEPT_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return dept
    return "other"


def _extract_skills(text: str) -> list[str]:
    skills: set[str] = set()
    text_lower = text.lower()
    for pattern in SKILL_PATTERNS:
        for m in re.findall(pattern, text_lower, re.IGNORECASE):
            skills.add(m.lower())
    return list(skills)[:10]


def _scrape_greenhouse(slug: str) -> list[JobPosting]:
    html = _get_html(f"https://boards.greenhouse.io/{slug}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for item in soup.select(".opening"):
        title_el = item.select_one("a")
        dept_el = item.select_one(".department")
        loc_el = item.select_one(".location")
        if title_el:
            title = title_el.get_text(strip=True)
            jobs.append(JobPosting(
                title=title,
                department=dept_el.get_text(strip=True) if dept_el else _classify_department(title),
                location=loc_el.get_text(strip=True) if loc_el else None,
                url=title_el.get("href", ""),
            ))
    return jobs[:50]


def _scrape_lever(slug: str) -> list[JobPosting]:
    html = _get_html(f"https://jobs.lever.co/{slug}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for item in soup.select(".posting"):
        title_el = item.select_one("h5")
        dept_el = item.select_one(".posting-category")
        loc_el = item.select_one(".sort-by-location")
        link_el = item.select_one("a.posting-title")
        if title_el:
            title = title_el.get_text(strip=True)
            jobs.append(JobPosting(
                title=title,
                department=dept_el.get_text(strip=True) if dept_el else _classify_department(title),
                location=loc_el.get_text(strip=True) if loc_el else None,
                url=link_el.get("href", "") if link_el else "",
            ))
    return jobs[:50]


def _scrape_ashby(slug: str) -> list[JobPosting]:
    html = _get_html(f"https://jobs.ashbyhq.com/{slug}")
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for item in soup.select("[data-testid='job-listing-item'], .ashby-job-posting-brief"):
        title_el = item.select_one("h3, h2, [class*='title']")
        if title_el:
            title = title_el.get_text(strip=True)
            link = item.find("a")
            jobs.append(JobPosting(
                title=title,
                department=_classify_department(title),
                url=link.get("href", "") if link else "",
            ))
    return jobs[:50]


def _scrape_careers_page(domain: str) -> list[JobPosting]:
    for path in ["/careers", "/jobs", "/about/careers", "/company/careers", "/work-with-us"]:
        html = _get_html(f"https://{domain}{path}")
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        for item in soup.select("li, .job, .position, .opening, [class*='job'], [class*='role']")[:60]:
            link = item.find("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            title_lower = title.lower()
            if not (5 < len(title) < 120):
                continue
            if any(nav in title_lower for nav in _NAV_WORDS):
                continue
            if not any(jw in title_lower for jw in _JOB_TITLE_WORDS):
                continue
            jobs.append(JobPosting(
                title=title[:100],
                department=_classify_department(title),
                url=link.get("href", ""),
            ))
        if len(jobs) > 1:
            return jobs[:50]
    return []


def scrape_jobs(domain: str, company_name: str) -> HiringData:
    """Attempt job scraping across multiple sources."""
    slug = company_name.lower().replace(" ", "").replace(".", "").replace(",", "")
    domain_slug = domain.split(".")[0]

    all_jobs: list[JobPosting] = []
    for scraper_fn, s in [
        (_scrape_greenhouse, slug),
        (_scrape_greenhouse, domain_slug),
        (_scrape_lever, slug),
        (_scrape_lever, domain_slug),
        (_scrape_ashby, slug),
    ]:
        try:
            jobs = scraper_fn(s)
            if jobs:
                all_jobs = jobs
                break
        except Exception as e:
            logger.debug(f"Job scraper failed for {s}: {e}")

    if not all_jobs:
        try:
            all_jobs = _scrape_careers_page(domain)
        except Exception as e:
            logger.debug(f"Careers page scrape failed: {e}")

    # Deduplicate
    seen: set[str] = set()
    unique: list[JobPosting] = []
    for job in all_jobs:
        key = job.title.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(job)

    dept = DepartmentHiring()
    for job in unique:
        d = job.department or _classify_department(job.title)
        job.department = d
        if d == "engineering":
            dept.engineering += 1
        elif d == "sales":
            dept.sales += 1
        elif d == "marketing":
            dept.marketing += 1
        elif d == "customer_success":
            dept.customer_success += 1
        elif d == "operations":
            dept.operations += 1
        else:
            dept.other += 1

    all_text = " ".join(j.title for j in unique)
    top_skills = _extract_skills(all_text)

    return HiringData(
        open_positions=len(unique),
        job_listings=unique,
        department_breakdown=dept,
        top_skills=top_skills,
        hiring_velocity=min(len(unique), 30),
    )
