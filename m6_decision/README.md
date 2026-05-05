# M6 Decision Engine

Current status: **placeholder only**.

The original SeeFire report defines M6 as the FSM that should coordinate:
- sensor fusion
- navigation commands
- alarm transitions
- snapshot/logging flow

That orchestration is **not implemented in this repository yet**.

## What Exists Today

- `m6_decision/__init__.py` placeholder
- `m6_decision/decision.py` placeholder
- header draft from the original module plan

## What M6 Is Expected To Do Later

- consume M3 fusion data
- consume M4 fire/smoke inference output
- command M5 navigation
- command M2 alarm outputs
- log events through M7

## Important Note

Do not treat older FSM documentation as live runtime behavior. It is still design intent, not current implementation.
