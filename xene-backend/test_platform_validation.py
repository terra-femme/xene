"""
Unit test for platform field validation.

Verifies that the identity_engine rejects platform contamination attempts
(e.g., Instagram handles in SoundCloud fields).
"""

import pytest
from services.identity_engine import map_ai_result_to_artist_fields


def test_soundcloud_field_rejects_instagram_handle():
    """Test that Instagram-style handles are rejected from soundcloud_username."""
    # Simulate LLM returning Instagram handle in soundcloud field
    ai_result = {
        "name": "R3IDY",
        "soundcloudRss": {
            "url": "r3idy_dnb"  # Instagram handle, not SoundCloud username
        },
        "passivePlatforms": {
            "instagram": "r3idy_dnb"  # Correct: Instagram handle in instagram field
        }
    }

    result = map_ai_result_to_artist_fields(ai_result, "R3IDY")

    # soundcloud_username should be ABSENT (validation rejected it)
    assert "soundcloud_username" not in result, \
        f"Instagram handle should not be written to soundcloud_username. Got: {result.get('soundcloud_username')}"

    # instagram_username should be PRESENT (correct field)
    assert result.get("instagram_username") == "r3idy_dnb", \
        f"Instagram handle should be in instagram_username. Got: {result.get('instagram_username')}"

    print("[PASS] Instagram handle correctly rejected from SoundCloud field")


def test_soundcloud_field_accepts_valid_username():
    """Test that valid SoundCloud usernames are accepted."""
    ai_result = {
        "name": "R3IDY",
        "soundcloudRss": {
            "url": "r3idy"  # Valid SoundCloud username
        }
    }

    result = map_ai_result_to_artist_fields(ai_result, "R3IDY")

    assert result.get("soundcloud_username") == "r3idy", \
        f"Valid SoundCloud username should be accepted. Got: {result.get('soundcloud_username')}"

    print("[PASS] Valid SoundCloud username accepted")


def test_soundcloud_field_accepts_valid_url():
    """Test that SoundCloud URLs are properly converted to usernames."""
    ai_result = {
        "name": "R3IDY",
        "soundcloudRss": {
            "url": "https://soundcloud.com/r3idy"  # URL format
        }
    }

    result = map_ai_result_to_artist_fields(ai_result, "R3IDY")

    # Should extract username from URL
    assert result.get("soundcloud_username") == "r3idy", \
        f"Should extract username from URL. Got: {result.get('soundcloud_username')}"

    print("[PASS] SoundCloud URL correctly extracted to username")


def test_instagram_field_accepts_valid_handle():
    """Test that Instagram handles go to the correct field."""
    ai_result = {
        "name": "R3IDY",
        "passivePlatforms": {
            "instagram": "r3idy_dnb"
        }
    }

    result = map_ai_result_to_artist_fields(ai_result, "R3IDY")

    assert result.get("instagram_username") == "r3idy_dnb", \
        f"Instagram handle should be in instagram_username. Got: {result.get('instagram_username')}"

    print("[PASS] Instagram handle correctly placed in instagram field")


def test_multiple_platforms_no_contamination():
    """Test that multiple platforms don't contaminate each other."""
    ai_result = {
        "name": "Artist Name",
        "soundcloudRss": {
            "url": "https://soundcloud.com/artist"
        },
        "passivePlatforms": {
            "instagram": "artist_official",
            "twitter": "artist_music"
        }
    }

    result = map_ai_result_to_artist_fields(ai_result, "Artist Name")

    # Each should be in its own field
    assert result.get("soundcloud_username") == "artist"
    assert result.get("instagram_username") == "artist_official"
    assert result.get("twitter_username") == "artist_music"

    print("[PASS] Multiple platforms correctly separated")


if __name__ == "__main__":
    test_soundcloud_field_rejects_instagram_handle()
    test_soundcloud_field_accepts_valid_username()
    test_soundcloud_field_accepts_valid_url()
    test_instagram_field_accepts_valid_handle()
    test_multiple_platforms_no_contamination()
    print("\n[SUCCESS] All platform validation tests passed!")
