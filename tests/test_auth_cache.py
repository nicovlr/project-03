"""Tests for API key authentication and caching."""

from __future__ import annotations

import os
import time

import pytest

from app.api.cache import cached, clear_cache


class TestCache:
    def setup_method(self):
        clear_cache()

    def test_cached_returns_same_value(self):
        call_count = 0

        @cached(ttl=60)
        def expensive():
            nonlocal call_count
            call_count += 1
            return {"data": 42}

        result1 = expensive()
        result2 = expensive()
        assert result1 == result2
        assert call_count == 1

    def test_cache_expires(self):
        call_count = 0

        @cached(ttl=1)
        def short_lived():
            nonlocal call_count
            call_count += 1
            return call_count

        r1 = short_lived()
        assert r1 == 1
        time.sleep(1.1)
        r2 = short_lived()
        assert r2 == 2

    def test_different_args_different_cache(self):
        @cached(ttl=60)
        def compute(x):
            return x * 2

        assert compute(5) == 10
        assert compute(10) == 20

    def test_clear_cache(self):
        @cached(ttl=60)
        def cached_fn():
            return time.time()

        val1 = cached_fn()
        evicted = clear_cache()
        assert evicted >= 1
        val2 = cached_fn()
        assert val2 != val1


class TestAuthModule:
    def test_open_mode_when_no_key_set(self):
        """When GOVSENSE_API_KEY is not set, auth should pass."""
        import app.api.auth as auth_module
        original = auth_module.API_KEY
        auth_module.API_KEY = None
        try:
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                auth_module.verify_api_key(None)
            )
            assert result is None
        finally:
            auth_module.API_KEY = original

    def test_reject_wrong_key(self):
        import app.api.auth as auth_module
        from fastapi import HTTPException
        original = auth_module.API_KEY
        auth_module.API_KEY = "secret-key-123"
        try:
            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    auth_module.verify_api_key("wrong-key")
                )
            assert exc_info.value.status_code == 403
        finally:
            auth_module.API_KEY = original

    def test_accept_correct_key(self):
        import app.api.auth as auth_module
        original = auth_module.API_KEY
        auth_module.API_KEY = "secret-key-123"
        try:
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                auth_module.verify_api_key("secret-key-123")
            )
            assert result == "secret-key-123"
        finally:
            auth_module.API_KEY = original
