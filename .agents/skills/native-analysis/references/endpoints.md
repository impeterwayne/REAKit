# GhidraMCP endpoint schema (253 endpoints)

Every endpoint is callable from the CLI:

```bash
rea native call <endpoint-or-alias> [-p key=value ...] [-X POST] [--grep RE] [--limit N]
```
`-p` params map to the endpoint's parameters below. POST bodies are sent as JSON automatically.

Common ones also have short aliases: `program, functions, search-functions, decompile,
disassemble, strings, search-strings, imports, exports, segments, globals, xrefs-to,
xrefs-from, memory, switch`. In Git Bash, prefix a leading-slash path with `MSYS_NO_PATHCONV=1`.


## analysis — Analysis tools (34)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/analyze_api_call_chains` | program | Analyze API call chains |
| GET | `/analyze_call_graph` | start_function, end_function, analysis_type, program | Analyze function call graph patterns |
| GET | `/analyze_control_flow` | function_name, program | Analyze control flow |
| POST | `/analyze_data_region` | address, max_scan_bytes, include_xref_map, include_assembly_patterns, include_boundary_detection, program | Analyze data region |
| GET | `/analyze_dataflow` | address, variable, direction, max_steps, program | Trace value propagation through a function (PCode graph, forward/backward) |
| GET | `/analyze_for_documentation` | function_address, program | Composite RE documentation analysis (decompile + classify + variables + completeness) |
| GET | `/analyze_function_complete` | name, include_xrefs, include_callees, include_callers, include_disasm, include_variables, include_completeness, program | Comprehensive single-call function analysis. Accepts function name or address. |
| GET | `/analyze_function_completeness` | function_address, compact, addresses, program | Analyze documentation completeness |
| POST | `/analyze_struct_field_usage` | address, struct_name, max_functions, program | Analyze struct field usage |
| POST | `/apply_data_classification` | address, classification, name, comment, type_definition, program | Apply data classification |
| POST | `/batch_apply_documentation` | address, name, prototype, calling_convention, variable_types, variable_renames, plate_comment, decompiler_comments, disassembly_comments, goto, score, program | Apply all documentation to a function in one call |
| GET | `/can_rename_at_address` | address, program | Check if address can be renamed |
| POST | `/clear_instruction_flow_override` | address, program | Clear flow override |
| POST | `/configure_analyzer` | name, enabled, program | Configure an analysis plugin |
| POST | `/create_function` | address, name, disassemble_first, program | Create function at address |
| POST | `/create_memory_block` | name, address, size, read, write, execute, volatile, comment, program | Create memory block |
| POST | `/delete_function` | address, program | Delete function at address |
| POST | `/detect_array_bounds` | address, analyze_loop_bounds, analyze_indexing, max_scan_range, program | Detect array bounds |
| GET | `/detect_crypto_constants` | program | Detect crypto constants |
| GET | `/detect_malware_behaviors` | program | Detect malware behaviors |
| GET | `/extract_iocs_with_context` | program | Extract IOCs with context |
| GET | `/find_anti_analysis_techniques` | program | Find anti-analysis techniques |
| GET | `/find_code_gaps` | min_size, offset, limit, program | Find gaps of undefined bytes between functions in executable memory |
| GET | `/find_dead_code` | function_name, program | Find dead code |
| GET | `/find_next_undefined_function` | start_address, criteria, pattern, direction, program | Find next undefined function |
| POST | `/get_assembly_context` | xref_sources, context_instructions, include_patterns, program | Get assembly context |
| POST | `/get_field_access_context` | struct_address, field_offset, num_examples, program | Get field access context |
| GET | `/get_function_pcode` | function_address, granularity, program | Dump raw P-code for a function (issue #192). Returns low (basic-iter) and high (HighFunction) P-code with basic blocks and varn... |
| GET | `/inspect_memory_content` | address, length, detect_strings, program | Inspect memory bytes |
| GET | `/list_analyzers` | program | List available analysis plugins |
| GET | `/read_memory` | address, length, program | Read raw memory |
| POST | `/run_analysis` | program | Run auto-analysis on the current program |
| GET | `/search_instructions` | mnemonic, operand_pattern, function, limit, program | Search for instructions by mnemonic and/or operand substring. Complement to /search_byte_patterns (byte-level); this matches af... |
| POST | `/suggest_field_names` | struct_address, struct_size, program | Suggest field names |

## datatype — Data type operations (33)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/add_struct_field` | struct_name, field_name, field_type, offset, program | Add struct field |
| GET | `/analyze_global_completeness` | address, compact, program | Score a global variable's documentation completeness on a budgeted 0-100 scale â€” the data-address analog of analyze_function_... |
| POST | `/apply_data_type` | address, type_name, clear_existing, program, strict_mode | Apply data type |
| GET | `/audit_global` | address, program | Audit a global variable's documentation state. Returns name, type, length, plate comment, xref count, and list of issues. Use t... |
| GET | `/audit_globals_in_function` | address, program | Audit every global variable referenced from within a function in one call. Walks the function's instructions, collects unique d... |
| POST | `/clone_data_type` | source_type, new_name, program | Clone data type |
| POST | `/create_array_type` | base_type, length, name, program | Create array type |
| POST | `/create_data_type_category` | category_path, program | Create data type category |
| POST | `/create_enum` | name, values, size, program | Create enumeration |
| POST | `/create_function_signature` | name, return_type, parameters, program | Create function signature type |
| POST | `/create_pointer_type` | base_type, name, program | Create pointer type |
| POST | `/create_struct` | name, fields, replace_placeholder, program | Create structure. Body fields must be a JSON array of objects with name and type, plus optional decimal offset. Example fields:... |
| POST | `/create_typedef` | name, base_type, program | Create typedef |
| POST | `/create_union` | name, fields, program | Create union |
| POST | `/delete_data_type` | type_name, resolve_demangler_duplicate, program | Delete data type |
| POST | `/embed_struct_field` | parent_struct, field_name, embedded_struct, program | Replace a structure field with an embedded struct type by value (e.g. Rectangle inside LayoutNode). Uses modify_struct_field in... |
| GET | `/get_type_size` | type_name, program | Get data type size and info |
| POST | `/import_data_types` | source, format, program | Import data types from GDT |
| GET | `/list_data_type_categories` | offset, limit, program | List data type categories |
| GET | `/list_data_types` | category, offset, limit, program | List data types |
| POST | `/modify_struct_field` | struct_name, field_name, new_type, new_name, program | Modify struct field |
| POST | `/modify_struct_field_type` | struct_name, field_name, new_type, program | Set a structure field's type by name or offset (offset:N). Same as modify_struct_field with new_type only. |
| POST | `/move_data_type_to_category` | type_name, category_path, program | Move data type to category |
| POST | `/recreate_struct` | name, fields, size, replace_placeholder, force, program | Replace a structure in one step: optionally remove an existing same-named type, then create with fields JSON (same shape as cre... |
| POST | `/remove_struct_field` | struct_name, field_name, program | Remove struct field |
| POST | `/rename_data_type` | old_name, new_name, program | Rename a data type (struct, union, enum, typedef) in place, preserving existing applications of it |
| POST | `/resize_struct` | name, new_size, preserve_fields, force, program | Grow or shrink an existing structure by total byte size. Defined fields whose end offset fits within new_size are preserved; gr... |
| POST | `/resolve_duplicate_type` | type_name, delete_demangler_stub, program | Find duplicate data types by simple name; delete unused /Demangler size-1 stubs when a larger canonical type exists. Helps fix ... |
| POST | `/set_function_prototype` | function_address, prototype, calling_convention, program | Set function prototype (return type, param types, calling convention). NOTE: the function name in the prototype string does NOT... |
| POST | `/set_global` | address, name, type_name, array_length, plate_comment, program, strict_mode, allow_evict | Atomically apply name + type + plate-comment + array length to a global variable. Single-transaction; rejects on validation fai... |
| POST | `/set_variable_storage` | function_address, variable_name, storage, program | Set variable storage |
| GET | `/validate_data_type` | address, type_name, program | Validate data type syntax |
| GET | `/validate_function_prototype` | function_address, prototype, calling_convention, program | Validate function prototype |

## program — Program management (26)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/analysis_status` | program | Get auto-analysis status for open programs |
| POST | `/close_program` | name, save | Close an open program by project path or name. Never prompts interactively: unsaved changes are saved first by default (save=tr... |
| POST | `/create_property_map` | name, type, program | Create a user property map to store typed values keyed by address. Types: int, long, string, void (address-presence tag). Use a... |
| POST | `/delete_property_map` | name, program | Delete a user property map and all values it holds. Call save_program to persist. |
| POST | `/exit_ghidra` | — | Save and exit Ghidra |
| GET | `/get_address_spaces` | program | List all physical and overlay address spaces in the program (overlays include is_overlay flag and overlayed_space name) |
| GET | `/get_current_program_info` | program | Get current program info |
| GET | `/get_language_metadata` | include_registers, include_default_symbols, program | Dump the program's language description: address spaces, registers, default symbols, endianness, pointer size (issue #192). Use... |
| GET | `/get_program_options` | group, program | Read all options in a program option group with types, current values, defaults, and descriptions. Use list_option_groups to di... |
| GET | `/get_property` | map, address, program | Read the value stored at an address in a property map. Returns has_value=false and a null value when the address holds no prope... |
| POST | `/import_file` | file_path, project_folder, language, compiler_spec, auto_analyze | Import a binary file from disk into the current Ghidra project and open it. For raw firmware binaries, specify language (e.g. '... |
| GET | `/list_open_programs` | — | List open programs |
| GET | `/list_option_groups` | program | List program option groups (e.g. 'Program Information', 'Analyzers', 'Decompiler'). Each group holds typed keyâ†’value settings... |
| GET | `/list_project_files` | folder | List project files |
| GET | `/list_properties` | map, start, end, offset, limit, program | List (address, value) entries stored in a property map, with pagination. Optionally restrict to an inclusive address range with... |
| GET | `/list_property_maps` | program | List user-defined property maps â€” typed per-address keyâ†’value stores. Each map reports its name, value type (int\|long\|str... |
| GET | `/open_program` | path, auto_analyze | Open program from project |
| POST | `/reanalyze` | program | Trigger full auto-analysis on a program |
| POST | `/remove_program_option` | group, name, program | Remove an option from a program option group. Built-in registered options may be re-created with defaults by Ghidra; primarily ... |
| POST | `/remove_property` | map, address, program | Remove the value stored at a single address in a property map. Call save_program to persist. |
| GET | `/save_all_programs` | — | Save all open programs |
| GET | `/save_program` | program | Save current program |
| POST | `/set_image_base` | address, program | Set the base address of the program (rebases all addresses) |
| POST | `/set_program_option` | group, name, value, type, program | Set a typed program option. If the option already exists its type is reused; otherwise pass type (string\|int\|long\|double\|fl... |
| POST | `/set_property` | map, address, value, program | Set a value at an address in a property map. The value is coerced to the map's type (int/long/string); 'void' maps ignore the v... |
| GET | `/switch_program` | program | Switch current program |

## debugger (18)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/debugger/dynamic_to_static` | address | Translate a runtime dynamic address from the current trace back to a static Ghidra program address |
| POST | `/debugger/interrupt` | — | Interrupt (break into) the running target |
| POST | `/debugger/launch` | executable_path, args, cwd, timeout_seconds, program, offer, python_executable | Launch an executable through Ghidra's Trace RMI debugger launcher |
| GET | `/debugger/launch_offers` | program | List available debugger launch/attach options for the current program |
| GET | `/debugger/list_breakpoints` | — | List all breakpoints in the current trace |
| GET | `/debugger/modules` | — | List modules (DLLs/EXEs) loaded in the debugged process |
| GET | `/debugger/read_memory` | address, size | Read memory from the debugged process. Returns hex dump and DWORD interpretation. |
| GET | `/debugger/registers` | — | Read CPU registers from the current debug trace snapshot. Shows general-purpose registers (EAX-EDI, EIP, ESP, EFLAGS for x86) |
| POST | `/debugger/remove_breakpoint` | address | Remove a breakpoint at an address |
| POST | `/debugger/resume` | — | Resume execution of the debugged process |
| POST | `/debugger/set_breakpoint` | address | Set a software execution breakpoint at an address in the trace |
| GET | `/debugger/stack_trace` | depth | Get the call stack backtrace for the current thread |
| GET | `/debugger/static_to_dynamic` | address, program | Translate a static Ghidra program address to a runtime dynamic address in the current trace |
| GET | `/debugger/status` | — | Get debugger status: active trace, thread, execution state, module count |
| POST | `/debugger/step_into` | — | Single-step into the next instruction (follows calls) |
| POST | `/debugger/step_out` | — | Step out of the current function (run to return) |
| POST | `/debugger/step_over` | — | Step over the next instruction (does not follow calls) |
| GET | `/debugger/traces` | — | List all open debug traces |

## utility — Utility endpoints (18)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/apply_function_documentation` | json_body, program | Apply function documentation |
| GET | `/check_connection` | — | Health check endpoint |
| GET | `/compare_programs_documentation` | program | Compare documentation across programs |
| GET | `/convert_number` | text, size | Convert number between bases |
| GET | `/diff_functions` | address_a, address_b, program_a, program_b | Diff two functions |
| GET | `/find_undocumented_by_string` | address, program | Find undocumented functions referencing string |
| GET | `/get_bulk_function_hashes` | offset, limit, filter, program | Get bulk function hashes |
| GET | `/get_function_documentation` | address, program | Export function documentation |
| GET | `/get_function_hash` | address, program | Get function hash |
| GET | `/get_function_signature` | address, program | Get function feature signature |
| GET | `/get_metadata` | program | Get program metadata |
| GET | `/get_version` | — | Get plugin version |
| GET | `/health` | — | Health check endpoint for headless server |
| GET | `/mcp/health` | — | HTTP server health: pool stats, uptime, memory, active request count |
| GET | `/mcp/schema` | — | Machine-readable API schema with endpoint metadata |
| POST | `/tool/goto_address` | address | Navigate CodeBrowser listing and decompiler to a specific address |
| POST | `/tool/launch_codebrowser` | path | Open a file in CodeBrowser, launching a new one if needed |
| GET | `/tool/running_tools` | — | List all running Ghidra tool windows |

## getter — Get specific data (17)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/get_current_address` | — | Get cursor address (GUI only) |
| GET | `/get_current_function` | — | Get function at cursor (GUI only) |
| GET | `/get_current_selection` | — | Get highlighted address ranges in the CodeBrowser listing (GUI only). Returns {program, is_empty, ranges:[{start,end,length}], ... |
| GET | `/get_entry_points` | program | Get program entry points |
| GET | `/get_enum_values` | enum_name, program | Get enumeration values |
| GET | `/get_external_location` | address, dll_name, program | Get external location details |
| GET | `/get_full_call_graph` | format, limit, program | Get full call graph |
| GET | `/get_function_by_address` | address, program | Get function at address |
| GET | `/get_function_call_graph` | name, address, depth, direction, program | Get call graph |
| GET | `/get_function_callees` | name, address, offset, limit, program | Get functions called |
| GET | `/get_function_callers` | name, address, offset, limit, program | Get calling functions |
| GET | `/get_function_count` | program | Return the number of functions in the loaded program |
| GET | `/get_function_jump_targets` | name, address, offset, limit, program | Get jump targets |
| GET | `/get_function_labels` | name, offset, limit, program | Get labels in function |
| GET | `/get_function_variables` | function_name, address, program, limit, filter | List all variables in a function. Accepts function_name or address (address takes precedence). Use address to avoid name-lookup... |
| GET | `/get_struct_layout` | struct_name, program | Get structure layout |
| GET | `/get_valid_data_types` | category, program | Get valid data type names |

## listing — List program data (17)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/list_bookmarks` | category, address, program | List bookmarks |
| GET | `/list_calling_conventions` | program | List available calling conventions |
| GET | `/list_classes` | offset, limit, program | List namespace/class names |
| GET | `/list_data_items` | offset, limit, program | List defined data |
| GET | `/list_data_items_by_xrefs` | offset, limit, format, filter, type_filter, min_xrefs, include_all_sections, program | List data sorted by xref count |
| GET | `/list_exports` | offset, limit, program | List exported symbols |
| GET | `/list_external_locations` | offset, limit, program | List external locations |
| GET | `/list_functions` | program | List functions with addresses |
| GET | `/list_functions_enhanced` | offset, limit, program | List functions with metadata |
| GET | `/list_globals` | offset, limit, filter, type_filter, min_xrefs, include_all_sections, name_substring, program | List global variables |
| GET | `/list_imports` | offset, limit, program | List imported symbols |
| GET | `/list_methods` | offset, limit, program | List all function names with pagination |
| GET | `/list_namespaces` | offset, limit, program | List all namespaces |
| GET | `/list_scripts` | filter | List available Ghidra scripts |
| GET | `/list_segments` | offset, limit, program | List memory segments |
| GET | `/list_shadowed_globals` | offset, limit, include_all_sections, program | List named global DATA symbols that have NO type of their own because a larger data unit starting at an earlier address covers ... |
| GET | `/list_strings` | offset, limit, filter, program | List defined strings |

## server — Server connection and version control (17)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/server/admin/set_permissions` | repo, user, accessLevel | Set user permissions on a repository |
| POST | `/server/admin/terminate_all_checkouts` | repo, path | Terminate all checkouts in a folder recursively |
| POST | `/server/admin/terminate_checkout` | repo, path, checkoutId, checkout_id | Terminate all checkouts on a single file |
| GET | `/server/admin/users` | — | List all users on the server |
| POST | `/server/authenticate` | username, password | Register server credentials for programmatic authentication |
| GET | `/server/checkouts` | path | List all checked-out files in a folder, including server-side checkouts |
| POST | `/server/connect` | host, port | Connect to a Ghidra server |
| POST | `/server/disconnect` | — | Disconnect from the Ghidra server |
| GET | `/server/repositories` | — | List repositories on the connected server |
| POST | `/server/repository/create` | name | Create a new repository on the server |
| GET | `/server/repository/file` | repo, path | Get file info from a server repository |
| GET | `/server/repository/files` | repo, path | List files in a server repository folder |
| POST | `/server/version_control/add` | repo, path, comment, keepCheckedOut | Add a file to version control |
| POST | `/server/version_control/checkin` | repo, path, comment, keepCheckedOut | Check in a version-controlled file |
| POST | `/server/version_control/checkout` | repo, path | Check out a version-controlled file |
| POST | `/server/version_control/undo_checkout` | repo, path | Undo a file checkout |
| GET | `/server/version_history` | repo, path | Get version history for a file |

## function (14)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/add_function_tag` | function, tags, assignments, program | Attach one or more tags to a function. Tags are comma-separated and will be auto-created if they do not already exist. |
| POST | `/clear_flow_and_repair` | start_address, end_address, program | Run Ghidra's GUI 'Clear Flow and Repair' action on a seed range: clears instruction flow reachable from the seed, then repairs ... |
| POST | `/create_function_tag` | name, comment, program | Create a program-wide function tag definition with an optional comment. Use add_function_tag to attach it to functions. |
| POST | `/delete_function_tag` | name, program | Delete a program-wide function tag definition. This detaches the tag from every function that had it. |
| GET | `/get_function_tags` | function, program | List all tags assigned to a specific function. Accepts either a function address or a function name. |
| GET | `/list_class_members` | class_name, offset, limit, program | List the member functions of a C++ class. A function counts as a member if it lives in the class's namespace (e.g. after set_fu... |
| GET | `/list_function_tags` | offset, limit, program | List all program-wide function tag definitions with their use counts. |
| POST | `/remove_function_tag` | function, tags, assignments, program | Detach one or more tags from a function. Does not delete the program-wide tag definition â€” use delete_function_tag for that. |
| GET | `/search_functions_by_tag` | tag, offset, limit, program | List all functions that have a specified tag attached. Returns name + entry address. |
| POST | `/set_function_no_return` | function_address, no_return, program | Set no-return attribute |
| POST | `/set_function_tag_comment` | name, comment, program | Update the comment/description on an existing program-wide function tag. |
| POST | `/set_function_this_type` | function_address, this_type, program | Set the decompiler/database type of the implicit 'this' pointer (ECX on x86 __thiscall/__fastcall). Use after set_function_prot... |
| POST | `/set_variable_type` | function_address, variable_name, new_type, program | Set the data type of a function variable (local OR parameter) by name at the decompiler (high-level) layer. Pass variable_name=... |
| POST | `/set_variables` | function_address, variables, program | Set types and names for multiple variables atomically. Types are applied first, then renames, in a single transaction. Hungaria... |

## headless (12)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/archive_project` | output_dir, output_name | Archive the currently open project to a Ghidra-native .gar file. The result can be restored into any Ghidra GUI via File â†’ Re... |
| POST | `/checkin_program` | path, comment, keep_checked_out | Check an open program back in to the shared Ghidra Server as a new version |
| POST | `/close_project` | — | Close the currently open project |
| POST | `/create_project` | parentDir, name | Create a new Ghidra project |
| POST | `/export_program` | program_name, output_dir, output_name | Export an open or project-resident program to a Ghidra Zip File (.gzf). Looks up the program in the open-programs map first (so... |
| GET | `/get_project_info` | — | Get info about the currently open project |
| POST | `/import_program` | gzf_path, target_folder, target_name, overwrite | Import a Ghidra Zip File (.gzf) into the currently open project as a new DomainFile under target_folder (default '/'). Refuses ... |
| POST | `/load_program` | file, language, compiler_spec | Load a binary file into the headless server for analysis. For raw firmware (no recognizable header), pass `language` (e.g. 'ARM... |
| POST | `/load_program_from_project` | path | Load program from Ghidra project (headless) |
| POST | `/open_project` | path, headless, program | Open an existing Ghidra project (.gpr file or directory). GUI mode adds optional `headless` (default true) to suppress auto-lau... |
| POST | `/restore_project` | gar_path, parent_dir, project_name | Restore a Ghidra .gar archive into a fresh on-disk project at `parent_dir/project_name`. Closes any currently-open project firs... |
| GET | `/server/status` | — | Check headless server connection status |

## comment — Set comments (7)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/batch_get_comments` | addresses, only_with_comments, program | Get listing comments (plate/pre/eol/post/repeatable) at MANY addresses in one call. Same per-address shape as get_comment. Pass... |
| POST | `/batch_set_comments` | address, decompiler_comments, disassembly_comments, plate_comment, program | Set multiple comments |
| POST | `/clear_function_comments` | address, clear_plate, clear_pre, clear_eol, program | Clear all comments for a function |
| POST | `/delete_bookmark` | address, category, program | Delete bookmark |
| GET | `/get_comment` | address, program | Get listing comments (plate/pre/eol/post/repeatable) at ANY address, including data addresses (works on functions and data glob... |
| POST | `/set_bookmark` | address, category, comment, program | Set bookmark |
| POST | `/set_comment` | address, comment, type, program | Set a listing comment of a given kind (plate/pre/eol/post/repeatable) at ANY address, including data addresses. Symmetric write... |

## project — Project lifecycle management (7)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/create_folder` | path, program | Create a folder in the project |
| POST | `/delete_file` | filePath | Delete a file from the project |
| POST | `/delete_project` | projectPath | Delete a Ghidra project |
| GET | `/list_projects` | searchDir | List available Ghidra projects |
| POST | `/move_file` | filePath, destFolder | Move a program file to a different folder in the project, preserving analysis and documentation. Refuses on unsaved changes; cl... |
| POST | `/move_folder` | sourcePath, destPath | Move a project folder and everything under it into another folder. Refuses to move a folder into itself or its own descendant. |
| GET | `/project/info` | — | Get detailed project info including running tools and open programs |

## documentation (6)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/archive_ingest_function` | address, program, version_override, dry_run | Ingest a single function's documentation into the cross-version archive (re_kb.functions on bsim Postgres). Idempotent; field-l... |
| POST | `/archive_ingest_program` | program, version_override, limit, skip_default_named, dry_run | Bulk-ingest every function in a program into the cross-version documentation archive. Posts each to /v1/doc_archive/upsert. Ret... |
| GET | `/batch_string_anchor_report` | pattern, program | Report of source file strings and their FUN_* functions |
| GET | `/bulk_fuzzy_match` | source_program, target_program, threshold, offset, limit, filter | Bulk cross-binary function matching |
| GET | `/find_similar_functions_fuzzy` | address, source_program, target_program, threshold, limit | Cross-binary fuzzy function matching. On programs with multiple address spaces (e.g., embedded targets), prefix addresses with ... |
| POST | `/merge_program_documentation` | source, target, dry_run | Bulk merge: copy all RE documentation (function names, signatures, plate comments, instruction comments at EOL/PRE/POST, non-de... |

## search — Search functionality (6)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/find_similar_functions` | target_function, threshold, program | Find similar functions |
| GET | `/search_byte_patterns` | pattern, mask, program | Search for byte patterns |
| GET | `/search_data_types` | pattern, offset, limit, program | Search data types |
| GET | `/search_functions` | name_pattern, offset, limit, program | Search functions by name |
| GET | `/search_functions_enhanced` | name_pattern, min_xrefs, max_xrefs, calling_convention, has_custom_name, is_thunk, is_external, regex, sort_by, offset, limit, program | Advanced function search |
| GET | `/search_strings` | search_term, min_length, encoding, offset, limit, program | Search defined strings by a regex/substring pattern |

## xref — Cross-references (6)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/add_memory_reference` | from_address, to_address, ref_type, source_type, operand_index, program | Create a user-defined cross-reference between two memory addresses that the auto-analyzer can't infer (runtime-populated pointe... |
| POST | `/get_bulk_xrefs` | addresses, program | Get xrefs for multiple addresses |
| GET | `/get_function_xrefs` | name, address, offset, limit, program | Get function cross-references |
| GET | `/get_xrefs_from` | address, offset, limit, program | Get references from address |
| GET | `/get_xrefs_to` | address, offset, limit, program | Get references to address |
| POST | `/remove_reference` | from_address, to_address, operand_index, program | Remove memory cross-reference(s) from one address to another â€” the inverse of add_memory_reference. Removes every reference f... |

## rename — Rename symbols (5)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/batch_rename_function_components` | function_address, function_name, parameter_renames, local_renames, return_type, program | Batch rename function components |
| POST | `/create_label` | address, name, labels, program | Create label |
| POST | `/delete_label` | address, name, labels, program | Delete label at address |
| POST | `/rename_function` | old_name, new_name, program, strict_mode | Rename function by name |
| POST | `/rename_variables` | function_address, variable_renames, force_individual, program | Batch rename variables |

## decompile — Decompilation/disassembly (4)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| GET | `/decompile_function` | address, functions, program, timeout | Decompile function |
| POST | `/disassemble_bytes` | start_address, end_address, length, restrict_to_execute_memory, include_instructions, max_instructions, program | Disassemble byte range |
| GET | `/disassemble_function` | address, program | Disassemble function |
| GET | `/force_decompile` | address, program | Force fresh decompilation |

## emulation — P-code emulation (run functions with controlled inputs) (2)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/emulate_function` | address, registers, memory, max_steps, return_registers, read_memory_after, program | Emulate a single function with controlled register/memory inputs. Returns final register state after execution. Ideal for under... |
| POST | `/emulate_hash_batch` | hash_function_address, string_register, result_register, target_hash, candidates, initial_registers, wide_string, program | Brute-force API hash resolution. Emulates a hash function with each candidate API name and returns the one that produces the ta... |

## script — Script execution (2)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/run_ghidra_script` | script_name, args, timeout_seconds, capture_output, program | Run script with output capture |
| POST | `/run_script_inline` | code, args, program | Run inline script code |

## symbol (1)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/rename_symbol` | target, new_name, kind, old_name, program | Rename a symbol of any kind. kind=auto (default): an address target routes to rename-or-create-label (handles data/label/any sy... |

## system (1)

| Method | Endpoint | Params | Description |
|---|---|---|---|
| POST | `/prompt_policy` | action, reason, seconds | Temporarily enable, disable, or query scoped automation prompt handling |
