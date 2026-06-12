# Cross-Agent Adapter Notes

This skill is written in the Agent Skills format: a directory with `SKILL.md`, optional `references/`, and optional `scripts/`.

## Canonical Source

Keep the canonical package in:

```text
agent-pack/skills/pdf2md-rag-ingest/
```

Do not maintain hand-edited copies for each agent. Install by symlink or copy from the canonical source.

## Claude Code

Project-local:

```bash
python3 scripts/install_agent_skill_pack.py --clients claude --scope project --mode copy
```

Equivalent target:

```text
.claude/skills/pdf2md-rag-ingest/SKILL.md
```

Claude Code also supports direct slash invocation once installed:

```text
/pdf2md-rag-ingest
```

## Cline

Project-local:

```bash
python3 scripts/install_agent_skill_pack.py --clients cline --scope project --mode copy
```

Equivalent target:

```text
.cline/skills/pdf2md-rag-ingest/SKILL.md
```

Enable Cline Skills in Cline settings before relying on automatic activation.

## Roo Code

Roo can use either Roo-specific locations or cross-agent `.agents` locations.

```bash
python3 scripts/install_agent_skill_pack.py --clients roo,agents --scope project --mode copy
```

Equivalent targets:

```text
.roo/skills/pdf2md-rag-ingest/SKILL.md
.agents/skills/pdf2md-rag-ingest/SKILL.md
```

## Cursor

Cursor is best served with a project rule generated from the adapter template:

```bash
python3 scripts/install_agent_skill_pack.py --clients cursor --scope project --mode copy
```

Equivalent target:

```text
.cursor/rules/pdf2md-rag-ingest.mdc
```

Use the rule to point Cursor back to the canonical skill and project CLI commands. If Cursor's rule format changes, update only the adapter template.

## Continue

Continue can load project rules from `.continue/rules`.

```bash
python3 scripts/install_agent_skill_pack.py --clients continue --scope project --mode copy
```

Equivalent target:

```text
.continue/rules/pdf2md-rag-ingest.md
```

For tool execution, prefer a future MCP server or explicit terminal commands from this skill.
