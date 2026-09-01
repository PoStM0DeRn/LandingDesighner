import json
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

STYLE_PREFIXES = {
    "photo": "professional photography, sharp focus, high resolution, ",
    "illustration": "digital illustration, vibrant colors, clean lines, ",
    "3d_render": "3D render, octane render, cinema 4D, realistic lighting, ",
    "watercolor": "watercolor painting, soft edges, artistic, ",
    "oil_painting": "oil painting, classical art, rich textures, ",
    "digital_art": "digital art, concept art, artstation, ",
}

PROMPT_NODE_TYPES = {"CLIPTextEncode"}
LATENT_NODE_TYPES = {"EmptyLatentImage", "EmptySD3LatentImage"}
SAMPLER_NODE_TYPES = {"KSampler"}

UI_SKIP_TYPES = {"MarkdownNote", "Note", "PrimitiveNode"}
REROUTE_TYPE = "Reroute"
SUBGRAPH_INPUT_ID = -10
SUBGRAPH_OUTPUT_ID = -20


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_workflow_template(workflow_path: str | None = None) -> dict:
    path = None
    if workflow_path:
        p = Path(workflow_path)
        if p.exists():
            path = p
        else:
            logger.warning("Custom workflow not found: %s, using default", workflow_path)
    if path is None and settings.comfyui_workflow_path:
        p = Path(settings.comfyui_workflow_path)
        if p.exists():
            path = p
        else:
            logger.warning("Configured workflow not found: %s, using default", settings.comfyui_workflow_path)
    if path is None:
        default = settings.workflows_dir / "txt2img.json"
        if default.exists():
            path = default
    if path is None:
        return _build_default_workflow()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Invalid workflow JSON (%s): %s", path, e)
        return _build_default_workflow()
    return normalize_workflow(data)


def normalize_workflow(data) -> dict:
    """Accept both ComfyUI API format and UI format, return clean API format."""
    if not isinstance(data, dict):
        return _build_default_workflow()

    if _is_api_format(data):
        clean = {
            k: v for k, v in data.items()
            if isinstance(v, dict) and "class_type" in v and isinstance(v.get("inputs"), dict)
        }
        return clean if clean else _build_default_workflow()

    try:
        converted = convert_ui_to_api(data)
        if converted:
            logger.info("Converted UI-format workflow to API format (%d nodes)", len(converted))
            return converted
    except Exception as e:
        logger.warning("UI workflow conversion failed: %s", e)
    return _build_default_workflow()


def _is_api_format(data: dict) -> bool:
    return any(isinstance(v, dict) and "class_type" in v for v in data.values())


# ---------------------------------------------------------------------------
# UI format -> API format conversion
# ---------------------------------------------------------------------------

def _named_widgets(node: dict) -> dict:
    named = node.get("widgets_values_named")
    if isinstance(named, dict):
        return {k: v for k, v in named.items() if k != "control_after_generate"}
    return {}


def _link_map(links) -> dict:
    """Normalize both list-style and dict-style link entries to {id: (origin_id, slot)}."""
    result = {}
    for l in links or []:
        if isinstance(l, list) and len(l) >= 3:
            result[l[0]] = (str(l[1]), l[2])
        elif isinstance(l, dict):
            result[l.get("id")] = (str(l.get("origin_id")), l.get("origin_slot", 0))
    return result


def convert_ui_to_api(ui: dict) -> dict:
    nodes = [n for n in ui.get("nodes") or [] if isinstance(n, dict)]
    node_by_id = {str(n.get("id")): n for n in nodes}
    subgraph_defs = {
        sg.get("id"): sg
        for sg in ((ui.get("definitions") or {}).get("subgraphs") or [])
        if isinstance(sg, dict) and sg.get("id")
    }
    tlinks = _link_map(ui.get("links"))

    api: dict = {}
    subgraph_outputs: dict[str, tuple[str, int]] = {}

    def resolve_top(origin_id: str, slot: int, depth: int = 0) -> tuple[str, int] | None:
        if depth < 16:
            node = node_by_id.get(origin_id)
            if node is not None and node.get("type") == REROUTE_TYPE:
                for inp in node.get("inputs") or []:
                    lid = inp.get("link")
                    if lid is not None and lid in tlinks:
                        oid, oslot = tlinks[lid]
                        resolved = resolve_top(oid, oslot, depth + 1)
                        if resolved:
                            return resolved
                return None
        out = subgraph_outputs.get(origin_id)
        if out:
            return out
        return origin_id, slot

    def flatten_subgraph(instance: dict) -> None:
        inst_id = str(instance.get("id"))
        sg = subgraph_defs.get(instance.get("type"))
        if sg is None:
            return

        inst_named = _named_widgets(instance)
        positional = instance.get("widgets_values") if isinstance(instance.get("widgets_values"), list) else []
        sg_inputs = sg.get("inputs") or []
        sg_input_values: dict[int, object] = {}
        for i, sgi in enumerate(sg_inputs):
            name = sgi.get("name")
            if name in inst_named:
                sg_input_values[i] = inst_named[name]
            elif i < len(positional):
                sg_input_values[i] = positional[i]

        slinks = _link_map(sg.get("links"))
        input_node_id = str((sg.get("inputNode") or {}).get("id", SUBGRAPH_INPUT_ID))
        output_node_id = str((sg.get("outputNode") or {}).get("id", SUBGRAPH_OUTPUT_ID))

        # The subgraph's output is the source of the link that targets outputNode (-20)
        for l in sg.get("links") or []:
            if isinstance(l, dict):
                if str(l.get("target_id")) == output_node_id:
                    subgraph_outputs[inst_id] = (f"{inst_id}:{l.get('origin_id')}", l.get("origin_slot", 0))
                    break
            elif isinstance(l, list) and len(l) >= 4 and str(l[3]) == output_node_id:
                subgraph_outputs[inst_id] = (f"{inst_id}:{l[1]}", l[2])
                break

        for internal in sg.get("nodes") or []:
            if not isinstance(internal, dict):
                continue
            itype = internal.get("type")
            if itype in UI_SKIP_TYPES or itype in subgraph_defs:
                logger.warning("Skipping unsupported node %s in subgraph", itype)
                continue
            if internal.get("mode") not in (0, None):
                continue
            api_id = f"{inst_id}:{internal.get('id')}"
            inputs: dict = {}
            for inp in internal.get("inputs") or []:
                lid = inp.get("link")
                if lid is None:
                    continue
                res = slinks.get(lid)
                if not res:
                    continue
                oid, oslot = res
                if oid == input_node_id:
                    val = sg_input_values.get(oslot)
                    if val is not None:
                        inputs[inp["name"]] = val
                else:
                    inputs[inp["name"]] = [f"{inst_id}:{oid}", oslot]
            for k, v in _named_widgets(internal).items():
                inputs.setdefault(k, v)
            api[api_id] = {
                "class_type": itype,
                "inputs": inputs,
                "_meta": {"title": internal.get("title") or itype},
            }

    for node in nodes:
        if node.get("type") in subgraph_defs:
            flatten_subgraph(node)

    for node in nodes:
        ntype = node.get("type")
        nid = str(node.get("id"))
        if ntype in subgraph_defs or ntype in UI_SKIP_TYPES:
            continue
        if node.get("mode") not in (0, None):
            continue
        inputs: dict = {}
        for inp in node.get("inputs") or []:
            lid = inp.get("link")
            if lid is None:
                continue
            res = tlinks.get(lid)
            if not res:
                continue
            resolved = resolve_top(res[0], res[1])
            if resolved:
                inputs[inp["name"]] = [resolved[0], resolved[1]]
        for k, v in _named_widgets(node).items():
            inputs.setdefault(k, v)
        api[nid] = {
            "class_type": ntype,
            "inputs": inputs,
            "_meta": {"title": node.get("title") or ntype},
        }

    return api


# ---------------------------------------------------------------------------
# Parameter injection
# ---------------------------------------------------------------------------

def build_txt2img_workflow(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    seed: int = -1,
    style: str = "photo",
    negative_prompt: str | None = None,
    checkpoint: str | None = None,
    workflow_path: str | None = None,
) -> dict:
    # Snap to multiples of 64 — required for valid SD3-family latents
    width = max(256, int(round(width / 64)) * 64)
    height = max(256, int(round(height / 64)) * 64)

    style_prefix = STYLE_PREFIXES.get(style, "")
    full_prompt = style_prefix + prompt

    if negative_prompt is None:
        negative_prompt = settings.image_negative_prompt

    workflow = load_workflow_template(workflow_path)

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        node_class = node.get("class_type", "")
        inputs = node.get("inputs", {})

        if node_class in PROMPT_NODE_TYPES:
            if "text" in inputs:
                inputs["text"] = full_prompt

        elif node_class in LATENT_NODE_TYPES:
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height

        elif node_class in SAMPLER_NODE_TYPES:
            # Only prompt, dimensions, seed and steps are injected.
            # cfg, sampler, scheduler etc. are model-specific and stay as authored in the workflow.
            if "steps" in inputs:
                inputs["steps"] = steps
            if "seed" in inputs and seed >= 0:
                inputs["seed"] = seed

    return workflow


def _build_default_workflow() -> dict:
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": settings.comfyui_model or "model.safetensors"},
            "_meta": {"title": "Load Checkpoint"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["1", 1]},
            "_meta": {"title": "Positive Prompt"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": settings.image_negative_prompt, "clip": ["1", 1]},
            "_meta": {"title": "Negative Prompt"},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
            "_meta": {"title": "Empty Latent Image"},
        },
        "5": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["7", 0], "vae": ["1", 2]},
            "_meta": {"title": "VAE Decode"},
        },
        "6": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "landing", "images": ["5", 0]},
            "_meta": {"title": "Save Image"},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
            "_meta": {"title": "KSampler"},
        },
    }
