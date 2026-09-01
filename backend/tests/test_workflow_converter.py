from pathlib import Path

from app.mcp.workflow import (
    build_txt2img_workflow,
    load_workflow_template,
    normalize_workflow,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
UI_FIXTURE = Path(__file__).parent / "fixtures" / "ui_workflow.json"
API_TEMPLATE = PROJECT_ROOT / "templates" / "workflows" / "txt2img.json"


def _is_valid_api(wf) -> bool:
    return (
        isinstance(wf, dict)
        and bool(wf)
        and all(
            isinstance(v, dict) and "class_type" in v and isinstance(v.get("inputs"), dict)
            for v in wf.values()
        )
    )


class TestUIFormatConversion:
    """The UI-format export must convert to a valid API workflow (regression:
    raw UI format crashed ComfyUI with 'argument of type int is not iterable')."""

    def test_converts_ui_fixture(self):
        wf = load_workflow_template(str(UI_FIXTURE))
        assert _is_valid_api(wf)
        # subgraph flattened with instance-id prefix
        assert "57:27" in wf  # CLIPTextEncode (positive prompt)
        assert "57:13" in wf  # EmptySD3LatentImage
        assert "57:3" in wf   # KSampler
        assert "9" in wf      # SaveImage

    def test_subgraph_output_resolution(self):
        wf = load_workflow_template(str(UI_FIXTURE))
        assert wf["9"]["inputs"]["images"] == ["57:8", 0]

    def test_subgraph_inputs_from_instance_widgets(self):
        wf = load_workflow_template(str(UI_FIXTURE))
        assert wf["57:28"]["inputs"]["unet_name"] == "z_image_turbo_bf16.safetensors"
        assert wf["57:30"]["inputs"]["clip_name"] == "qwen_3_4b.safetensors"
        assert wf["57:29"]["inputs"]["vae_name"] == "ae.safetensors"

    def test_sampler_params_from_internal_widgets(self):
        wf = load_workflow_template(str(UI_FIXTURE))
        ks = wf["57:3"]["inputs"]
        assert ks["sampler_name"] == "res_multistep"
        assert ks["scheduler"] == "simple"
        assert ks["cfg"] == 1

    def test_no_ui_junk_keys_in_output(self):
        wf = load_workflow_template(str(UI_FIXTURE))
        assert "revision" not in wf
        assert "nodes" not in wf
        assert "definitions" not in wf


class TestNormalize:
    def test_api_format_sanitized(self):
        api = {
            "1": {"class_type": "KSampler", "inputs": {"seed": 1}},
            "junk_int": 5,
            "junk_str": "hello",
            "junk_list": [1, 2],
        }
        wf = normalize_workflow(api)
        assert list(wf.keys()) == ["1"]

    def test_malformed_ui_returns_default(self):
        wf = normalize_workflow({"id": "abc", "revision": 0, "last_node_id": 61, "nodes": [], "links": []})
        assert _is_valid_api(wf)

    def test_none_is_safe(self):
        assert _is_valid_api(normalize_workflow(None))

    def test_invalid_json_falls_back(self, tmp_path, no_custom_workflow):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert _is_valid_api(load_workflow_template(str(bad)))

    def test_missing_path_falls_back(self, no_custom_workflow):
        assert _is_valid_api(load_workflow_template("Z:/definitely/missing.json"))


class TestParamInjection:
    def test_injects_prompt_size_steps_seed(self):
        wf = build_txt2img_workflow(
            prompt="a red apple",
            width=1024, height=576, steps=8, seed=42, style="photo",
            workflow_path=str(API_TEMPLATE),
        )
        assert wf["57:27"]["inputs"]["text"].endswith("a red apple")
        assert wf["57:13"]["inputs"]["width"] == 1024
        assert wf["57:13"]["inputs"]["height"] == 576
        assert wf["57:3"]["inputs"]["steps"] == 8
        assert wf["57:3"]["inputs"]["seed"] == 42

    def test_cfg_is_never_overwritten(self):
        wf = build_txt2img_workflow("x", steps=8, workflow_path=str(API_TEMPLATE))
        assert wf["57:3"]["inputs"]["cfg"] == 1

    def test_sampler_scheduler_preserved(self):
        wf = build_txt2img_workflow("x", workflow_path=str(API_TEMPLATE))
        assert wf["57:3"]["inputs"]["sampler_name"] == "res_multistep"
        assert wf["57:3"]["inputs"]["scheduler"] == "simple"

    def test_seed_minus_one_keeps_workflow_value(self):
        wf = build_txt2img_workflow("x", seed=-1, workflow_path=str(API_TEMPLATE))
        assert wf["57:3"]["inputs"]["seed"] == 569840199374168

    def test_dimension_snapping_to_64(self):
        wf = build_txt2img_workflow("x", width=1200, height=600, workflow_path=str(API_TEMPLATE))
        assert wf["57:13"]["inputs"]["width"] == 1216
        assert wf["57:13"]["inputs"]["height"] == 576

    def test_min_dimension_256(self):
        wf = build_txt2img_workflow("x", width=10, height=10, workflow_path=str(API_TEMPLATE))
        assert wf["57:13"]["inputs"]["width"] == 256
        assert wf["57:13"]["inputs"]["height"] == 256

    def test_style_prefix_applied(self):
        wf = build_txt2img_workflow("a cat", style="illustration", workflow_path=str(API_TEMPLATE))
        assert wf["57:27"]["inputs"]["text"].startswith("digital illustration")
