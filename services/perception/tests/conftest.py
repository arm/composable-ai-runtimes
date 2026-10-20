# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    if exitstatus == pytest.ExitCode.OK and session.testsfailed == 0:
        terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal_reporter is not None and terminal_reporter.stats.get("skipped"):
            terminal_reporter.write_sep(
                "=",
                "ERROR: skipped tests are not permitted",
            )
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
