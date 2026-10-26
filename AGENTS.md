# Working rules for Scheduling Core

- Read `docs/VNEDU_TKB_CORE_FIRST_CODEX.md` and the phase requested by the user.
- Work on the standalone Python core in `src/tkb_core/`; keep external services,
  Desktop, SQLite and vnEdu schema assumptions outside it.
- Implement only the authorized phase. Phase 0 has contracts and input validation;
  it does not provide a solver, feasibility prechecks or independent schedule validation.
- Use synthetic fixtures and opaque string IDs. Never call vnEdu APIs or copy real
  personal data/credentials into fixtures or logs during core implementation.
- Keep `research/` and `reverse-engineering/` unchanged unless the user explicitly
  requests further research. Do not copy FET/STKB implementations into product code.
- Follow existing src layout. Public APIs have type hints/docstrings; reject unknown
  input fields and unsupported schema versions instead of ignoring them.
- Use `uv sync --locked --extra solver`, `uv run --extra solver pytest`, `uv run ruff check .`,
  `uv run ruff format --check src tests`, and `uv run mypy` before claiming completion.
- Add regression tests for validation/algorithm behavior; distinguish contract
  validation, feasibility, solver status and independent result validation.
- Pin dependency changes with `uv.lock`; runtime dependencies stay separate from dev.
- Report commands actually executed, test results, phase boundaries and limitations.
  Do not claim benchmark/performance results without measurements.
# Next Step Suggestions

After completing each task:
- Analyze the current project state.
- Suggest exactly one logical next action.
- Provide a ready-to-send Vietnamese prompt.
- Prioritize unfinished work, bugs, tests, and dependencies.
- Do not execute the suggested action automatically.

End every response with:

**Gợi ý tiếp theo:**
> [Prompt cụ thể để người dùng copy và gửi]
