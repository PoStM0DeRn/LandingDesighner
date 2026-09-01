import logging
import re
from pathlib import Path
from jinja2 import Template

from app.models.schemas import Section, SectionType, DesignTokens
from app.engine.images import get_icon_svg, get_testimonial_avatar

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "templates"


def ensure_section_id(section: Section, html: str) -> str:
    """Guarantee id="{type}" on the section so nav anchors and JS keep working."""
    wanted = f'id="{section.type.value}"'
    if wanted in html:
        return html
    m = re.search(r"<section\b([^>]*)>", html, re.IGNORECASE)
    if m:
        return html[: m.end() - 1] + f" {wanted}" + html[m.end() - 1:]
    return f'<section id="{section.type.value}">{html}</section>'


def _render_section(section: Section, tokens: DesignTokens) -> str:
    renderers = {
        SectionType.hero: _hero,
        SectionType.features: _features,
        SectionType.about: _about,
        SectionType.services: _services,
        SectionType.testimonials: _testimonials,
        SectionType.pricing: _pricing,
        SectionType.faq: _faq,
        SectionType.cta: _cta,
        SectionType.footer: _footer,
    }
    renderer = renderers.get(section.type)
    if renderer:
        return renderer(section, tokens)
    return ""


def _hero(s: Section, t: DesignTokens) -> str:
    img_html = ""
    if s.image_url:
        img_html = f'<img src="{s.image_url}" alt="{s.title}" class="absolute inset-0 w-full h-full object-cover" />'
    else:
        img_html = f'<div class="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent"></div>'

    return f"""
  <section id="hero" class="relative overflow-hidden py-24 sm:py-32 min-h-[70vh] flex items-center">
    {img_html}
    <div class="absolute inset-0 bg-black/40"></div>
    <div class="relative mx-auto max-w-4xl px-6 text-center lg:px-8 z-10">
      <h1 class="font-heading text-4xl font-bold tracking-tight sm:text-6xl text-white drop-shadow-lg">{s.title}</h1>
      {"<p class='mt-6 text-lg leading-8 text-white/90 max-w-2xl mx-auto drop-shadow'>" + s.subtitle + "</p>" if s.subtitle else ""}
      {"<p class='mt-6 text-lg leading-8 text-white/80 max-w-2xl mx-auto drop-shadow'>" + s.description + "</p>" if s.description else ""}
      {"<div class='mt-10 flex items-center justify-center gap-x-6'><a href='" + s.button_url + "' class='rounded-md bg-primary px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 transition'>" + s.button_text + "</a></div>" if s.button_text else ""}
    </div>
  </section>"""


def _features(s: Section, t: DesignTokens) -> str:
    items = ""
    for item in s.items:
        icon_name = item.get("icon", "star")
        svg = get_icon_svg(icon_name) if not icon_name.startswith("http") and len(icon_name) < 20 else f'<span class="text-3xl">{icon_name}</span>'
        title = item.get("title", "")
        desc = item.get("description", "")
        img = item.get("image_url", "")
        img_html = f'<img src="{img}" alt="{title}" class="w-full h-40 object-cover rounded-xl mb-4" />' if img else ""
        items += f"""
      <div class="relative rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-200/50">
        {img_html}
        <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary mb-4">{svg}</div>
        <h3 class="font-heading text-lg font-semibold">{title}</h3>
        <p class="mt-2 text-gray-600 text-sm leading-relaxed">{desc}</p>
      </div>"""
    cols = "md:grid-cols-2 lg:grid-cols-3" if len(s.items) > 3 else "md:grid-cols-2" if len(s.items) > 1 else ""
    return f"""
  <section id="features" class="py-20 sm:py-28">
    <div class="mx-auto max-w-7xl px-6 lg:px-8">
      <div class="mx-auto max-w-2xl text-center">
        <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl">{s.title}</h2>
        {"<p class='mt-4 text-lg text-gray-600'>" + s.description + "</p>" if s.description else ""}
      </div>
      <div class="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 {cols} lg:max-w-none">
{items}
      </div>
    </div>
  </section>"""


def _about(s: Section, t: DesignTokens) -> str:
    img_html = ""
    if s.image_url:
        img_html = f'<img src="{s.image_url}" alt="{s.title}" class="w-full rounded-2xl shadow-lg" />'
    return f"""
  <section id="about" class="py-20 sm:py-28">
    <div class="mx-auto max-w-7xl px-6 lg:px-8">
      <div class="mx-auto max-w-2xl">
        <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl">{s.title}</h2>
        <p class="mt-6 text-lg leading-8 text-gray-600">{s.description}</p>
      </div>
      {"<div class='mt-8'>" + img_html + "</div>" if img_html else ""}
    </div>
  </section>"""


def _services(s: Section, t: DesignTokens) -> str:
    items = ""
    for item in s.items:
        icon_name = item.get("icon", "layers")
        svg = get_icon_svg(icon_name) if not icon_name.startswith("http") and len(icon_name) < 20 else f'<span class="text-2xl">{icon_name}</span>'
        title = item.get("title", "")
        desc = item.get("description", "")
        items += f"""
      <div class="flex gap-4">
        <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">{svg}</div>
        <div>
          <h3 class="font-heading font-semibold">{title}</h3>
          <p class="mt-1 text-gray-600 text-sm">{desc}</p>
        </div>
      </div>"""
    return f"""
  <section id="services" class="py-20 sm:py-28 bg-gray-50">
    <div class="mx-auto max-w-7xl px-6 lg:px-8">
      <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl text-center">{s.title}</h2>
      <div class="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 sm:grid-cols-2 lg:max-w-none">
{items}
      </div>
    </div>
  </section>"""


def _testimonials(s: Section, t: DesignTokens) -> str:
    items = ""
    for item in s.items:
        name = item.get("title", "")
        desc = item.get("description", "")
        avatar_url = item.get("image_url") or get_testimonial_avatar(name)
        items += f"""
      <div class="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-200/50">
        <p class="text-gray-600 text-sm leading-relaxed italic">"{desc}"</p>
        <div class="mt-4 flex items-center gap-3">
          <img src="{avatar_url}" alt="{name}" class="w-10 h-10 rounded-full object-cover" />
          <div class="font-heading font-semibold text-sm">{name}</div>
        </div>
      </div>"""
    return f"""
  <section id="testimonials" class="py-20 sm:py-28">
    <div class="mx-auto max-w-7xl px-6 lg:px-8">
      <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl text-center">{s.title}</h2>
      <div class="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 lg:max-w-none">
{items}
      </div>
    </div>
  </section>"""


def _pricing(s: Section, t: DesignTokens) -> str:
    items = ""
    for item in s.items:
        title = item.get("title", "")
        price = item.get("price", "")
        desc = item.get("description", "")
        btn = item.get("button_text", "Choose")
        featured = item.get("featured", False)
        ring = "ring-2 ring-primary" if featured else "ring-1 ring-gray-200/50"
        items += f"""
      <div class="rounded-2xl bg-white p-8 shadow-sm {ring} flex flex-col">
        <h3 class="font-heading font-semibold text-lg">{title}</h3>
        <div class="mt-4 text-3xl font-bold">{price}</div>
        <p class="mt-4 text-gray-600 text-sm flex-1">{desc}</p>
        <a href="#" class="mt-8 block rounded-md bg-primary px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-primary/90 transition">{btn}</a>
      </div>"""
    cols = "md:grid-cols-3" if len(s.items) == 3 else "md:grid-cols-2"
    return f"""
  <section id="pricing" class="py-20 sm:py-28">
    <div class="mx-auto max-w-7xl px-6 lg:px-8">
      <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl text-center">{s.title}</h2>
      <div class="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 {cols} lg:max-w-none items-start">
{items}
      </div>
    </div>
  </section>"""


def _faq(s: Section, t: DesignTokens) -> str:
    items = ""
    for i, item in enumerate(s.items):
        q = item.get("title", "")
        a = item.get("description", "")
        items += f"""
      <div class="border-b border-gray-200">
        <button data-faq-toggle class="w-full flex items-center justify-between py-6 text-left">
          <h3 class="font-heading font-semibold pr-4">{q}</h3>
          <svg class="faq-chevron w-5 h-5 text-gray-500 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
        </button>
        <div class="faq-answer pb-6">
          <p class="text-gray-600 text-sm">{a}</p>
        </div>
      </div>"""
    return f"""
  <section id="faq" class="py-20 sm:py-28 bg-gray-50">
    <div class="mx-auto max-w-3xl px-6 lg:px-8">
      <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl text-center">{s.title}</h2>
      <div class="mt-16">
{items}
      </div>
    </div>
  </section>"""


def _cta(s: Section, t: DesignTokens) -> str:
    return f"""
  <section id="cta" class="py-20 sm:py-28">
    <div class="mx-auto max-w-4xl px-6 text-center lg:px-8">
      <h2 class="font-heading text-3xl font-bold tracking-tight sm:text-4xl">{s.title}</h2>
      {"<p class='mt-4 text-lg text-gray-600'>" + s.description + "</p>" if s.description else ""}
      {"<div class='mt-10'><a href='" + s.button_url + "' class='rounded-md bg-primary px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 transition'>" + s.button_text + "</a></div>" if s.button_text else ""}
    </div>
  </section>"""


def _footer(s: Section, t: DesignTokens) -> str:
    links = ""
    for item in s.items:
        title = item.get("title", "")
        url = item.get("button_url", "#")
        if title:
            links += f'<a href="{url}" class="text-sm text-gray-600 hover:text-gray-900">{title}</a>\n        '
    return f"""
  <footer id="footer" class="border-t border-gray-200 py-12">
    <div class="mx-auto max-w-7xl px-6 lg:px-8">
      <div class="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <div class="font-heading font-semibold">{s.title}</div>
        <div class="flex gap-6">
          {links}
        </div>
      </div>
    </div>
  </footer>"""


def _generate_meta_description(sections: list[Section]) -> str:
    for s in sections:
        if s.type == SectionType.hero:
            if s.subtitle:
                return s.subtitle[:160]
            if s.description:
                return s.description[:160]
            if s.title:
                return s.title[:160]
    return "Generated landing page"


def compute_surface_alt(bg_color: str) -> str:
    """Secondary surface color derived from the background (used by template + tailwind config)."""
    return "#f8f9fa" if bg_color.lower() in ("#ffffff", "#fff", "white") else "#1a1a2e"


def assemble_html(
    title: str,
    sections: list[Section],
    tokens: DesignTokens,
    sections_html: list[str | None] | None = None,
) -> str:
    """Assemble the final page. When sections_html is provided (LLM-generated
    markup), those are used; None entries fall back to built-in renderers."""
    if sections_html:
        parts = []
        for s, markup in zip(sections, sections_html):
            if markup:
                parts.append(ensure_section_id(s, markup))
            else:
                parts.append(_render_section(s, tokens))
        content = "\n".join(parts)
    else:
        content_parts = [_render_section(s, tokens) for s in sections]
        content = "\n".join(content_parts)

    bg = tokens.bg_color
    surface_alt = compute_surface_alt(bg)

    meta_description = _generate_meta_description(sections)

    template_path = TEMPLATE_DIR / "landing.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.render(
        title=title,
        meta_description=meta_description,
        heading_font=tokens.heading_font.replace(" ", "+"),
        body_font=tokens.body_font.replace(" ", "+"),
        primary_color=tokens.primary_color,
        secondary_color=tokens.secondary_color,
        accent_color=tokens.accent_color,
        bg_color=bg,
        text_color=tokens.text_color,
        border_radius=tokens.border_radius,
        surface_alt=surface_alt,
        content=content,
    )
