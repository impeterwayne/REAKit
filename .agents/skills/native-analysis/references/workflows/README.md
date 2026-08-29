# GhidraMCP workflow playbooks

These are the upstream GhidraMCP workflow guides (function documentation, data-type
investigation, string labeling, orphaned-code discovery, plate comments, conventions).
They are written against the GhidraMCP **tool** names, which are the same as this repo's
REST endpoints. From the REA_Kit CLI, call any tool mentioned in a playbook as:

```bash
rea native call <tool_name> -p key=value       # e.g. rea native call rename_function -p ...
```

or use a short alias where one exists (see ../endpoints.md). Read a specific playbook only
when the task calls for it (e.g. renaming/commenting functions, labeling strings).

## Files
- `CUSTOMIZING_CONVENTIONS.md`
- `DATA_SECTION_WORKFLOW.md`
- `DATA_TYPE_INVESTIGATION_QUICK.md`
- `FUNCTION_DOC_WORKFLOW_V5.md`
- `FUNCTION_DOC_WORKFLOW_V5_BATCH.md`
- `GLOBAL_DATA_ANALYSIS_WORKFLOW.md`
- `ORPHANED_CODE_DISCOVERY_WORKFLOW.md`
- `PLATE_COMMENT_EXAMPLES.md`
- `QUICK_START_PROMPT.md`
- `STRING_LABELING_CONVENTION.md`
- `TOOL_USAGE_GUIDE.md`
