"""Provider presets: default base URLs and short known-quirk hints."""

from __future__ import annotations

import fnmatch
from typing import Dict, List, Optional, Tuple

# (probe_id_glob, hint) — attached only on FAIL/WARN when the glob matches.
Preset = Dict[str, object]

PRESETS: Dict[str, Preset] = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "hints": [
            ("tools.*", "Ollama OpenAI-compat tool calling is often buggy (ollama#11621)"),
            ("stream.tools*", "Ollama may emit tool markup as streamed content"),
        ],
    },
    "vllm": {
        "base_url": "http://localhost:8000/v1",
        "hints": [
            ("tools.choice_*", "vLLM tool_choice support varies by version/backend"),
            ("stream.tools*", "vLLM streaming+tools has known breakage (vllm#22403)"),
            ("tools.no_parallel", "vLLM may ignore or reject parallel_tool_calls"),
        ],
    },
    "llamacpp": {
        "base_url": "http://localhost:8080/v1",
        "hints": [
            ("tools.*", "llama.cpp needs --jinja; templates often leak or drop tool results (llama.cpp#15012)"),
            ("tools.clean_content", "chat template leak: enable --jinja and a tools-capable template"),
            ("tools.choice_*", "named/required tool_choice depends on the Jinja chat template"),
        ],
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "hints": [
            ("tools.*", "LM Studio tool support depends on the loaded model and prompt template"),
            ("tools.no_parallel", "LM Studio may not honour parallel_tool_calls yet"),
        ],
    },
    "sglang": {
        "base_url": "http://localhost:30000/v1",
        "hints": [
            ("tools.choice_*", "SGLang tool_choice coverage depends on backend version"),
            ("tools.no_parallel", "SGLang may ignore parallel_tool_calls=false"),
        ],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "hints": [
            ("tools.*", "OpenRouter forwards to the upstream model; failures are often upstream quirks"),
            ("errors.bad_model", "OpenRouter returns its own error shape for unknown model ids"),
        ],
    },
    "litellm": {
        "base_url": "http://localhost:4000/v1",
        "hints": [
            ("tools.*", "LiteLLM proxies upstream; check the backing provider when tools fail"),
            ("anthropic.*", "LiteLLM Anthropic mapping depends on the configured model route"),
        ],
    },
}

PRESET_NAMES = tuple(PRESETS.keys())


def default_base_url(name: str) -> str:
    return str(PRESETS[name]["base_url"])


def quirk_hint(preset: Optional[str], probe_id: str) -> Optional[str]:
    """Return a short known-quirk hint for this preset+probe, or None."""
    if not preset or preset not in PRESETS:
        return None
    hints: List[Tuple[str, str]] = PRESETS[preset].get("hints") or []  # type: ignore[assignment]
    for pat, text in hints:
        if fnmatch.fnmatch(probe_id, pat):
            return text
    return None
