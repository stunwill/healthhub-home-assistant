from __future__ import annotations

import os

# Pytest imports conftest.py before collecting test modules. Configure the
# application to use repository-local test state before app.database is ever
# imported by another test module.
os.environ.setdefault("HEALTHHUB_DATABASE_URL", "sqlite:///./test-healthhub.db")
os.environ.setdefault("HEALTHHUB_ACTIVE_PROFILE_FILE", "./test-active-profile.json")
