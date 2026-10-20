# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

pytest_plugins = ("pytester",)


def test_e2e_hook_records_test_call_failure(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(Path(__file__).with_name("conftest.py").read_text())
    pytester.makepyfile(
        """
        import pytest


        @pytest.fixture
        def observes_test_failure(request):
            yield
            print(
                "test call failed: "
                f"{getattr(request.node, '_cairn_test_call_failed', False)}"
            )


        def test_fails(observes_test_failure):
            assert False, "test body failed"
        """
    )

    result = pytester.runpytest("-q", "-s")

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*test call failed: True*"])
