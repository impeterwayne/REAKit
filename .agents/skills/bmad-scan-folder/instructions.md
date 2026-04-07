# Folder Scan Workflow Router

<critical>Communicate all responses in {communication_language}</critical>

<workflow>

<critical>This router mirrors `bmad-document-project` deep-dive mode while requiring an explicit folder target instead of interactive target selection.</critical>

<step n="1" goal="Validate requested deep-dive target and determine whether to resume">
<action>Receive the `target_folder` from the user or invoking prompt.</action>
<action>Validate that `target_folder` is provided, resolves to an existing folder, and is inside `{project-root}` unless the user explicitly requests otherwise.</action>
<action>Normalize and store as `deep_dive_target_path`.</action>
<action>Derive `deep_dive_target_name` from the folder name or relative path.</action>
<action>Set `workflow_mode = "deep_dive"`.</action>
<action>Set `scan_level = "exhaustive"`.</action>
<action>Set `autonomous = "true"`.</action>

<action>Check for existing state file at: {project_knowledge}/project-scan-report.json</action>

<check if="project-scan-report.json exists">
  <action>Read state file and extract: timestamps, mode, scan_level, current_step, completed_steps, deep_dive_targets</action>
  <action>Calculate age of state file (current time - last_updated)</action>

  <check if="state file age < 24 hours AND mode == deep_dive">
    <action>Check whether `deep_dive_target_path` already appears in `deep_dive_targets` or resume context.</action>

    <check if="deep_dive_target_path does not appear in deep_dive_targets or resume context">
      <action>Display: "Found a recent deep-dive state for a different target. Starting a fresh deep-dive for {{deep_dive_target_path}} instead of reusing unrelated state."</action>
      <action>Create archive directory: {project_knowledge}/.archive/</action>
      <action>Move old state file to: {project_knowledge}/.archive/project-scan-report-{{timestamp}}.json</action>
      <action>Set resume_mode = false</action>
    </check>

    <check if="deep_dive_target_path appears in deep_dive_targets or resume context">

    <ask>I found an in-progress deep-dive workflow state from {{last_updated}}.

**Requested Target Folder:** {{deep_dive_target_path}}

Would you like to:

1. **Resume from current state** - Continue using the existing deep-dive workflow state
2. **Start fresh** - Archive old state and begin a new deep-dive for this folder
3. **Cancel** - Exit without changes

Your choice [1/2/3]:
</ask>

    <check if="user selects 1">
      <action>Set resume_mode = true</action>
      <action>Display: "Resuming deep-dive workflow for {{deep_dive_target_path}} from {{current_step}}"</action>
      <action>Read fully and follow: ./workflows/deep-dive-workflow.md with resume context</action>
    </check>

    <check if="user selects 2">
      <action>Create archive directory: {project_knowledge}/.archive/</action>
      <action>Move old state file to: {project_knowledge}/.archive/project-scan-report-{{timestamp}}.json</action>
      <action>Set resume_mode = false</action>
    </check>

    <check if="user selects 3">
      <action>Display: "Exiting workflow without changes."</action>
      <action>Exit workflow</action>
    </check>
    </check>
  </check>

  <check if="state file age < 24 hours AND mode != deep_dive">
    <action>Display: "Found a recent non-deep-dive workflow state. Archiving it before starting an explicit folder deep-dive scan."</action>
    <action>Create archive directory: {project_knowledge}/.archive/</action>
    <action>Move old state file to: {project_knowledge}/.archive/project-scan-report-{{timestamp}}.json</action>
    <action>Set resume_mode = false</action>
  </check>

  <check if="state file age >= 24 hours">
    <action>Display: "Found old state file (>24 hours). Starting fresh deep-dive scan."</action>
    <action>Create archive directory: {project_knowledge}/.archive/</action>
    <action>Move old state file to: {project_knowledge}/.archive/project-scan-report-{{timestamp}}.json</action>
    <action>Set resume_mode = false</action>
  </check>
</check>

<check if="project-scan-report.json does not exist">
  <action>Set resume_mode = false</action>
</check>

</step>

<step n="2" goal="Start explicit-folder deep-dive mode" if="resume_mode == false">
  <action>Display: "Starting deep-dive documentation mode for explicit folder target {{deep_dive_target_path}}..."</action>
  <action>Read fully and follow: ./workflows/deep-dive-workflow.md</action>
</step>

</workflow>
