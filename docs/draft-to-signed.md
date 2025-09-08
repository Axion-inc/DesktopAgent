# Draft to Signed Pipeline

Planner outputs LLM draft proposals that are non-executable by design. This pipeline turns a draft into an executable, signed template.

## Stages

1. Static checks (lint): ensure `dsl` present, list `risk_flags`, require key assertions.
2. Dry-run ×3: run planner/verifier logic without side effects.
3. Signing: attach signature and metadata; only then the template becomes executable.
4. Registration: add to library with signature metadata.

See `app/planner/draft_flow.py` for a minimal reference implementation.

## Prohibitions

- Unsigned drafts must never execute.
- Dangerous actions must never be auto-added by patches.
- Respect policy/approval/signature before any real execution.

