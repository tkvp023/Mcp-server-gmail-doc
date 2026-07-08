"""
Run this script once to trigger the Google OAuth 2.0 consent flow
and generate the token.json file.
"""

import sys
import logging
from src.auth import get_credentials

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("Starting OAuth consent flow...")
    try:
        creds = get_credentials()
        if creds and creds.valid:
            print("\n✅ Authentication successful! token.json has been created.")
        else:
            print("\n❌ Authentication failed.")
    except Exception as e:
        print(f"\n❌ Error during authentication: {e}")
        sys.exit(1)
