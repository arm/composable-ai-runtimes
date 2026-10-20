# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest
from loguru import logger

from perception_service.logging import configure_logging

pytestmark = pytest.mark.unit


def test_configure_logging_uses_log_level(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    configure_logging()

    logger.debug("hidden")
    logger.warning("visible")
    logger.remove()

    output = capsys.readouterr()
    assert output.out == ""
    assert "hidden" not in output.err
    assert "visible" in output.err


def test_configure_logging_rejects_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INVALID")

    with pytest.raises(ValueError, match="Level 'INVALID' does not exist"):
        configure_logging()
