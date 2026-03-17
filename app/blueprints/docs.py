"""Documentation blueprint — serves project docs as rendered HTML.

Reads markdown files from the ``docs/`` directory and renders them
with the ``markdown`` library.  All routes require authentication.
"""

import os
import re

import markdown
from flask import Blueprint, abort, current_app, render_template
from flask_security import login_required

docs_bp = Blueprint("docs", __name__, url_prefix="/docs")

# Mapping of URL slugs to markdown filenames
_DOC_FILES = {
    "user-guide": "user_guide.md",
    "architecture": "architecture.md",
    "installation": "installation.md",
    "configuration": "configuration.md",
    "cloud-deployment": "cloud_deployment.md",
}


def _docs_dir():
    """Return the absolute path to the docs/ directory."""
    return os.path.join(current_app.root_path, "..", "docs")


def _extract_title(md_content):
    """Extract the first ``# heading`` from markdown content."""
    match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    return match.group(1).strip() if match else None


def _get_doc_list():
    """Return a list of dicts with slug, title, and filename for each doc."""
    docs = []
    docs_path = _docs_dir()
    for slug, filename in sorted(_DOC_FILES.items()):
        filepath = os.path.join(docs_path, filename)
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            first_lines = f.read(500)
        title = _extract_title(first_lines) or slug.replace("-", " ").title()
        docs.append({"slug": slug, "title": title, "filename": filename})
    return docs


@docs_bp.route("/")
@login_required
def index():
    """List available documentation pages."""
    return render_template("docs/index.html", docs=_get_doc_list())


@docs_bp.route("/<slug>")
@login_required
def detail(slug):
    """Render a single documentation page."""
    filename = _DOC_FILES.get(slug)
    if filename is None:
        abort(404)

    filepath = os.path.join(_docs_dir(), filename)
    if not os.path.isfile(filepath):
        abort(404)

    with open(filepath, "r", encoding="utf-8") as f:
        md_content = f.read()

    title = _extract_title(md_content) or slug.replace("-", " ").title()
    html_content = markdown.markdown(
        md_content,
        extensions=["fenced_code", "tables", "toc", "codehilite"],
    )

    return render_template(
        "docs/detail.html",
        title=title,
        content=html_content,
        docs=_get_doc_list(),
        current_slug=slug,
    )
