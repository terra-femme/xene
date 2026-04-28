"""
Audit script to detect and fix platform field contamination in the artists table.

Identifies records where platform identifiers have been mixed (e.g., Instagram handles
in soundcloud_username field) and provides repair suggestions.

Usage:
    python audit_platform_corruption.py --scan    # Find corrupted records
    python audit_platform_corruption.py --fix     # Fix identified corruption
    python audit_platform_corruption.py --report  # Generate report
"""

import asyncio
import logging
from database import get_db
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def _is_instagram_handle(value: str) -> bool:
    """Detect Instagram-style handles."""
    if not value:
        return False
    value_lower = value.lower()
    # Instagram handles often have underscores; SoundCloud rarely do
    if "_dnb" in value_lower or "_" in value_lower and "@" not in value:
        return True
    return False


def _is_full_url(value: str) -> bool:
    """Check if value is a URL instead of just an identifier."""
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def _is_soundcloud_url(value: str) -> bool:
    """Check if value is specifically a SoundCloud URL."""
    if not value:
        return False
    return "soundcloud.com" in value.lower()


def audit_soundcloud_field() -> dict[str, Any]:
    """Scan for corruption in soundcloud_username field."""
    db = get_db()
    logger.info("[audit] Scanning soundcloud_username field for corruption...")

    result = db.table("artists").select("id, name, soundcloud_username, user_id").execute()
    artists = result.data or []

    corrupted = []
    suspicious = []

    for artist in artists:
        sc_user = artist.get("soundcloud_username", "").strip()
        if not sc_user:
            continue

        red_flags = []

        # Red flag 1: Contains a full URL
        if _is_full_url(sc_user):
            red_flags.append("contains_full_url")
            # Red flag 1a: Is it a SoundCloud URL being stored as a username?
            if _is_soundcloud_url(sc_user):
                red_flags.append("is_soundcloud_url_not_username")
            else:
                red_flags.append("is_non_soundcloud_url")

        # Red flag 2: Instagram-style handle
        if _is_instagram_handle(sc_user):
            red_flags.append("instagram_style_handle")

        # Red flag 3: Contains @ symbol (Twitter/Instagram)
        if "@" in sc_user:
            red_flags.append("contains_at_symbol")

        # Red flag 4: Extremely long (usernames are usually <50 chars)
        if len(sc_user) > 100:
            red_flags.append("unusually_long")

        if red_flags:
            record = {
                "id": artist["id"],
                "name": artist["name"],
                "user_id": artist["user_id"],
                "soundcloud_username": sc_user,
                "red_flags": red_flags,
                "severity": "CRITICAL" if "non_soundcloud_url" in red_flags else "HIGH"
            }

            if "non_soundcloud_url" in red_flags or "instagram_style_handle" in red_flags:
                corrupted.append(record)
            else:
                suspicious.append(record)

    return {
        "total_artists_scanned": len(artists),
        "corrupted_count": len(corrupted),
        "suspicious_count": len(suspicious),
        "corrupted": corrupted,
        "suspicious": suspicious,
    }


def print_audit_report(audit_result: dict[str, Any]) -> None:
    """Print human-readable audit report."""
    print("\n" + "="*80)
    print("PLATFORM FIELD CORRUPTION AUDIT REPORT")
    print("="*80)

    print(f"\nTotal artists scanned: {audit_result['total_artists_scanned']}")
    print(f"CORRUPTED (needs manual review): {audit_result['corrupted_count']}")
    print(f"SUSPICIOUS (potential issues): {audit_result['suspicious_count']}")

    if audit_result["corrupted"]:
        print("\n" + "-"*80)
        print("CORRUPTED RECORDS (High Priority)")
        print("-"*80)
        for record in audit_result["corrupted"]:
            print(f"\nArtist ID: {record['id']}")
            print(f"  Name: {record['name']}")
            print(f"  User ID: {record['user_id']}")
            print(f"  soundcloud_username: {record['soundcloud_username']}")
            print(f"  Red Flags: {', '.join(record['red_flags'])}")
            print(f"  Severity: {record['severity']}")

            # Suggest fix based on flags
            if "is_non_soundcloud_url" in record["red_flags"]:
                print(f"  SUGGESTION: Extract just the username from the URL")
                # Try to extract
                url = record["soundcloud_username"]
                if "soundcloud.com/" in url:
                    suggested = url.split("soundcloud.com/")[-1].split("/")[0]
                    print(f"    → Try: '{suggested}'")

    if audit_result["suspicious"]:
        print("\n" + "-"*80)
        print("SUSPICIOUS RECORDS (Review Recommended)")
        print("-"*80)
        for record in audit_result["suspicious"][:10]:  # Limit output
            print(f"\nArtist: {record['name']} (ID: {record['id']})")
            print(f"  soundcloud_username: {record['soundcloud_username']}")
            print(f"  Flags: {', '.join(record['red_flags'])}")

        if len(audit_result["suspicious"]) > 10:
            print(f"\n... and {len(audit_result['suspicious']) - 10} more suspicious records")

    print("\n" + "="*80)


def suggest_fixes(audit_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Suggest automated fixes for corrupted records."""
    fixes = []

    for record in audit_result["corrupted"]:
        sc_user = record["soundcloud_username"]
        fix_action = None
        new_value = None

        # Fix 1: Extract username from SoundCloud URL
        if "is_soundcloud_url_not_username" in record["red_flags"]:
            try:
                # Parse: https://soundcloud.com/r3idy or https://soundcloud.com/r3idy/
                if "soundcloud.com/" in sc_user:
                    new_value = sc_user.split("soundcloud.com/")[-1].strip("/").split("/")[0]
                    fix_action = "EXTRACT_USERNAME_FROM_URL"
            except Exception:
                pass

        # Fix 2: Flag for manual review if it's a non-SoundCloud URL
        if "is_non_soundcloud_url" in record["red_flags"]:
            fix_action = "MANUAL_REVIEW_REQUIRED"
            print(f"⚠️  {record['name']}: Contains non-SoundCloud URL, needs manual fix")

        if fix_action:
            fixes.append({
                "artist_id": record["id"],
                "artist_name": record["name"],
                "current_value": sc_user,
                "suggested_value": new_value,
                "action": fix_action
            })

    return fixes


async def apply_fixes(fixes: list[dict[str, Any]]) -> None:
    """Apply suggested fixes to database."""
    if not fixes:
        logger.info("[audit] No fixes to apply")
        return

    db = get_db()
    success_count = 0
    skip_count = 0

    for fix in fixes:
        if fix["action"] == "EXTRACT_USERNAME_FROM_URL" and fix["suggested_value"]:
            try:
                db.table("artists").update({
                    "soundcloud_username": fix["suggested_value"]
                }).eq("id", fix["artist_id"]).execute()

                logger.info(
                    "[audit] Fixed %s: %r → %r",
                    fix["artist_name"], fix["current_value"], fix["suggested_value"]
                )
                success_count += 1
            except Exception as e:
                logger.error("[audit] Failed to fix %s: %s", fix["artist_name"], e)

        elif fix["action"] == "MANUAL_REVIEW_REQUIRED":
            logger.warning("[audit] Skipping %s (requires manual review): %s",
                          fix["artist_name"], fix["current_value"])
            skip_count += 1

    logger.info("[audit] Applied fixes: %d successful, %d skipped", success_count, skip_count)


if __name__ == "__main__":
    import sys

    action = sys.argv[1] if len(sys.argv) > 1 else "--scan"

    if action == "--scan":
        result = audit_soundcloud_field()
        print_audit_report(result)

    elif action == "--fix":
        result = audit_soundcloud_field()
        fixes = suggest_fixes(result)
        if fixes:
            print(f"\nWill apply {len(fixes)} fixes...")
            confirm = input("Apply fixes? (y/N): ").lower()
            if confirm == "y":
                asyncio.run(apply_fixes(fixes))
            else:
                print("Cancelled")
        else:
            print("No fixes available")

    elif action == "--report":
        result = audit_soundcloud_field()
        print_audit_report(result)
        # Also dump JSON for further processing
        import json
        with open("audit_report.json", "w") as f:
            # Convert for JSON serialization
            clean_result = {
                k: v for k, v in result.items()
                if k not in ("corrupted", "suspicious")
            }
            clean_result["corrupted"] = result["corrupted"][:50]  # Limit for JSON
            clean_result["suspicious"] = result["suspicious"][:50]
            json.dump(clean_result, f, indent=2)
        print("\nReport saved to audit_report.json")

    else:
        print(f"Usage: python audit_platform_corruption.py [--scan|--fix|--report]")
        sys.exit(1)
