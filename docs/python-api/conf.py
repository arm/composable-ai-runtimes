# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Sphinx configuration for the Cairn Python API reference."""

import builtins
import inspect
import sys
from pathlib import Path

import tomllib
from jinja2 import ChoiceLoader, Environment, PackageLoader, PrefixLoader
from sphinx import addnodes

DOCS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = DOCS_ROOT.parents[1]
THEME_ROOT = DOCS_ROOT / "_theme"
PYPROJECT_PATH = REPOSITORY_ROOT / "lib" / "pyproject.toml"

sys.path.insert(0, str(THEME_ROOT))

with PYPROJECT_PATH.open("rb") as pyproject_file:
    project_metadata = tomllib.load(pyproject_file)["project"]

project = "Cairn Python API Reference"
author = "Arm"
copyright = "2026, Arm"
version = project_metadata["version"]
release = version

extensions = [
    "arm_design_system",
    "autoapi.extension",
    "sphinx.ext.intersphinx",
]

python_docs_version = f"{sys.version_info.major}.{sys.version_info.minor}"
intersphinx_mapping = {
    "python": (f"https://docs.python.org/{python_docs_version}", None)
}

# AutoAPI reads the package and generated PyO3 stub without importing or
# compiling the native extension.
autoapi_dirs = [str(REPOSITORY_ROOT / "lib" / "python")]
autoapi_file_patterns = ["*.pyi", "*.py"]
autoapi_root = "api"
autoapi_add_toctree_entry = False
autoapi_member_order = "bysource"
autoapi_template_dir = "_templates"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "special-members",
]

exclude_patterns = ["_build", "_templates", "Thumbs.db", ".DS_Store"]

html_theme = "arm_design_system"
html_title = "Cairn Python API Reference"


def _link_builtin_type_references(_app, doctree):
    """Resolve built-in types through the Python documentation inventory."""
    for reference in doctree.findall(addnodes.pending_xref):
        target = reference.get("reftarget")
        if (
            reference.get("refdomain") == "py"
            and reference.get("reftype") in {"class", "obj"}
            and isinstance(target, str)
            and inspect.isclass(getattr(builtins, target, None))
        ):
            reference["intersphinx"] = True
            reference["inventory"] = "python"


def _prepare_autoapi_templates(environment: Environment) -> None:
    # Keep the upstream class template available to classes outside this override.
    environment.loader = ChoiceLoader(
        [
            environment.loader,
            PrefixLoader({"upstream": PackageLoader("autoapi", "templates")}),
        ]
    )


autoapi_prepare_jinja_env = _prepare_autoapi_templates


def setup(app):
    # Resolve built-ins externally before local members such as the ``bytes``
    # payload properties can shadow them.
    app.connect("doctree-read", _link_builtin_type_references)
