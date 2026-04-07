# Deep-Dive Folder Scan Sub-Workflow

**Goal:** Exhaustive deep-dive documentation of a specific target folder.

**Your Role:** Deep-dive documentation specialist.
- Deep-dive mode requires literal full-file review. Sampling, guessing, or relying solely on tooling output is FORBIDDEN.

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve:

- `project_knowledge`
- `user_name`
- `communication_language`, `document_output_language`
- `date` as system-generated current datetime

✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the configured `{communication_language}`.
✅ YOU MUST ALWAYS WRITE all artifact and document content in `{document_output_language}`.

### Runtime Inputs

- `workflow_mode` = `deep_dive`
- `scan_level` = `exhaustive`
- `autonomous` = `true` (explicit folder target is already provided)
- `target_type` = `folder`
- `target_path` = `deep_dive_target_path`
- `target_name` = `deep_dive_target_name`

---

## EXECUTION

Read fully and follow: `./deep-dive-instructions.md`
