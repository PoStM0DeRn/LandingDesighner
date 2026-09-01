import re
from html.parser import HTMLParser

from app.models.schemas import Section, ValidationReport


class _HTMLCheckParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[str] = []
        self.attrs: dict[str, str] = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def handle_starttag(self, tag: list[str], attrs: list[tuple[str, str | None]]):
        self.tags.append(tag)
        for key, val in attrs:
            if key == "name" and val == "description":
                self.attrs["meta_description"] = "true"
            if key == "property" and val and "og:" in val:
                self.attrs[val] = "true"


def validate_html(html: str, sections: list[Section] | None = None) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if not html or len(html) < 50:
        return ValidationReport(valid=False, errors=["HTML is empty or too short"])

    if "<!DOCTYPE html>" not in html and "<!doctype html>" not in html:
        warnings.append("Missing DOCTYPE declaration")

    if "<title>" not in html and "<title " not in html:
        errors.append("Missing <title> tag")

    if 'charset="UTF-8"' not in html and "charset='UTF-8'" not in html and "charset=UTF-8" not in html:
        warnings.append("Missing charset declaration")

    if 'name="viewport"' not in html:
        warnings.append("Missing viewport meta tag")

    if 'name="description"' not in html:
        warnings.append("Missing meta description (SEO)")

    if 'property="og:title"' not in html:
        warnings.append("Missing Open Graph title tag (SEO)")

    try:
        parser = _HTMLCheckParser()
        parser.feed(html)
    except Exception as e:
        errors.append(f"HTML parsing error: {e}")

    if sections:
        section_types = {s.type.value for s in sections}
        for st in section_types:
            if f'id="{st}"' not in html and f'class=".*{st}' not in html:
                pass

    colors = re.findall(r"#[0-9a-fA-F]{3,8}", html)
    for color in colors:
        if len(color) not in (4, 5, 7, 9):
            warnings.append(f"Unusual color format: {color}")

    return ValidationReport(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
