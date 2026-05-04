"""
api_test slate — corporate template for API test style.

Drop your real corporate API test file here.
PRISM will parse the style and apply it when generating API test output files.

Role: api_test → drives API/{entity}_test.py generation
"""
from __future__ import annotations

import logging

import httpx
import pytest

logger = logging.getLogger(__name__)

BASE_URL = "https://api.example.com"


class TestExampleApi:
    """Corporate API test class."""

    def test_get_resource(self) -> None:
        logger.info("Testing GET /resource")
        response = httpx.get(f"{BASE_URL}/resource")
        assert response.status_code == 200

    def test_post_resource(self) -> None:
        logger.info("Testing POST /resource")
        payload = {"name": "example"}
        response = httpx.post(f"{BASE_URL}/resource", json=payload)
        assert response.status_code == 201
