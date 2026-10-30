"""The brain: Gemini Robotics-ER 2 calling bridge tools, plus an offline stand-in.

Design rule: the model decides WHAT to look up; M-Files (the bridge) says WHAT IS TRUE.
The app shows procedure steps from the bridge result, never from the model's own text.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..bridge.tools import TOOL_DECLARATIONS, Bridge, dispatch

DEFAULT_MODEL = os.environ.get("LANTERN_MODEL", "gemini-robotics-er-2-preview")

SYSTEM_PROMPT = """You are the reasoning layer of a physical agent working in a factory or warehouse.
You can see through a camera. Company knowledge lives in an M-Files vault that you reach only through tools.

Rules:
1. Read the identifier on the item in the image (serial number, batch number, container ID or part number).
   Zoom into the label if the text is small. Pass it to identify_item exactly as printed.
2. If identify_item does not return status "ok", stop. Say what you read and ask a person to confirm.
   Never guess an identifier and never pick a close match yourself.
3. Always call check_blockers before giving any instructions.
4. For equipment, call get_approved_job with the requested task.
   For a batch or container, call check_part_for_build with the build order you were given
   and the revision letter you read on the label.
5. Never invent, reword or add procedure steps. The app shows the approved steps from the vault.
6. If anything is blocked, ambiguous or missing, say so plainly and stop.
7. For a drone pre-flight check, read the drone ID in the image, identify it, then call
   check_mission_readiness with the site you were given.
8. For an inspection, read the asset tag and the gauge. Identify the asset, call get_inspection_criteria,
   then call evaluate_reading with the gauge tag, the value exactly as you read it, and the unit.
   If you cannot read the gauge clearly, say so and do not guess a value.
9. You cannot write to the vault. A person confirms the work and the app records the evidence.

Finish with a short summary of at most four sentences: what you identified, the decision, and why."""


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentResult:
    mode: str
    seen: dict[str, Any] = field(default_factory=dict)
    calls: list[ToolCall] = field(default_factory=list)
    final_text: str = ""

    def last(self, tool: str) -> dict[str, Any] | None:
        for c in reversed(self.calls):
            if c.name == tool:
                return c.result
        return None


def _user_prompt(task: str | None, build_order: str | None, site: str | None = None,
                 inspection: bool = False) -> str:
    if site:
        return f"Drone pre-flight check for site '{site}'. Read the drone ID in the image and check mission readiness."
    if inspection:
        return ("Inspection round. Read the asset tag and the pressure gauge in the image, get the approved "
                "inspection criteria and evaluate the reading.")
    if build_order:
        return (f"Logistics check. Read the label in the image and check whether this batch can go to build order "
                f"{build_order}.")
    return f"Maintenance job requested: '{task}'. Identify the equipment in the image and prepare the approved job."


class GeminiAgent:
    """Function-calling loop against Gemini Robotics-ER 2 (or any Gemini model id)."""

    def __init__(self, bridge: Bridge, model: str = DEFAULT_MODEL, client: Any = None, max_turns: int = 8,
                 on_call: Callable[[ToolCall], None] | None = None, max_retries: int = 6,
                 on_wait: Callable[[float], None] | None = None, sleep: Callable[[float], None] = time.sleep):
        from google import genai  # imported lazily so offline mode works without the SDK
        from google.genai import types

        self.types = types
        self.bridge = bridge
        self.model = model
        self.client = client or genai.Client()  # reads GEMINI_API_KEY from the environment
        self.max_turns = max_turns
        self.on_call = on_call
        self.max_retries = max_retries
        self.on_wait = on_wait
        self.sleep = sleep

    def _config(self):
        t = self.types
        return t.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[t.Tool(function_declarations=[t.FunctionDeclaration(**d) for d in TOOL_DECLARATIONS])],
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )

    def _generate(self, contents, config):
        """generate_content, waiting out 429 rate limits (free tier allows only a few requests a minute)."""
        for attempt in range(self.max_retries + 1):
            try:
                return self.client.models.generate_content(model=self.model, contents=contents, config=config)
            except Exception as exc:  # google.genai.errors.ClientError; matched by status so the SDK stays lazy
                if getattr(exc, "code", None) != 429 or attempt == self.max_retries:
                    raise
                if "PerDay" in str(exc):  # daily quota: waiting a minute will not help
                    raise RuntimeError("Gemini daily quota exhausted for this key/model (free tier). "
                                       "Retry tomorrow, enable billing, or use --model with another model.") from exc
                m = re.search(r"retry in ([\d.]+)s", str(exc))
                wait = (float(m.group(1)) if m else 30.0) + 1.0
                if self.on_wait:
                    self.on_wait(wait)
                self.sleep(wait)

    def run(self, image_path: str | Path, task: str | None = None, build_order: str | None = None,
            site: str | None = None, inspection: bool = False) -> AgentResult:
        t = self.types
        image_path = Path(image_path)
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        contents = [t.Content(role="user", parts=[
            t.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime),
            t.Part.from_text(text=_user_prompt(task, build_order, site, inspection)),
        ])]
        result = AgentResult(mode=f"gemini:{self.model}")
        config = self._config()
        for _ in range(self.max_turns):
            resp = self._generate(contents, config)
            calls = list(resp.function_calls or [])
            if not calls:
                result.final_text = (resp.text or "").strip()
                break
            contents.append(resp.candidates[0].content)
            response_parts = []
            for call in calls:
                args = dict(call.args or {})
                if call.name == "identify_item":
                    result.seen.setdefault("identifier", args.get("identifier"))
                if call.name == "check_part_for_build" and args.get("label_revision"):
                    result.seen.setdefault("label_revision", args.get("label_revision"))
                if call.name == "evaluate_reading":
                    result.seen.update({k: args.get(k) for k in ("measurement_point", "value", "unit")})
                out = dispatch(self.bridge, call.name, args)
                tc = ToolCall(call.name, args, out)
                result.calls.append(tc)
                if self.on_call:
                    self.on_call(tc)
                response_parts.append(t.Part(function_response=t.FunctionResponse(
                    id=getattr(call, "id", None), name=call.name, response={"result": out})))
            contents.append(t.Content(role="user", parts=response_parts))
        else:
            result.final_text = "Stopped: too many tool turns without a final answer."
        return result


class OfflineAgent:
    """No AI model. Simulates perception from a sidecar JSON file and follows the same tool plan.

    Use it to demo and test the M-Files side without an API key. It is clearly labelled as a simulation.
    """

    def __init__(self, bridge: Bridge, on_call: Callable[[ToolCall], None] | None = None):
        self.bridge = bridge
        self.on_call = on_call

    def _call(self, result: AgentResult, name: str, args: dict[str, Any]) -> dict[str, Any]:
        out = dispatch(self.bridge, name, args)
        tc = ToolCall(name, args, out)
        result.calls.append(tc)
        if self.on_call:
            self.on_call(tc)
        return out

    def run(self, image_path: str | Path, task: str | None = None, build_order: str | None = None,
            site: str | None = None, inspection: bool = False) -> AgentResult:
        truth_file = Path(image_path).with_suffix(".json")
        if not truth_file.exists():
            raise FileNotFoundError(f"Offline mode needs {truth_file.name} next to the image (simulated perception).")
        seen = json.loads(truth_file.read_text())
        result = AgentResult(mode="offline-simulation", seen=seen)
        ident = self._call(result, "identify_item", {"identifier": seen["identifier"]})
        if ident.get("status") != "ok":
            result.final_text = (f"I read '{seen['identifier']}' but it has no exact match in the vault. "
                                 "Please confirm the identifier.")
            return result
        ref = ident["item"]["item_ref"]
        if site:
            res = self._call(result, "check_mission_readiness", {"site": site, "drone_ref": ref})
            result.final_text = (f"Pre-flight check for {site}: {res['decision'].replace('_', '-').upper()}."
                                 + (" " + " ".join(res["reasons"]) if res["reasons"] else ""))
            return result
        if inspection:
            crit = self._call(result, "get_inspection_criteria", {"item_ref": ref})
            if crit.get("status") != "ok":
                result.final_text = crit.get("message", "No approved criteria.")
                return result
            ev = self._call(result, "evaluate_reading", {"item_ref": ref, "measurement_point": seen["measurement_point"],
                                                         "value": seen["value"], "unit": seen["unit"]})
            result.final_text = (f"{ident['item']['title']}: {seen['measurement_point']} reads {seen['value']} "
                                 f"{seen['unit']}, {ev['status'].replace('_', ' ')}.")
            return result
        if build_order:
            args = {"item_ref": ref, "build_order": build_order}
            if seen.get("label_revision"):
                args["label_revision"] = seen["label_revision"]
            res = self._call(result, "check_part_for_build", args)
            result.final_text = (f"{ident['item']['title']} for {build_order}: {res.get('decision', res.get('status'))}."
                                 + (" " + " ".join(res.get("reasons", [])) if res.get("reasons") else ""))
            return result
        blockers = self._call(result, "check_blockers", {"item_ref": ref})
        job = self._call(result, "get_approved_job", {"item_ref": ref, "task": task or ""})
        if blockers["status"] == "blocked":
            result.final_text = "Work is blocked. See blockers; a person must resolve them first."
        elif job.get("status") != "ok":
            result.final_text = job.get("message", "No approved job found.")
        else:
            result.final_text = (f"Identified {ident['item']['title']}. Approved procedure "
                                 f"{job['source']['title']} Rev {job['source']['revision']} applies.")
        return result
