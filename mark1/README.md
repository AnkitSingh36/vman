# Mark-1

A phone-camera AI assistant that works like an experienced engineer standing next to you. It
recognises the exact unit, uses only approved knowledge from a (mock) M-Files-like vault, reasons
about faults, guides approved steps on the camera view, and earns autonomy from its proven record.

The AI decides what to look up and how to reason; the vault says what is true; fixed guardrails say
what is allowed.

> All data is fictional. No real M-Files vault is ever contacted. See [CLAUDE.md](CLAUDE.md) for the hard rules.

## Status
Skeleton. See [PLAN.md](PLAN.md).

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env     # add GEMINI_API_KEY
python -m pytest -q
```

## Demo
_To be written (BIOS update, overheating, training gym)._

## Layout
`mark1/{vault,bridge,engine,gym,planner,executor,webapp}`, `scripts/`, `samples/`, `tests/`, `docs/`.
