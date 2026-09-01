from app.engine.sanitize import sanitize_html
from app.engine.assembler import assemble_html, ensure_section_id
from app.models.schemas import DesignTokens, Section, SectionType


class TestSanitizer:
    def test_strips_script_with_content(self):
        dirty = '<section><p>ok</p><script>alert("x")</script></section>'
        clean = sanitize_html(dirty)
        assert "script" not in clean and "alert" not in clean
        assert "<p>ok</p>" in clean

    def test_strips_style_and_iframe(self):
        clean = sanitize_html('<div><style>.x{}</style><iframe src="http://e"></iframe><b>t</b></div>')
        assert "style" not in clean and "iframe" not in clean
        assert "<b>t</b>" in clean

    def test_removes_event_handlers(self):
        clean = sanitize_html('<button onclick="steal()" onmouseover="x()">Go</button>')
        assert "onclick" not in clean and "onmouseover" not in clean
        assert "<button>Go</button>" in clean

    def test_blocks_javascript_urls(self):
        clean = sanitize_html('<a href="javascript:alert(1)">link</a>')
        assert "javascript:" not in clean

    def test_keeps_data_image_src(self):
        uri = "data:image/png;base64,AAAA"
        clean = sanitize_html(f'<img src="{uri}" alt="x">')
        assert 'src="data:image/png;base64,AAAA"' in clean

    def test_keeps_classes_and_svg(self):
        dirty = (
            '<section class="py-20 bg-primary"><svg viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2"><path d="M4 12h16"/></svg></section>'
        )
        clean = sanitize_html(dirty)
        assert 'class="py-20 bg-primary"' in clean
        assert 'viewBox="0 0 24 24"' in clean.lower() or 'viewbox="0 0 24 24"' in clean
        assert "<path" in clean

    def test_unwraps_unknown_tags_keeps_children(self):
        clean = sanitize_html('<section><weird-tag><p>kept</p></weird-tag></section>')
        assert "weird-tag" not in clean
        assert "<p>kept</p>" in clean

    def test_balances_unclosed_tags(self):
        clean = sanitize_html('<section><div><p>text')
        assert clean.count("<section") == clean.count("</section>")
        assert clean.count("<div") == clean.count("</div>")

    def test_escapes_text_injection(self):
        clean = sanitize_html("<p>&lt;script&gt;boom&lt;/script&gt;</p>")
        assert "<script>" not in clean
        assert "boom" in clean


class TestGenerateSectionMarkup:
    def _make_section(self) -> Section:
        return Section(
            type=SectionType.hero,
            title="Hero title",
            subtitle="Sub",
            description="Desc",
            image_url="data:image/webp;base64,QUJD",
            button_text="Go",
            button_url="#go",
        )

    def test_good_markup_sanitized_and_substituted(self, monkeypatch):
        import app.engine.content as content

        def fake_llm(messages, **kwargs):
            return (
                "```html\n<section class=\"relative py-24\"><img src=\"__IMAGE__\" alt=\"bg\">"
                "<h1 class=\"font-heading text-5xl\">Hero title</h1>"
                "<script>alert(1)</script></section>\n```"
            )

        monkeypatch.setattr(content, "chat_completion", fake_llm)
        html = content.generate_section_markup(self._make_section(), DesignTokens())
        assert html is not None
        assert 'src="data:image/webp;base64,QUJD"' in html
        assert "script" not in html
        assert "Hero title" in html
        assert "font-heading" in html

    def test_no_section_tag_returns_none(self, monkeypatch):
        import app.engine.content as content

        monkeypatch.setattr(content, "chat_completion", lambda m, **k: "<div>just a div</div>")
        assert content.generate_section_markup(self._make_section(), DesignTokens()) is None

    def test_llm_exception_propagates(self, monkeypatch):
        import app.engine.content as content

        def boom(m, **k):
            raise RuntimeError("LLM down")

        monkeypatch.setattr(content, "chat_completion", boom)
        try:
            content.generate_section_markup(self._make_section(), DesignTokens())
            raised = False
        except RuntimeError:
            raised = True
        assert raised

    def test_sanitizer_garbage_returns_none(self, monkeypatch):
        import app.engine.content as content

        monkeypatch.setattr(content, "chat_completion", lambda m, **k: "<section></section>")
        assert content.generate_section_markup(self._make_section(), DesignTokens()) is None

    def test_items_image_placeholders(self, monkeypatch):
        import app.engine.content as content

        section = Section(
            type=SectionType.features,
            title="F",
            items=[
                {"title": "A", "description": "a", "image_url": "data:image/png;base64,AAA1"},
                {"title": "B", "description": "b"},
            ],
        )

        def fake_llm(messages, **kwargs):
            return '<section><img src="__ITEM_IMAGE_0__"><h2>F</h2></section>'

        monkeypatch.setattr(content, "chat_completion", fake_llm)
        html = content.generate_section_markup(section, DesignTokens())
        assert html is not None
        assert 'src="data:image/png;base64,AAA1"' in html
        assert "__ITEM_IMAGE_0__" not in html


class TestAssemblerSectionsHtml:
    def test_fallback_for_none_entries(self):
        sections = [
            Section(type=SectionType.hero, title="H"),
            Section(type=SectionType.cta, title="C"),
        ]
        html = assemble_html("T", sections, DesignTokens(), sections_html=[None, None])
        assert 'id="hero"' in html and 'id="cta"' in html

    def test_llm_markup_used_with_id_injection(self):
        sections = [Section(type=SectionType.hero, title="H")]
        llm = '<section class="relative py-24"><h1>H</h1></section>'
        html = assemble_html("T", sections, DesignTokens(), sections_html=[llm])
        assert 'id="hero"' in html
        assert "py-24" in html

    def test_wraps_when_no_section_tag(self):
        sections = [Section(type=SectionType.cta, title="C")]
        llm = '<div class="py-10"><h2>C</h2></div>'
        html = assemble_html("T", sections, DesignTokens(), sections_html=[llm])
        assert '<section id="cta"' in html and "</section>" in html

    def test_id_not_duplicated(self):
        sections = [Section(type=SectionType.hero, title="H")]
        llm = '<section id="hero" class="x"><h1>H</h1></section>'
        html = assemble_html("T", sections, DesignTokens(), sections_html=[llm])
        assert html.count('id="hero"') == 1


class TestOrchestratorWiring:
    def test_graph_compiles_with_markup_node(self):
        from app.core.orchestrator import graph

        # compiled graph must be invokable object with nodes registered
        assert graph is not None
        from app.core.orchestrator import node_generate_markup
        assert callable(node_generate_markup)

    def test_node_skips_when_disabled(self):
        from app.core.orchestrator import node_generate_markup

        state = {"error": None, "use_llm_markup": False, "sections": [], "design_tokens": DesignTokens()}
        assert node_generate_markup(state) == {}
