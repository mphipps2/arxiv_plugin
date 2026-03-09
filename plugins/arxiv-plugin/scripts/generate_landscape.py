#!/usr/bin/env python3
"""Generate landscape analysis HTML from JSON on stdin."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", str(SCRIPT_DIR.parent))

config_path = os.path.join(PLUGIN_ROOT, "config.yaml")
try:
    with open(config_path) as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    config = {}

output_dir = Path(config.get("output_dir", "./arxiv-output"))
output_dir.mkdir(parents=True, exist_ok=True)

data = json.loads(sys.stdin.read())

tailwind_css_path = TEMPLATE_DIR / "tailwind.built.css"
data["tailwind_css"] = tailwind_css_path.read_text() if tailwind_css_path.exists() else ""

env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
template = env.get_template("landscape.html")

html = template.render(**data)

topic_slug = re.sub(r"[^a-z0-9]+", "-", data.get("topic", "unknown").lower()).strip("-")
date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
out_path = output_dir / f"landscape-{topic_slug}-{date}.html"
out_path.write_text(html)

print(str(out_path.resolve()))
