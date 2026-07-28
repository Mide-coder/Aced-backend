"""
Identity Validation Strategy [E001-S04]
Manual verification criteria for Nigerian university students during the pilot.

Storage schema for Cloudflare R2: matric-ids/{user_id}/{uuid}.{ext}

Manual verification criteria:
1. Matric ID must clearly show the student's full name matching their account
2. Matric ID must show the university name matching the detected university
3. The registration number must follow Nigerian university format (e.g., 21/1234, 2021/12345)
4. Photo on ID must match the user (subjective visual check)
5. Expiry date must be valid (if applicable)
"""

from app.models import VerificationStatus  # Re-export for convenience

VERIFICATION_CRITERIA = [
    "Matric ID must clearly display the student's full name matching their account registration name",
    "Matric ID must show the university name matching the auto-detected university from email domain",
    "Registration number must follow a valid Nigerian university format (e.g., 21/1234, 2021/12345, 19012345)",
    "Photo on the matric ID (if present) should visually match the user",
    "Document must not be expired or tampered with",
    "File must be a clear scan/photo — not blurry or cut off",
    "Only Nigerian university matriculation IDs are accepted during the pilot",
]
