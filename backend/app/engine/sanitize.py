"""Allowlist HTML sanitizer for LLM-generated section markup.

LLMs write raw HTML for sections. Before it can touch the assembled page we
strip everything dangerous: scripts, styles, iframes, event handlers and
javascript: URLs. Unknown tags are unwrapped (children kept), stripped tags
lose their content, the output is always balanced.
"""
import html as html_module
from html.parser import HTMLParser

STRIP_TAGS = {"script", "style", "iframe", "object", "embed", "noscript"}

ALLOWED_TAGS = {
    "section", "div", "header", "footer", "nav", "main", "article", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "span", "a", "img", "br", "hr",
    "ul", "ol", "li",
    "button", "strong", "em", "b", "i", "small", "sub", "sup",
    "figure", "figcaption", "blockquote",
    "svg", "path", "circle", "rect", "line", "g", "polygon", "polyline", "defs", "title",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th",
    "label", "input", "textarea",
}

VOID_TAGS = {"img", "br", "hr", "input"}

ALLOWED_ATTRS = {
    "class", "id", "href", "src", "alt", "title", "target", "rel", "aria-label",
    "aria-hidden", "role", "width", "height", "colspan", "rowspan", "placeholder",
    "name", "type", "value", "checked", "disabled", "loading",
    # svg
    "viewbox", "fill", "fill-rule", "clip-rule", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset",
    "stroke-opacity", "fill-opacity", "opacity", "d", "xmlns", "cx", "cy", "r", "rx",
    "ry", "x", "y", "x1", "x2", "y1", "y2", "points", "transform",
    "preserveAspectRatio", "version",
}

URL_ATTRS = {"href", "src"}
BLOCKED_SCHEMES = ("javascript:", "vbscript:", "data:text/html")


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open_tags: list[str] = []
        self.skip_depth = 0

    # -- helpers ----------------------------------------------------------
    def _render_attrs(self, attrs: list[tuple[str, str | None]]) -> str:
        parts = []
        for key, value in attrs:
            key = key.lower()
            if key.startswith("on") or key not in ALLOWED_ATTRS:
                continue
            if key in URL_ATTRS and value:
                v = value.strip().lower()
                if v.startswith(BLOCKED_SCHEMES):
                    continue
            if value is None:
                parts.append(f" {key}")
            else:
                parts.append(f' {key}="{html_module.escape(value, quote=True)}"')
        return "".join(parts)

    # -- parser callbacks --------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.skip_depth:
            if tag in STRIP_TAGS:
                self.skip_depth += 1
            return
        if tag in STRIP_TAGS:
            self.skip_depth = 1
            return
        if tag not in ALLOWED_TAGS:
            return  # unwrap: children are kept
        if tag in VOID_TAGS:
            self.out.append(f"<{tag}{self._render_attrs(attrs)}>")
            return
        self.out.append(f"<{tag}{self._render_attrs(attrs)}>")
        self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self.skip_depth:
            return
        if tag in STRIP_TAGS or tag not in ALLOWED_TAGS:
            return
        if tag in VOID_TAGS:
            self.out.append(f"<{tag}{self._render_attrs(attrs)}>")
        else:
            # expand self-closing to open+close so the stack stays balanced
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip_depth:
            if tag in STRIP_TAGS:
                self.skip_depth -= 1
            return
        if tag in self.open_tags:
            # close inner unclosed tags to keep output balanced
            while self.open_tags:
                open_tag = self.open_tags.pop()
                self.out.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.out.append(html_module.escape(data, quote=False))

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def close(self):
        super().close()
        while self.open_tags:  # balance leftover tags
            self.out.append(f"</{self.open_tags.pop()}>")


def sanitize_html(raw: str) -> str:
    """Sanitize an LLM-generated HTML fragment. Returns balanced, safe HTML."""
    parser = _Sanitizer()
    try:
        parser.feed(raw or "")
        parser.close()
    except Exception:
        return ""
    return "".join(parser.out)
