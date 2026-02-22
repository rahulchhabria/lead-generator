"""Detect iOS and Android mobile apps from website HTML."""
from __future__ import annotations

import re

from .models import MobileApp, MobileApps

IOS_PATTERNS = [
    (r"https://apps\.apple\.com/[a-z]{2}/app/[^\"'>\s]+/id(\d+)", "app_store_link"),
    (r"https://itunes\.apple\.com/[^\"'>\s]+/id(\d+)", "itunes_link"),
    (r'<meta[^>]+name=["\']apple-itunes-app["\'][^>]+content=["\'][^"\']*app-id=(\d+)', "smart_banner"),
]

ANDROID_PATTERNS = [
    (r"https://play\.google\.com/store/apps/details\?id=([\w.]+)", "play_store_link"),
    (r'<link[^>]+rel=["\']alternate["\'][^>]+href=["\']android-app://([\w.]+)', "android_app_link"),
]


def detect_mobile_apps(html: str) -> MobileApps:
    """Detect iOS and Android apps from page HTML."""
    ios_apps: list[MobileApp] = []
    android_apps: list[MobileApp] = []
    seen_ios: set[str] = set()
    seen_android: set[str] = set()

    for pattern, method in IOS_PATTERNS:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            app_id = m.group(1)
            if app_id not in seen_ios:
                seen_ios.add(app_id)
                ios_apps.append(MobileApp(
                    app_id=app_id,
                    url=m.group(0).split('"')[0].split("'")[0],
                    detection_method=method,
                ))

    for pattern, method in ANDROID_PATTERNS:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            pkg = m.group(1)
            if pkg not in seen_android:
                seen_android.add(pkg)
                android_apps.append(MobileApp(
                    app_id=pkg,
                    url=f"https://play.google.com/store/apps/details?id={pkg}",
                    detection_method=method,
                ))

    return MobileApps(
        has_ios_app=len(ios_apps) > 0,
        has_android_app=len(android_apps) > 0,
        ios_apps=ios_apps,
        android_apps=android_apps,
    )
