# Cross-Agent Adapter Notes

This skill is written in the Agent Skills format: a directory with `SKILL.md`, optional `references/`, and optional `scripts/`.

## Canonical Source

Keep the canonical package in:

```text
agent-pack/skills/pdf2md-rag-ingest/
```

Do not maintain hand-edited copies for each agent. Install by symlink or copy from the canonical source.
After changing this Skill or any reference file, run an overwrite dry-run before
regenerating installed targets:

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy --overwrite --dry-run
```

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

Use the rule to point Cursor back to the canonical skill and project CLI commands. Keep the rule thin; do not duplicate the full sidecar contract outside `agent-pack/skills/pdf2md-rag-ingest/references/`. If Cursor's rule format changes, update only the adapter template.

## Continue

Continue can load project rules from `.continue/rules`.

```bash
python3 scripts/install_agent_skill_pack.py --clients continue --scope project --mode copy
```

Equivalent target:

```text
.continue/rules/pdf2md-rag-ingest.md
```

For tool execution, prefer the local stdio MCP server when the client supports MCP. Use explicit terminal commands from
this skill when MCP is unavailable. For large PDFs, MCP clients should prefer the page-window tools documented in
`docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md`.
Keep the Continue rule thin; do not duplicate the full sidecar contract outside
the canonical Skill references.
