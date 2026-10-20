# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Sphinx entry point for the Arm API reference theme."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docutils.nodes import document
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.util.typing import ExtensionMetadata

THEME_PATH = Path(__file__).parent / "theme" / "arm_design_system"
TEMPLATE_PATH = Path(__file__).parent / "templates"


def _add_template_path(app: Sphinx, _config: Config) -> None:
    app.config.templates_path.append(str(TEMPLATE_PATH))


def _add_page_context(
    _app: Sphinx,
    _page_name: str,
    _template_name: str,
    context: dict[str, Any],
    _doctree: document | None,
) -> None:
    context["arm_current_year"] = datetime.now(UTC).year


def setup(app: Sphinx) -> ExtensionMetadata:
    """Register the bundled HTML theme with Sphinx."""

    app.add_html_theme("arm_design_system", str(THEME_PATH))
    app.add_css_file("styles/arm-design-system.css", priority=700)
    app.connect("config-inited", _add_template_path)
    app.connect("html-page-context", _add_page_context)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
