import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_brandbook(file_path: str) -> dict:
    p = Path(file_path)
    suffix = p.suffix.lower()

    if suffix == ".json":
        return _parse_json(p)
    if suffix in (".yaml", ".yml"):
        return _parse_yaml(p)
    if suffix == ".pdf":
        return _parse_pdf(p)

    logger.warning("Unsupported brandbook format: %s", suffix)
    return {}


def _parse_json(p: Path) -> dict:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return _extract_colors(data)
    except Exception as e:
        logger.error("Failed to parse JSON brandbook: %s", e)
        return {}


def _parse_yaml(p: Path) -> dict:
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return _extract_colors(data)
    except Exception as e:
        logger.error("Failed to parse YAML brandbook: %s", e)
        return {}


def _parse_pdf(p: Path) -> dict:
    try:
        import fitz
        doc = fitz.open(str(p))
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return _extract_colors_from_text(text)
    except Exception as e:
        logger.error("Failed to parse PDF brandbook: %s", e)
        return {}


def _extract_colors(data: dict) -> dict:
    colors = {}
    color_keys = ["primary", "secondary", "accent", "background", "text", "colors", "palette"]
    for key in color_keys:
        if key in data:
            val = data[key]
            if isinstance(val, str):
                colors[key] = val
            elif isinstance(val, dict):
                for k, v in val.items():
                    if isinstance(v, str) and v.startswith("#"):
                        colors[f"{key}_{k}"] = v
            elif isinstance(val, list):
                for i, v in enumerate(val):
                    if isinstance(v, str) and v.startswith("#"):
                        colors[f"{key}_{i}"] = v
    return colors


def _extract_colors_from_text(text: str) -> dict:
    import re
    colors = {}
    hex_pattern = r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})"
    matches = re.findall(hex_pattern, text)
    for i, match in enumerate(matches[:10]):
        colors[f"color_{i}"] = f"#{match}"
    return colors
