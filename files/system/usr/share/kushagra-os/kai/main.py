#!/usr/bin/env python3
"""Kushagra OS K-AI Wayland Side Drawer Qt6/QML Application.

Features:
- Live Model Tier Badge from `/usr/bin/k-ai-detect --json`
- Live engine status & idle RAM (`0 MB`) from `http://127.0.0.1:11435/v1/status`
- Multilingual Hindi / Hinglish / English UI & conversation support
- Interactive Action Confirmation Cards validated read-only against
  `/usr/share/kushagra-os/kai/actions.json`, executed ONLY on explicit user
  button click via `/usr/libexec/k-ai-broker --approved`
- Explicit user-triggered Screen OCR (`k-ai-ocr --json`) & KWallet API Key dialog
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QObject,
    QSize,
    QSocketNotifier,
    QThread,
    QTimer,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QGuiApplication, QWindow
from PyQt6.QtQml import QQmlApplicationEngine

ENGINE_BASE_URL = "http://127.0.0.1:11435"
ACTIONS_JSON_PATH = Path("/usr/share/kushagra-os/kai/actions.json")
MAX_HISTORY_TURNS = 12

ACTION_PRESETS = {
    "translate": (
        "Translate the following context cleanly. If it is in English, translate to natural "
        "Hindi (Devanagari). If it is in Hindi or Hinglish, translate to clear English."
    ),
    "summarize": "Provide a concise bulleted summary of the following context.",
    "fix_grammar": (
        "Fix grammar, spelling, and clarity in the following text, then briefly list the key fixes."
    ),
    "explain_code": (
        "Explain clearly step-by-step what the following code, command, or error means and how to handle it."
    ),
}

SLASH_ALIAS_HINTS = {
    "dns": ("kavach_dns", "dns", "set_dns"),
    "glass": ("glass_toggle", "glass", "kwin_glass"),
    "layout": ("layout_switch", "layout", "desktop_layout"),
    "scan": ("kavach_scan", "scan", "clamscan"),
    "convert": ("resolve_convert", "convert", "doc_convert"),
    "health": ("health_report", "health", "health_check"),
    "windows": ("reboot_windows", "windows", "winrun"),
}


def load_actions_registry(path: Path = ACTIONS_JSON_PATH) -> tuple[dict[str, dict[str, Any]], str]:
    """Read /usr/share/kushagra-os/kai/actions.json read-only into a canonical map."""
    if not path.is_file():
        return {}, f"Action registry not found at {path}"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"Failed to parse {path}: {exc}"

    entries: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        container = raw.get("actions", raw)
        if isinstance(container, dict):
            for key, val in container.items():
                if key in ("version", "schema", "$schema", "description") and not isinstance(val, dict):
                    continue
                if isinstance(val, dict):
                    spec = dict(val)
                    spec.setdefault("id", str(key))
                    entries[str(key)] = spec
        elif isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    aid = str(item.get("id") or item.get("name") or item.get("action") or "").strip()
                    if aid:
                        spec = dict(item)
                        spec.setdefault("id", aid)
                        entries[aid] = spec
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                aid = str(item.get("id") or item.get("name") or item.get("action") or "").strip()
                if aid:
                    spec = dict(item)
                    spec.setdefault("id", aid)
                    entries[aid] = spec

    return entries, ""


def _resolve_registry_action(name: str, registry: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    """Resolve an action name or slash command strictly against loaded registry."""
    if not registry:
        return None
    needle = name.strip().lstrip("/").lower()
    if not needle:
        return None

    # 1. Exact ID match (case-insensitive)
    for aid, spec in registry.items():
        if aid.lower() == needle:
            return aid, spec

    # 2. Match explicit slash/aliases metadata declared in actions.json
    for aid, spec in registry.items():
        slash = str(spec.get("slash") or spec.get("command") or "").strip().lstrip("/").lower()
        if slash == needle:
            return aid, spec
        aliases = spec.get("aliases") or []
        if isinstance(aliases, list):
            if any(str(a).strip().lstrip("/").lower() == needle for a in aliases):
                return aid, spec

    # 3. Well-known slash hint match ONLY if that key actually exists in registry
    for candidate in SLASH_ALIAS_HINTS.get(needle, ()):
        for aid, spec in registry.items():
            if aid.lower() == candidate:
                return aid, spec

    return None


def _extract_param_names(spec: dict[str, Any]) -> list[str]:
    """Determine declared parameter names from an actions.json entry."""
    for key in ("args", "params", "parameters", "arguments", "arg_schema"):
        val = spec.get(key)
        if isinstance(val, dict):
            props = val.get("properties") if isinstance(val.get("properties"), dict) else val
            return [str(k) for k in props.keys()]
        if isinstance(val, list):
            names = []
            for item in val:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
            if names:
                return names
    return []


def validate_action_request(
    raw_name: str,
    args_dict: dict[str, Any] | None,
    raw_tokens: list[str] | None,
    registry: dict[str, dict[str, Any]],
) -> tuple[bool, str, dict[str, Any], dict[str, Any], str]:
    """Validate an action request strictly against actions.json.

    Returns (valid, canonical_id, normalized_args, spec, error_message).
    """
    resolved = _resolve_registry_action(raw_name, registry)
    if resolved is None:
        available = ", ".join(sorted(registry.keys())) if registry else "none loaded"
        return (
            False,
            raw_name,
            {},
            {},
            f"Action '{raw_name}' is not permitted by {ACTIONS_JSON_PATH}. Allowed: {available}",
        )

    aid, spec = resolved
    normalized: dict[str, Any] = dict(args_dict) if isinstance(args_dict, dict) else {}
    arg_schema_top = spec.get("args") if isinstance(spec.get("args"), dict) else {}

    # Bind flag, key=value, and positional tokens from slash commands cleanly
    if raw_tokens:
        positional: list[str] = []
        for tok in raw_tokens:
            if tok.startswith("--") and len(tok) > 2:
                flag_name = tok[2:].replace("-", "_")
                if flag_name in arg_schema_top:
                    normalized[flag_name] = True
                    continue
            if "=" in tok and not tok.startswith(("/", "-")):
                k, v = tok.split("=", 1)
                k_clean = k.strip().replace("-", "_")
                if k_clean:
                    normalized[k_clean] = v.strip()
                    continue
            positional.append(tok)

        if positional:
            # Prefer non-boolean parameters when binding positional arguments
            all_params = _extract_param_names(spec)
            non_bool_params = [
                p
                for p in all_params
                if not (
                    isinstance(arg_schema_top.get(p), dict)
                    and arg_schema_top[p].get("type") == "bool_optional"
                )
            ]
            target_params = non_bool_params or all_params
            if len(target_params) == 1 and target_params[0] not in normalized:
                normalized[target_params[0]] = " ".join(positional)
            elif target_params:
                for idx, val in enumerate(positional):
                    if idx < len(target_params):
                        normalized.setdefault(target_params[idx], val)
            else:
                return (
                    False,
                    aid,
                    {},
                    spec,
                    f"Action '{aid}' does not accept extra arguments: {' '.join(positional)}",
                )

    # Validate against actions.json schema (values/enum/bool_optional/home_realpath/required)
    for key in ("args", "params", "parameters", "arguments", "arg_schema"):
        schema = spec.get(key)
        if not isinstance(schema, dict):
            continue
        req_list = schema.get("required") if isinstance(schema.get("required"), list) else []
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else schema

        if props:
            unknown = sorted(k for k in normalized.keys() if k not in props)
            if unknown:
                return (
                    False,
                    aid,
                    normalized,
                    spec,
                    f"Unknown argument(s) for '{aid}': {', '.join(unknown)}",
                )

        for req_name in req_list:
            if not str(normalized.get(req_name, "")).strip():
                return False, aid, normalized, spec, f"Missing required argument '{req_name}' for {aid}"

        if isinstance(props, dict):
            for pname, pspec in props.items():
                if not isinstance(pspec, dict):
                    continue
                if pspec.get("required") and (
                    pname not in normalized or not str(normalized.get(pname, "")).strip()
                ):
                    return False, aid, normalized, spec, f"Missing required argument '{pname}' for {aid}"
                if pname not in normalized:
                    continue

                ptype = str(pspec.get("type") or "")
                if ptype == "bool_optional":
                    raw_b = normalized[pname]
                    if isinstance(raw_b, bool):
                        pass
                    elif isinstance(raw_b, str) and raw_b.lower() in ("true", "1", "yes", "on"):
                        normalized[pname] = True
                    elif isinstance(raw_b, str) and raw_b.lower() in ("false", "0", "no", "off"):
                        normalized[pname] = False
                    else:
                        return (
                            False,
                            aid,
                            normalized,
                            spec,
                            f"Argument '{pname}' must be true or false for {aid}",
                        )
                elif ptype == "home_realpath":
                    if not isinstance(normalized[pname], str) or not normalized[pname].strip():
                        return False, aid, normalized, spec, f"Path argument '{pname}' cannot be empty."

                choices = pspec.get("values") or pspec.get("enum") or pspec.get("choices") or pspec.get("allowed")
                if isinstance(choices, list):
                    val_str = str(normalized[pname])
                    if val_str not in [str(c) for c in choices]:
                        return (
                            False,
                            aid,
                            normalized,
                            spec,
                            f"Invalid value '{val_str}' for '{pname}'. Allowed: {', '.join(str(c) for c in choices)}",
                        )

    return True, aid, normalized, spec, ""


def parse_slash_command(text: str) -> tuple[str, list[str]]:
    """Parse `/cmd arg1 arg2` safely without invoking a shell."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return "", []
    try:
        tokens = shlex.split(stripped)
    except ValueError:
        tokens = stripped.split()
    if not tokens:
        return "", []
    return tokens[0].lstrip("/"), tokens[1:]


def extract_k_ai_actions(text: str) -> list[dict[str, Any]]:
    """Extract all valid JSON objects containing `k_ai_action` from assistant output."""
    decoder = json.JSONDecoder()
    results: list[dict[str, Any]] = []
    idx = 0
    length = len(text)
    while idx < length:
        pos = text.find("{", idx)
        if pos == -1:
            break
        try:
            obj, end_pos = decoder.raw_decode(text, pos)
            if isinstance(obj, dict) and isinstance(obj.get("k_ai_action"), str):
                results.append(obj)
            idx = max(pos + 1, end_pos)
        except json.JSONDecodeError:
            idx = pos + 1
    return results


def normalize_tier_info(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize hardware/tier output from `/usr/bin/k-ai-detect --json`."""
    if not raw:
        return {
            "tierNum": 0,
            "tierBadge": "Tier: Detecting...",
            "tierBadgeHi": "टियर: जांच जारी...",
            "tierDetail": "Hardware profile unavailable",
            "recommendedModel": "",
        }

    raw_tier = raw.get("tier") if raw.get("tier") is not None else raw.get("tier_id", 0)
    tier_num = 0
    if isinstance(raw_tier, int):
        tier_num = raw_tier
    elif isinstance(raw_tier, str):
        low = raw_tier.lower()
        if "1" in low or "cloud" in low:
            tier_num = 1
        elif "2" in low or "3b" in low or "4b" in low:
            tier_num = 2
        elif "3" in low or "hybrid" in low:
            tier_num = 3

    default_labels = {
        1: ("Tier 1 • Cloud", "टियर 1 • क्लाउड"),
        2: ("Tier 2 • Local 3B–4B", "टियर 2 • लोकल 3B–4B"),
        3: ("Tier 3 • Local / Hybrid", "टियर 3 • लोकल / हाइब्रिड"),
    }
    en_label, hi_label = default_labels.get(
        tier_num,
        (
            str(raw.get("tier_label") or raw.get("label") or f"Tier {raw_tier}"),
            str(raw.get("tier_label") or raw.get("label") or f"टियर {raw_tier}"),
        ),
    )

    ram_gb = raw.get("ram_gib") or raw.get("ram_gb") or raw.get("total_ram_gb") or ""
    vram_gb = raw.get("vram_gib") or raw.get("vram_gb") or 0
    backend = raw.get("gpu_backend") or raw.get("backend") or raw.get("gpu") or ""
    model = str(raw.get("recommended_model") or raw.get("model") or "")
    detail_parts = []
    if ram_gb:
        detail_parts.append(f"{ram_gb} GiB RAM")
    if vram_gb:
        detail_parts.append(f"{vram_gb} GiB VRAM")
    if backend and str(backend) != "none":
        detail_parts.append(str(backend))
    if model:
        detail_parts.append(model)

    return {
        "tierNum": tier_num,
        "tierBadge": en_label,
        "tierBadgeHi": hi_label,
        "tierDetail": " • ".join(detail_parts) if detail_parts else str(raw.get("message") or raw.get("reason") or ""),
        "recommendedModel": model,
    }


def normalize_status_info(raw: dict[str, Any] | None, online: bool) -> dict[str, Any]:
    """Normalize engine status from `http://127.0.0.1:11435/v1/status`."""
    if not online or raw is None:
        return {
            "online": False,
            "state": "offline",
            "ramMb": 0,
            "ramText": "Engine Offline • Idle 0 MB",
            "ramTextHi": "इंजन ऑफ़लाइन • 0 MB RAM",
            "model": "",
            "provider": "",
            "cloudConfigured": False,
        }

    model_loaded = bool(raw.get("model_loaded", False))
    model = str(raw.get("loaded_model") or raw.get("active_model") or raw.get("model") or "")
    backend = str(raw.get("backend") or "").lower()
    provider = str(raw.get("cloud_provider") or raw.get("provider") or "")
    cloud_ok = bool(
        raw.get("cloud_configured")
        or raw.get("api_key_configured")
        or raw.get("has_api_key")
        or False
    )

    ram_val = raw.get("rss_mb")
    if ram_val is None:
        ram_val = raw.get("ram_mb", raw.get("memory_mb", raw.get("idle_ram_mb", 0)))
    try:
        ram_mb = int(round(float(ram_val or 0)))
    except (TypeError, ValueError):
        ram_mb = 0

    state = "loaded" if model_loaded else ("cloud" if backend.startswith("cloud:") else "idle")
    if not model_loaded and ram_mb == 0:
        if cloud_ok and provider:
            en_txt = f"Cloud Ready ({provider}) • 0 MB"
            hi_txt = f"क्लाउड तैयार ({provider}) • 0 MB"
        else:
            en_txt = "Idle • 0 MB RAM"
            hi_txt = "आइडल • 0 MB RAM"
    elif model_loaded and model:
        en_txt = f"Loaded • {model} • {ram_mb} MB"
        hi_txt = f"लोड • {model} • {ram_mb} MB"
    else:
        en_txt = f"{state.title()} • {ram_mb} MB RAM"
        hi_txt = f"{state.title()} • {ram_mb} MB RAM"

    return {
        "online": True,
        "state": state,
        "ramMb": ram_mb,
        "ramText": en_txt,
        "ramTextHi": hi_txt,
        "model": model,
        "provider": provider,
        "cloudConfigured": cloud_ok,
    }


def _http_get_json(url: str, timeout: float = 2.5) -> tuple[bool, dict[str, Any] | None]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False, None
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body.strip() else {}
            return True, data if isinstance(data, dict) else {}
    except Exception:
        return False, None


def _build_system_prompt(is_hindi: bool, registry: dict[str, dict[str, Any]]) -> str:
    actions_desc = ", ".join(f"{aid}" for aid in sorted(registry.keys())) or "none"
    lang_hint = (
        "Prefer clear Hindi (Devanagari) unless the user writes in English or Hinglish."
        if is_hindi
        else "Respond in the same language/script as the user (English, Hindi Devanagari, or Hinglish)."
    )
    return (
        "You are K-AI, the privacy-first desktop assistant of Kushagra OS (Fedora Atomic Kinoite 44, "
        "KDE Plasma 6 Wayland). "
        f"{lang_hint} Be concise, truthful, and technically accurate. "
        "NEVER fabricate file paths, package names, or command outputs. "
        f"Allowed system actions in registry ({ACTIONS_JSON_PATH}): [{actions_desc}]. "
        "If the user asks to perform a system action from that registry, propose it ONLY as a JSON object "
        'like {"k_ai_action": "<action_id>", "args": {...}} and wait for explicit user approval. '
        "Never claim an action has already run."
    )


class StatusWorker(QThread):
    """Non-blocking poller for k-ai-detect and engine /v1/status."""

    statusReady = pyqtSignal(dict, dict)

    def __init__(self, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.preview_mode = preview_mode

    def run(self) -> None:
        if self.preview_mode:
            tier = normalize_tier_info(
                {
                    "tier": 2,
                    "ram_gb": 8,
                    "backend": "Vulkan",
                    "recommended_model": "qwen2.5-3b-instruct",
                }
            )
            status = normalize_status_info(
                {"state": "idle", "ram_mb": 0, "model_loaded": False, "cloud_configured": False},
                online=True,
            )
            self.statusReady.emit(tier, status)
            return

        raw_detect = None
        detect_bin = "/usr/bin/k-ai-detect"
        if not os.path.exists(detect_bin):
            detect_bin = shutil.which("k-ai-detect") or ""
        if detect_bin:
            try:
                res = subprocess.run(
                    [detect_bin, "--json"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=4,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    parsed = json.loads(res.stdout)
                    if isinstance(parsed, dict):
                        raw_detect = parsed
            except Exception:
                pass

        online, raw_status = _http_get_json(f"{ENGINE_BASE_URL}/v1/status", timeout=2.5)
        self.statusReady.emit(
            normalize_tier_info(raw_detect),
            normalize_status_info(raw_status, online),
        )


class ChatWorker(QThread):
    """Non-blocking streaming/non-streaming client for local k-ai-engine."""

    chunkReceived = pyqtSignal(str, str)  # msg_id, delta_text
    finishedReply = pyqtSignal(str, str, bool, str)  # msg_id, full_text, ok, err

    def __init__(
        self,
        msg_id: str,
        messages: list[dict[str, str]],
        model_hint: str = "",
        preview_mode: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.msg_id = msg_id
        self.messages = messages
        self.model_hint = model_hint
        self.preview_mode = preview_mode
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _try_start_engine(self) -> None:
        if not shutil.which("systemctl"):
            return
        try:
            subprocess.run(
                ["systemctl", "--user", "start", "k-ai-engine.service"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
        except Exception:
            pass

    def _post_chat(self, url: str, payload: dict[str, Any]) -> tuple[str, str]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream, application/json"},
            method="POST",
        )
        full_parts: list[str] = []
        with urllib.request.urlopen(req, timeout=120) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/event-stream" in ctype:
                while not self._cancelled:
                    raw_line = resp.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        chunk_str = line[5:].strip()
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk_obj = json.loads(chunk_str)
                        except json.JSONDecodeError:
                            continue
                        delta = ""
                        choices = chunk_obj.get("choices")
                        if isinstance(choices, list) and choices:
                            c0 = choices[0] if isinstance(choices[0], dict) else {}
                            delta_obj = c0.get("delta") or c0.get("message") or {}
                            if isinstance(delta_obj, dict):
                                delta = str(delta_obj.get("content") or "")
                            elif isinstance(c0.get("text"), str):
                                delta = c0["text"]
                        elif isinstance(chunk_obj.get("delta"), str):
                            delta = chunk_obj["delta"]
                        elif isinstance(chunk_obj.get("content"), str):
                            delta = chunk_obj["content"]
                        if delta:
                            full_parts.append(delta)
                            self.chunkReceived.emit(self.msg_id, delta)
                return "".join(full_parts), ""

            body = resp.read().decode("utf-8", errors="replace")
            obj = json.loads(body) if body.strip() else {}
            text = ""
            if isinstance(obj, dict):
                choices = obj.get("choices")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message") or {}
                    text = str(msg.get("content") or choices[0].get("text") or "")
                if not text:
                    text = str(
                        obj.get("reply")
                        or obj.get("content")
                        or obj.get("response")
                        or obj.get("text")
                        or ""
                    )
            if text:
                self.chunkReceived.emit(self.msg_id, text)
            return text, ""

    def run(self) -> None:
        if self.preview_mode:
            demo = (
                "Preview mode active (local k-ai-engine not queried). "
                "Try `/health`, `/dns quad9`, `/layout modern-floating`, or click Read Screen (OCR)."
            )
            self.chunkReceived.emit(self.msg_id, demo)
            self.finishedReply.emit(self.msg_id, demo, True, "")
            return

        payload: dict[str, Any] = {"messages": self.messages, "stream": True}
        if self.model_hint:
            payload["model"] = self.model_hint

        last_err = ""
        for attempt in range(2):
            try:
                text, _ = self._post_chat(f"{ENGINE_BASE_URL}/v1/chat/completions", payload)
                if self._cancelled:
                    self.finishedReply.emit(self.msg_id, text, False, "Cancelled")
                else:
                    self.finishedReply.emit(self.msg_id, text, True, "")
                return
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    try:
                        text, _ = self._post_chat(f"{ENGINE_BASE_URL}/v1/chat", payload)
                        self.finishedReply.emit(self.msg_id, text, True, "")
                        return
                    except Exception as inner_exc:
                        last_err = str(inner_exc)
                        break
                err_body = ""
                try:
                    err_body = exc.read().decode("utf-8", errors="replace").strip()
                except Exception:
                    pass
                last_err = f"Engine HTTP {exc.code}: {err_body or exc.reason}"
                break
            except (urllib.error.URLError, ConnectionRefusedError, OSError) as exc:
                last_err = f"K-AI engine offline on 127.0.0.1:11435 ({exc})"
                if attempt == 0:
                    self._try_start_engine()
                    self.msleep(600)
                    continue
            except Exception as exc:
                last_err = str(exc)
                break

        self.finishedReply.emit(self.msg_id, "", False, last_err)


class BrokerWorker(QThread):
    """Non-blocking executor running `k-ai-broker --approved` ONLY after click."""

    finishedAction = pyqtSignal(str, bool, str)

    def __init__(
        self,
        card_id: str,
        action_id: str,
        args_dict: dict[str, Any],
        preview_mode: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.card_id = card_id
        self.action_id = action_id
        self.args_dict = args_dict
        self.preview_mode = preview_mode

    def run(self) -> None:
        if self.preview_mode:
            self.msleep(350)
            self.finishedAction.emit(
                self.card_id,
                True,
                f"[Preview] Would invoke: k-ai-broker --approved for '{self.action_id}' with {json.dumps(self.args_dict)}",
            )
            return

        broker_bin = "/usr/libexec/k-ai-broker"
        if not os.path.exists(broker_bin):
            broker_bin = shutil.which("k-ai-broker") or ""
        if not broker_bin:
            self.finishedAction.emit(
                self.card_id, False, "Missing executable: /usr/libexec/k-ai-broker"
            )
            return

        help_txt = ""
        try:
            hres = subprocess.run(
                [broker_bin, "--help"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            help_txt = (hres.stdout or "") + "\n" + (hres.stderr or "")
        except Exception:
            pass

        use_args_json = ("--args-json" in help_txt) or ("--args " not in help_txt and "--args\n" not in help_txt)
        cmd = [
            broker_bin,
            "--approved",
            "--action",
            self.action_id,
            "--args-json" if use_args_json else "--args",
            json.dumps(self.args_dict, ensure_ascii=False),
        ]

        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            raw_stdout = (res.stdout or "").strip()
            raw_stderr = (res.stderr or "").strip()
            display_parts: list[str] = []
            if raw_stdout:
                try:
                    parsed = json.loads(raw_stdout)
                    if isinstance(parsed, dict):
                        if parsed.get("stdout"):
                            display_parts.append(str(parsed["stdout"]).strip())
                        if parsed.get("stderr"):
                            display_parts.append(str(parsed["stderr"]).strip())
                        if parsed.get("error"):
                            display_parts.append(str(parsed["error"]).strip())
                        if not display_parts and parsed.get("status"):
                            display_parts.append(f"status: {parsed['status']}")
                    else:
                        display_parts.append(raw_stdout)
                except json.JSONDecodeError:
                    display_parts.append(raw_stdout)
            if raw_stderr:
                display_parts.append(raw_stderr)

            combined = "\n".join(part for part in display_parts if part)
            if res.returncode == 0:
                self.finishedAction.emit(
                    self.card_id, True, combined or f"Action '{self.action_id}' succeeded."
                )
            else:
                self.finishedAction.emit(
                    self.card_id,
                    False,
                    combined or f"k-ai-broker exited with code {res.returncode}",
                )
        except subprocess.TimeoutExpired:
            self.finishedAction.emit(self.card_id, False, "Action timed out after 600s.")
        except OSError as exc:
            self.finishedAction.emit(self.card_id, False, f"Broker launch failed: {exc}")


class OcrWorker(QThread):
    """Non-blocking worker invoking on-demand `k-ai-ocr --json` ONLY on click."""

    finishedOcr = pyqtSignal(bool, str, bool, str)  # ok, text, cancelled, err

    def __init__(self, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.preview_mode = preview_mode

    def run(self) -> None:
        if self.preview_mode:
            self.msleep(300)
            self.finishedOcr.emit(True, "[Preview OCR] Sample text captured safely.", False, "")
            return

        ocr_bin = "/usr/bin/k-ai-ocr"
        if not os.path.exists(ocr_bin):
            ocr_bin = shutil.which("k-ai-ocr") or ""
        if not ocr_bin:
            self.finishedOcr.emit(False, "", False, "Missing executable: /usr/bin/k-ai-ocr")
            return

        try:
            res = subprocess.run(
                [ocr_bin, "--json"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=70,
                check=False,
            )
            raw_out = (res.stdout or "").strip()
            if raw_out:
                data = json.loads(raw_out)
                if data.get("ok"):
                    self.finishedOcr.emit(True, str(data.get("text", "")), False, "")
                else:
                    self.finishedOcr.emit(
                        False,
                        "",
                        bool(data.get("cancelled", False)),
                        str(data.get("error", "OCR failed")),
                    )
                return
            err = (res.stderr or f"OCR exited with code {res.returncode}").strip()
            self.finishedOcr.emit(False, "", False, err)
        except Exception as exc:
            self.finishedOcr.emit(False, "", False, str(exc))


class KeySaveWorker(QThread):
    """Store Cloud API Key securely in KWallet via `k-ai-engine set-key`."""

    finishedSave = pyqtSignal(bool, str)

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str = "",
        cloud_model: str = "",
        preview_mode: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.provider = provider
        self._api_key = api_key
        self.base_url = base_url.strip()
        self.cloud_model = cloud_model.strip()
        self.preview_mode = preview_mode

    def run(self) -> None:
        key_val = self._api_key
        self._api_key = ""
        try:
            if self.preview_mode:
                self.msleep(250)
                self.finishedSave.emit(
                    True, f"[Preview] API key for '{self.provider}' routed to KWallet."
                )
                return

            engine_bin = "/usr/bin/k-ai-engine"
            if not os.path.exists(engine_bin):
                engine_bin = shutil.which("k-ai-engine") or ""
            if not engine_bin:
                self.finishedSave.emit(False, "Missing executable: /usr/bin/k-ai-engine")
                return

            cmd = [engine_bin, "set-key", "--provider", self.provider]
            if self.base_url:
                cmd.extend(["--base-url", self.base_url])
            if self.cloud_model:
                cmd.extend(["--model", self.cloud_model])

            res = subprocess.run(
                cmd,
                input=key_val + "\n",
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if res.returncode == 0:
                self.finishedSave.emit(
                    True,
                    (res.stdout or "").strip() or f"Saved {self.provider} key into KWallet.",
                )
            else:
                msg = (res.stderr or res.stdout or f"exit code {res.returncode}").strip()
                self.finishedSave.emit(False, msg)
        except Exception as exc:
            self.finishedSave.emit(False, str(exc))
        finally:
            key_val = ""


class KaiBackend(QObject):
    """Main QML backend orchestrating tier detection, chat, OCR, and broker actions."""

    tierChanged = pyqtSignal()
    statusChanged = pyqtSignal()
    busyChanged = pyqtSignal()
    contextChanged = pyqtSignal()
    keyFeedbackChanged = pyqtSignal()
    languageChanged = pyqtSignal()

    messageAdded = pyqtSignal(dict)
    messageUpdated = pyqtSignal(str, str, bool)
    actionCardUpdated = pyqtSignal(str, str, str, bool)
    messagesCleared = pyqtSignal()

    def __init__(self, preview_mode: bool = False, initial_hindi: bool = False, parent=None):
        super().__init__(parent)
        self._preview_mode = preview_mode
        self._is_hindi = initial_hindi
        self._actions_registry, self._registry_error = load_actions_registry()

        self._tier = normalize_tier_info(None)
        self._status = normalize_status_info(None, False)
        self._chat_busy = False
        self._ocr_busy = False
        self._key_busy = False
        self._attached_context = ""
        self._key_feedback = ""
        self._key_feedback_ok = True

        self._history: list[dict[str, str]] = []
        self._pending_cards: dict[str, dict[str, Any]] = {}
        self._active_workers: list[QThread] = []
        self._chat_worker: ChatWorker | None = None
        self._status_worker: StatusWorker | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(10000)
        self._poll_timer.timeout.connect(self.refreshStatus)
        self._poll_timer.start()

    @pyqtProperty(bool, notify=languageChanged)
    def isHindi(self) -> bool:
        return self._is_hindi

    @pyqtSlot(bool)
    def setHindi(self, val: bool) -> None:
        if self._is_hindi != bool(val):
            self._is_hindi = bool(val)
            self.languageChanged.emit()
            self.tierChanged.emit()
            self.statusChanged.emit()

    @pyqtProperty(int, notify=tierChanged)
    def tierNum(self) -> int:
        return int(self._tier["tierNum"])

    @pyqtProperty(str, notify=tierChanged)
    def tierBadge(self) -> str:
        return self._tier["tierBadgeHi"] if self._is_hindi else self._tier["tierBadge"]

    @pyqtProperty(str, notify=tierChanged)
    def tierDetail(self) -> str:
        return str(self._tier["tierDetail"])

    @pyqtProperty(bool, notify=statusChanged)
    def engineOnline(self) -> bool:
        return bool(self._status["online"])

    @pyqtProperty(str, notify=statusChanged)
    def engineStatusText(self) -> str:
        return self._status["ramTextHi"] if self._is_hindi else self._status["ramText"]

    @pyqtProperty(bool, notify=statusChanged)
    def cloudConfigured(self) -> bool:
        return bool(self._status["cloudConfigured"])

    @pyqtProperty(bool, notify=busyChanged)
    def chatBusy(self) -> bool:
        return self._chat_busy

    @pyqtProperty(bool, notify=busyChanged)
    def ocrBusy(self) -> bool:
        return self._ocr_busy

    @pyqtProperty(bool, notify=busyChanged)
    def keyBusy(self) -> bool:
        return self._key_busy

    @pyqtProperty(str, notify=contextChanged)
    def attachedContext(self) -> str:
        return self._attached_context

    @pyqtProperty(str, notify=keyFeedbackChanged)
    def keyFeedback(self) -> str:
        return self._key_feedback

    @pyqtProperty(bool, notify=keyFeedbackChanged)
    def keyFeedbackOk(self) -> bool:
        return self._key_feedback_ok

    def _track_worker(self, worker: QThread) -> None:
        self._active_workers.append(worker)

        def _cleanup() -> None:
            if worker in self._active_workers:
                self._active_workers.remove(worker)

        worker.finished.connect(_cleanup)
        worker.finished.connect(worker.deleteLater)

    def shutdownWorkers(self) -> None:
        """Stop timers and wait briefly for background QThreads before exit."""
        self._poll_timer.stop()
        if self._chat_worker is not None and self._chat_worker.isRunning():
            self._chat_worker.cancel()
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.wait(1200)

    def _emit_message(
        self,
        *,
        msg_id: str | None = None,
        role: str,
        msg_type: str,
        text: str = "",
        streaming: bool = False,
        action_id: str = "",
        action_title: str = "",
        action_desc: str = "",
        args_pretty: str = "",
        requires_polkit: bool = False,
        card_status: str = "",
        card_output: str = "",
        card_ok: bool = True,
    ) -> str:
        mid = msg_id or uuid.uuid4().hex[:12]
        self.messageAdded.emit(
            {
                "msgId": mid,
                "role": role,
                "msgType": msg_type,
                "text": text,
                "streaming": streaming,
                "actionId": action_id,
                "actionTitle": action_title,
                "actionDesc": action_desc,
                "argsPretty": args_pretty,
                "requiresPolkit": requires_polkit,
                "cardStatus": card_status,
                "cardOutput": card_output,
                "cardOk": card_ok,
            }
        )
        return mid

    @pyqtSlot()
    def refreshStatus(self) -> None:
        if self._status_worker is not None and self._status_worker.isRunning():
            return
        worker = StatusWorker(preview_mode=self._preview_mode, parent=self)
        self._status_worker = worker
        worker.statusReady.connect(self._on_status_ready)
        self._track_worker(worker)
        worker.start()

    def _on_status_ready(self, tier_data: dict, status_data: dict) -> None:
        self._tier = tier_data
        self._status = status_data
        self.tierChanged.emit()
        self.statusChanged.emit()

    @pyqtSlot()
    def startEngineService(self) -> None:
        if not shutil.which("systemctl"):
            self._emit_message(
                role="system",
                msg_type="notice",
                text="systemctl unavailable; start k-ai-engine manually.",
                card_ok=False,
            )
            return
        try:
            subprocess.Popen(
                ["systemctl", "--user", "start", "k-ai-engine.service"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            QTimer.singleShot(900, self.refreshStatus)
        except OSError as exc:
            self._emit_message(
                role="system",
                msg_type="notice",
                text=f"Unable to start engine service: {exc}",
                card_ok=False,
            )

    @pyqtSlot()
    def clearContext(self) -> None:
        if self._attached_context:
            self._attached_context = ""
            self.contextChanged.emit()

    @pyqtSlot()
    def clearChat(self) -> None:
        self._history.clear()
        self._pending_cards.clear()
        self.messagesCleared.emit()

    @pyqtSlot()
    def stopGeneration(self) -> None:
        if self._chat_worker is not None and self._chat_worker.isRunning():
            self._chat_worker.cancel()

    def _propose_action_card(
        self, raw_name: str, args_dict: dict[str, Any] | None, raw_tokens: list[str] | None
    ) -> None:
        # Reload read-only registry so updates on disk are always respected
        self._actions_registry, reg_err = load_actions_registry()
        if reg_err and not self._actions_registry:
            self._emit_message(
                role="system",
                msg_type="notice",
                text=reg_err,
                card_ok=False,
            )
            return

        valid, aid, norm_args, spec, err_msg = validate_action_request(
            raw_name, args_dict, raw_tokens, self._actions_registry
        )
        if not valid:
            self._emit_message(
                role="system",
                msg_type="notice",
                text=err_msg,
                card_ok=False,
            )
            return

        card_id = f"card_{uuid.uuid4().hex[:10]}"
        self._pending_cards[card_id] = {
            "action_id": aid,
            "args": norm_args,
            "status": "pending",
        }
        title = str(spec.get("title") or spec.get("name") or aid)
        desc = str(spec.get("description") or f"Execute whitelisted K-AI action '{aid}'")
        requires_polkit = bool(spec.get("polkit") or spec.get("privileged") or spec.get("requires_polkit"))
        priv_when_not = spec.get("privileged_when_not")
        if isinstance(priv_when_not, str):
            requires_polkit = norm_args.get("action") != priv_when_not
        args_pretty = (
            json.dumps(norm_args, ensure_ascii=False, indent=2) if norm_args else "{}"
        )

        self._emit_message(
            msg_id=card_id,
            role="system",
            msg_type="action_card",
            action_id=aid,
            action_title=title,
            action_desc=desc,
            args_pretty=args_pretty,
            requires_polkit=requires_polkit,
            card_status="pending",
            card_output="",
            card_ok=True,
        )

    @pyqtSlot(str)
    def submitMessage(self, raw_text: str) -> None:
        text = raw_text.strip()
        if not text and not self._attached_context:
            return
        if self._chat_busy:
            return

        # 1. Intercept slash commands deterministically before LLM chat
        if text.startswith("/"):
            self._emit_message(role="user", msg_type="chat", text=text)
            cmd, tokens = parse_slash_command(text)
            self._propose_action_card(cmd, {}, tokens)
            return

        display_text = text
        ctx = self._attached_context.strip()
        llm_user_text = text
        if ctx:
            if not display_text:
                display_text = "Analyze attached context"
            llm_user_text = f"Context:\n```\n{ctx}\n```\n\n{display_text}"
            self._attached_context = ""
            self.contextChanged.emit()

        self._emit_message(role="user", msg_type="chat", text=display_text)
        self._history.append({"role": "user", "content": llm_user_text})
        if len(self._history) > MAX_HISTORY_TURNS * 2:
            self._history = self._history[-(MAX_HISTORY_TURNS * 2) :]

        # Also check if user literally pasted an action JSON directly
        direct_actions = extract_k_ai_actions(text)
        if direct_actions:
            for act in direct_actions:
                self._propose_action_card(
                    str(act.get("k_ai_action", "")),
                    act.get("args") if isinstance(act.get("args"), dict) else {},
                    None,
                )
            return

        assistant_id = self._emit_message(
            role="assistant", msg_type="chat", text="", streaming=True
        )
        self._chat_busy = True
        self.busyChanged.emit()

        sys_prompt = _build_system_prompt(self._is_hindi, self._actions_registry)
        messages = [{"role": "system", "content": sys_prompt}, *self._history]
        model_hint = str(self._status.get("model") or self._tier.get("recommendedModel") or "")

        worker = ChatWorker(
            msg_id=assistant_id,
            messages=messages,
            model_hint=model_hint,
            preview_mode=self._preview_mode,
            parent=self,
        )
        self._chat_worker = worker
        self._stream_buffers = getattr(self, "_stream_buffers", {})
        self._stream_buffers[assistant_id] = []

        worker.chunkReceived.connect(self._on_chat_chunk)
        worker.finishedReply.connect(self._on_chat_finished)
        self._track_worker(worker)
        worker.start()

    def _on_chat_chunk(self, msg_id: str, delta: str) -> None:
        buf = self._stream_buffers.setdefault(msg_id, [])
        buf.append(delta)
        self.messageUpdated.emit(msg_id, "".join(buf), True)

    def _on_chat_finished(self, msg_id: str, full_text: str, ok: bool, err: str) -> None:
        self._chat_busy = False
        self.busyChanged.emit()
        buf_text = "".join(self._stream_buffers.pop(msg_id, []))
        final_text = full_text or buf_text

        if ok:
            self.messageUpdated.emit(msg_id, final_text, False)
            if final_text:
                self._history.append({"role": "assistant", "content": final_text})
                for act in extract_k_ai_actions(final_text):
                    self._propose_action_card(
                        str(act.get("k_ai_action", "")),
                        act.get("args") if isinstance(act.get("args"), dict) else {},
                        None,
                    )
        else:
            fallback_msg = final_text.strip()
            notice = f"{fallback_msg}\n\n[{err}]" if fallback_msg else err
            self.messageUpdated.emit(msg_id, notice, False)

    @pyqtSlot(str)
    def approveAction(self, card_id: str) -> None:
        card = self._pending_cards.get(card_id)
        if not card or card.get("status") != "pending":
            return
        card["status"] = "running"
        self.actionCardUpdated.emit(card_id, "running", "", True)

        worker = BrokerWorker(
            card_id=card_id,
            action_id=str(card["action_id"]),
            args_dict=dict(card.get("args") or {}),
            preview_mode=self._preview_mode,
            parent=self,
        )
        worker.finishedAction.connect(self._on_broker_finished)
        self._track_worker(worker)
        worker.start()

    def _on_broker_finished(self, card_id: str, ok: bool, output: str) -> None:
        card = self._pending_cards.get(card_id)
        if card:
            card["status"] = "completed" if ok else "failed"
        self.actionCardUpdated.emit(
            card_id, "completed" if ok else "failed", output, ok
        )

    @pyqtSlot(str)
    def cancelAction(self, card_id: str) -> None:
        card = self._pending_cards.get(card_id)
        if not card or card.get("status") != "pending":
            return
        card["status"] = "cancelled"
        self.actionCardUpdated.emit(
            card_id, "cancelled", "Cancelled by user (not executed).", True
        )

    @pyqtSlot()
    def triggerOcr(self) -> None:
        if self._ocr_busy:
            return
        self._ocr_busy = True
        self.busyChanged.emit()

        worker = OcrWorker(preview_mode=self._preview_mode, parent=self)
        worker.finishedOcr.connect(self._on_ocr_finished)
        self._track_worker(worker)
        worker.start()

    def _on_ocr_finished(self, ok: bool, text: str, cancelled: bool, err: str) -> None:
        self._ocr_busy = False
        self.busyChanged.emit()
        if ok:
            cleaned = text.strip()
            if cleaned:
                self._attached_context = cleaned
                self.contextChanged.emit()
                self._emit_message(
                    role="system",
                    msg_type="notice",
                    text=f"Screen OCR attached ({len(cleaned)} chars). Temp screenshot shredded.",
                    card_ok=True,
                )
            else:
                self._emit_message(
                    role="system",
                    msg_type="notice",
                    text="Screen OCR completed: no readable text found. Temp screenshot shredded.",
                    card_ok=True,
                )
        elif cancelled:
            self._emit_message(
                role="system",
                msg_type="notice",
                text="Screen OCR cancelled.",
                card_ok=True,
            )
        else:
            self._emit_message(
                role="system",
                msg_type="notice",
                text=f"Screen OCR failed: {err}",
                card_ok=False,
            )

    @pyqtSlot(str, str, str, str)
    def saveApiKey(self, provider: str, api_key: str, base_url: str = "", cloud_model: str = "") -> None:
        cleaned = api_key.strip()
        if not cleaned:
            self._key_feedback = "Please enter a non-empty API key."
            self._key_feedback_ok = False
            self.keyFeedbackChanged.emit()
            return
        if self._key_busy:
            return

        self._key_busy = True
        self._key_feedback = "Saving to KWallet..."
        self._key_feedback_ok = True
        self.busyChanged.emit()
        self.keyFeedbackChanged.emit()

        worker = KeySaveWorker(
            provider=provider.strip().lower() or "openai",
            api_key=cleaned,
            base_url=base_url,
            cloud_model=cloud_model,
            preview_mode=self._preview_mode,
            parent=self,
        )
        cleaned = ""
        worker.finishedSave.connect(self._on_key_saved)
        self._track_worker(worker)
        worker.start()

    def _on_key_saved(self, ok: bool, msg: str) -> None:
        self._key_busy = False
        self._key_feedback = msg
        self._key_feedback_ok = ok
        self.busyChanged.emit()
        self.keyFeedbackChanged.emit()
        if ok:
            QTimer.singleShot(300, self.refreshStatus)

    def apply_cli_launch(self, prompt: str, context: str, action: str) -> None:
        """Apply incoming CLI flags or IPC invocation cleanly."""
        if context.strip():
            self._attached_context = context.strip()
            self.contextChanged.emit()

        effective_prompt = prompt.strip()
        preset = ACTION_PRESETS.get(action.strip().lower(), "")
        if preset:
            effective_prompt = f"{preset}\n\n{effective_prompt}".strip() if effective_prompt else preset

        if effective_prompt:
            self.submitMessage(effective_prompt)


def _position_drawer(app: QGuiApplication, win: QWindow) -> None:
    """Position frosted-glass drawer on right edge of active QScreen safely."""
    screen = app.primaryScreen()
    if not screen and app.screens():
        screen = app.screens()[0]
    if not screen:
        return
    geo = screen.availableGeometry()
    if geo.width() <= 0 or geo.height() <= 0:
        geo = screen.geometry()
    if geo.width() <= 0 or geo.height() <= 0:
        return

    drawer_w = min(460, max(360, int(geo.width() * 0.30)))
    drawer_h = max(480, geo.height() - 24)
    pos_x = geo.x() + max(0, geo.width() - drawer_w - 12)
    pos_y = geo.y() + 12

    win.setMinimumSize(QSize(340, 440))
    win.setScreen(screen)
    win.setGeometry(pos_x, pos_y, drawer_w, drawer_h)


def _install_signal_handlers(app: QGuiApplication) -> None:
    state = {"quit": False}

    def _on_sig(_signum=None, _frame=None):
        state["quit"] = True

    for sig_name in ("SIGTERM", "SIGHUP", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            signal.signal(sig, _on_sig)

    timer = QTimer(app)
    timer.setInterval(150)
    timer.timeout.connect(lambda: app.quit() if state["quit"] else None)
    timer.start()


def _ipc_socket_path() -> Path | None:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if not runtime_dir:
        return None
    return Path(runtime_dir) / "k-ai-drawer.sock"


def _try_forward_to_existing(payload: dict[str, str]) -> bool:
    sock_path = _ipc_socket_path()
    if sock_path is None or not sock_path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cli:
            cli.settimeout(1.0)
            cli.connect(str(sock_path))
            cli.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return True
    except OSError:
        try:
            sock_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _start_ipc_server(app: QGuiApplication, win: QWindow | None, backend: KaiBackend) -> socket.socket | None:
    sock_path = _ipc_socket_path()
    if sock_path is None:
        return None
    try:
        sock_path.unlink(missing_ok=True)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        os.umask(0o077)
        srv.bind(str(sock_path))
        os.chmod(sock_path, 0o600)
        srv.listen(4)
        srv.setblocking(False)
    except OSError:
        return None

    notifier = QSocketNotifier(srv.fileno(), QSocketNotifier.Type.Read, app)

    def _accept() -> None:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        with conn:
            try:
                conn.settimeout(0.5)
                chunks = []
                while True:
                    buf = conn.recv(65536)
                    if not buf:
                        break
                    chunks.append(buf)
                    if sum(len(c) for c in chunks) > 524288:
                        break
                raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        backend.apply_cli_launch(
                            str(data.get("prompt", "")),
                            str(data.get("context", "")),
                            str(data.get("action", "")),
                        )
            except Exception:
                pass
        if win is not None:
            win.show()
            win.raise_()
            win.requestActivate()

    notifier.activated.connect(_accept)
    app.aboutToQuit.connect(lambda: (srv.close(), sock_path.unlink(missing_ok=True)))
    return srv


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="k-ai-drawer",
        description="Kushagra OS K-AI Frosted-Glass Wayland Side Drawer.",
    )
    parser.add_argument("--prompt", default="", help="Initial prompt or slash command")
    parser.add_argument("--context", default="", help="Context text snippet to attach")
    parser.add_argument(
        "--context-file",
        default="",
        help="Private transient file containing large context (read and removed)",
    )
    parser.add_argument(
        "--action",
        default="",
        choices=["", "translate", "summarize", "fix_grammar", "explain_code"],
        help="Quick action preset mode",
    )
    parser.add_argument("--lang", default="", choices=["", "en", "hi"], help="UI language")
    parser.add_argument("--preview", action="store_true", help="Run in offline preview mode")
    return parser.parse_args(argv)


def _read_context_args(args: argparse.Namespace) -> str:
    context = args.context or ""
    if args.context_file:
        cpath = Path(args.context_file)
        try:
            if cpath.is_file():
                context = cpath.read_text(encoding="utf-8", errors="replace")
        finally:
            try:
                cpath.unlink(missing_ok=True)
            except OSError:
                pass
    return context


def main() -> int:
    args = parse_args(sys.argv[1:])
    context_text = _read_context_args(args)

    if not args.preview:
        if _try_forward_to_existing(
            {
                "prompt": args.prompt,
                "context": context_text,
                "action": args.action,
            }
        ):
            return 0

    try:
        from PyQt6.QtQuickControls2 import QQuickStyle
        QQuickStyle.setStyle("Basic")
    except Exception:
        pass

    app = QGuiApplication(sys.argv)
    app.setApplicationName("K-AI")
    app.setOrganizationName("Kushagra OS")
    _install_signal_handlers(app)

    initial_hindi = args.lang == "hi"
    engine = QQmlApplicationEngine()
    backend = KaiBackend(preview_mode=args.preview, initial_hindi=initial_hindi, parent=engine)

    base_dir = Path(__file__).resolve().parent
    logo_path = Path("/usr/share/kushagra-os/branding/logo-symbol.svg")
    if not logo_path.exists():
        logo_path = base_dir.parent / "branding" / "logo-symbol.svg"

    ctx = engine.rootContext()
    ctx.setContextProperty("kaiBackend", backend)
    ctx.setContextProperty("kushagraLogoUrl", QUrl.fromLocalFile(str(logo_path)))
    ctx.setContextProperty("isPreviewMode", args.preview)

    qml_path = base_dir / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1

    win = engine.rootObjects()[0]
    if isinstance(win, QWindow):
        _position_drawer(app, win)
        win.show()

    if not args.preview:
        _start_ipc_server(app, win if isinstance(win, QWindow) else None, backend)

    app.aboutToQuit.connect(backend.shutdownWorkers)
    QTimer.singleShot(50, backend.refreshStatus)
    if args.prompt or context_text or args.action:
        QTimer.singleShot(
            180,
            lambda: backend.apply_cli_launch(args.prompt, context_text, args.action),
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
