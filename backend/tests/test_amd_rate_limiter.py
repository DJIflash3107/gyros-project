import pytest

import app.configs.amd_client as amd_client_module


@pytest.mark.asyncio
async def test_rate_limiter_spaces_requests(monkeypatch):
    amd_client_module._reset_rate_limiter_for_tests()
    current_time = 100.0

    def fake_monotonic():
        nonlocal current_time
        value = current_time
        current_time += 0.1
        return value

    monkeypatch.setattr(amd_client_module.time, "monotonic", fake_monotonic)
    delays = []

    async def record_sleep(delay):
        delays.append(delay)
        nonlocal current_time
        current_time += delay

    monkeypatch.setattr(amd_client_module.asyncio, "sleep", record_sleep)
    await amd_client_module._wait_for_rate_slot()
    await amd_client_module._wait_for_rate_slot()

    assert delays == [pytest.approx(60 / 18 - 0.1)]
    amd_client_module._reset_rate_limiter_for_tests()
