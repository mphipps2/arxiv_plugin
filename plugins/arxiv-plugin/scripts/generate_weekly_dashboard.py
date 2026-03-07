#!/usr/bin/env python3
"""Generate weekly dashboard HTML from JSON on stdin."""

import json
import os
import sys
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

env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
template = env.get_template("weekly-dashboard.html")

html = template.render(**data)

week_end = data.get("week_end", "unknown")
out_path = output_dir / f"weekly-{week_end}.html"
out_path.write_text(html)

print(str(out_path.resolve()))
