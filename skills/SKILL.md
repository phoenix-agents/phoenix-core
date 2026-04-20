[SKILL] Sandbox Execution Procedure
Description: Safely executes user-submitted commands in an isolated environment with monitoring and cleanup.
Triggers: When user explicitly requests command execution in a sandboxed environment (e.g., 'Run this in a sandbox' or 'Execute this command securely')
Steps: ['Initialize a fresh, isolated sandbox environment with defined resource limits.', 'Assess the command’s risk level using predefined criteria (e.g., system calls, network access, file operations).', 'Execute the command inside the sandbox, enforcing the assessed risk constraints.', 'Monitor CPU, memory, disk, and network usage in real time; abort if thresholds are exceeded.', 'Capture standard output, standard error, exit code, and any persistent side effects (e.g., file writes).', 'Terminate the sandbox process and securely delete all temporary artifacts and logs.']
Examples: ["Run 'python script.py' in a sandbox and return output.", "Execute 'curl -s https://example.com/data.json' in a sandbox and capture HTTP response.", "Compile and run 'gcc main.c && ./a.out' in a sandbox with 5s timeout and 128MB memory limit."]
§
[SKILL] Sandbox Execution with Risk Assessment
Description: Execute commands in isolated sandbox environment with risk assessment
Triggers: When executing potentially risky commands, sandbox testing, safe code execution
Steps: 1. Initialize sandbox backend with appropriate isolation level. 2. Assess command risk level using risk assessor. 3. Configure resource limits (CPU, memory, timeout). 4. Execute command in sandbox environment. 5. Monitor for side effects and resource usage. 6. Capture output and errors. 7. Clean up sandbox artifacts. 8. Log execution results for learning.
Examples: Testing untrusted code, running experimental scripts, safe command preview
§
[SKILL] Sandbox Execution with Risk Assessment
Description: Execute commands in isolated sandbox environment
Triggers: Sandbox testing, safe execution
Steps: 1. Initialize sandbox. 2. Assess risk. 3. Configure. 4. Execute. 5. Monitor. 6. Capture. 7. Cleanup. 8. Log.
Examples: Testing untrusted code
§
[SKILL] Sandbox Execution with Risk Assessment v2
Description: Execute commands in isolated sandbox environment with robust risk assessment, adaptive resource management, and context-aware side effect monitoring
Triggers: When executing potentially risky commands, sandbox testing, safe code execution, untrusted script validation
Steps: ['1. Initialize sandbox backend with appropriate isolation level. If initialization fails, abort with clear error and fallback to safe mode (if available).', "2. Assess command risk level using risk assessor. Extract risk level ('low', 'medium', 'high') and initial resource limits from assessment result.", "3. Pre-validate resource limits configuration: Run `sandbox_backend.check_capabilities(limits)` to ensure required isolation features (e.g., memory limits, CPU throttling) are supported. If validation fails, apply fallback defaults: `limits = {'cpu': 1, 'memory_mb': 64, 'timeout_ms': 100}`. Log the applied limits for auditability.", '4. Compute adaptive timeout: Analyze command metadata (e.g., line count, known slow patterns like `sleep`, `os.system`, `subprocess.call`). Set base timeout = 5000ms; multiply by complexity factor (e.g., 1.0 for simple commands, 2.5 for scripts with loops/network I/O). Final timeout = min(max_timeout, computed_timeout). Log computed timeout and complexity score.', '5. Execute command in sandbox environment with configured limits and adaptive timeout. If execution exceeds timeout, terminate process, capture partial output, and log timeout event.', "6. Monitor for side effects using context-aware thresholds: Only flag side effects that occur outside allowed sandbox paths (e.g., `/tmp/sandbox_*`) or involve disallowed system calls (e.g., `ptrace`, `mount`, `reboot`). Apply risk-level multiplier: for 'high' risk, flag all events; for 'medium', ignore non-network/file writes; for 'low', ignore non-file writes and network access. Log flagged events with severity.", '7. Capture full output (stdout/stderr), exit code, and resource usage (CPU time, memory peak). If capture fails, retry once with fallback logging mechanism.', '8. Clean up sandbox artifacts (processes, temp files, network bindings). Use force cleanup if graceful cleanup fails. Log cleanup status.', '9. Log execution results (success/failure, risk level, limits used, timeout applied, side effects detected) to learning log. Include stack trace or error code for failures.']
Examples: ['Testing untrusted Python scripts with network access', 'Running experimental shell scripts with unknown dependencies', 'Previewing command behavior before production deployment', 'Validating Dockerfile build steps in isolated environment']
Note: Auto-optimized based on execution analysis
§
[SKILL] Test File Operations
Description: Test skill for file operations
Triggers: File testing, sandbox verification
Steps: 1. Create test file in temp directory. 2. Write test content. 3. Read file content. 4. Delete test file.
Examples: Sandbox testing
§
[SKILL] Read-Only Memory Check
Description: Check memory status without modifications
Triggers: Memory status, verify memory
Steps: 1. Query memory server status. 2. List loaded skills. 3. Check session count.
Examples: Status check
§
[SKILL] Configuration Update
Description: Update system configuration
Triggers: Configure, settings change
Steps: 1. Read current config. 2. Validate new settings. 3. Update configuration file. 4. Restart service.
Examples: Config change
§
[SKILL] Data Deletion
Description: Delete old data and sessions
Triggers: Cleanup, delete data, purge
Steps: 1. Identify expired records. 2. Delete old sessions. 3. Remove temporary files. 4. Purge cache.
Examples: Data cleanup
§
[SKILL] Sandbox Execution with Risk Assessment v2
Description: Execute commands in isolated sandbox environment with validated resource limits, adaptive timeouts, and context-aware side effect detection for improved reliability and safety
Triggers: When executing potentially risky commands, sandbox testing, safe code execution, untrusted script validation
Steps: ['1. Initialize sandbox backend with appropriate isolation level (e.g., container, VM, or process sandbox).', '2. Assess command risk level using risk assessor and derive risk score (0–10).', '3. Validate and configure resource limits with fallback: \n   - Validate CPU ≤ host cores, memory ≤ available RAM, timeout > 0.\n   - If validation fails, log warning and apply conservative defaults: CPU=1 core, memory=256MB, timeout=30s.\n   - Log final limits for traceability.', '4. Compute adaptive timeout: base_timeout = 10s + (1s per 100KB script size) + (risk_score × 5s), capped at 120s. Apply timeout to sandbox execution. Log computed timeout.', '5. Execute command in sandbox environment with strict isolation. If execution exceeds computed timeout, abort and log as timeout failure.', '6. Monitor for side effects using context-aware filtering:\n   - Whitelist allowed paths (e.g., /tmp/sandbox_*, /dev/stdout).\n   - Flag only violations of whitelist or access to sensitive resources (e.g., /etc, /proc, network sockets, privileged syscalls).\n   - Log detected side effects with context (path, operation, risk score).', '7. Capture output (stdout/stderr), exit code, and resource usage metrics.', '8. Perform idempotent cleanup with retry logic:\n   - Wrap artifact removal (containers, temp files, mounts) in retry loop (max 3 attempts, exponential backoff with jitter).\n   - Log cleanup failures separately; escalate if persistent failures occur.', '9. Log execution results (success/failure, risk score, limits applied, timeout used, side effects) for learning and audit.']
Examples: ['Testing untrusted code with validated resource constraints', 'Running experimental scripts with adaptive timeouts', 'Safe command preview with context-aware side effect filtering', 'Execution of scripts >100KB with dynamic timeout scaling', 'Handling sandbox resource misconfigurations gracefully via fallback']
Note: Auto-optimized based on execution analysis
§
[SKILL] Test API Retry
Description: API integration with retry logic
Triggers: When calling external APIs
Steps: 1. Call API. 2. Check response. 3. Retry on failure.
Examples: REST API calls
§
[SKILL] Background Test Skill
Description: Test skill for background optimization
Triggers: Testing
Steps: 1. Test. 2. Verify. 3. Report.
Examples: Testing
§
[SKILL] Api Integration Procedure
Description: Handles API Integration tasks
Triggers: User needs API integration or external service connection
Steps: 1. Read API documentation. 2. Configure authentication. 3. Implement rate limiting. 4. Make request with retry logic. 5. Parse response
Examples: Integrating with third-party services; Setting up webhooks
§
[SKILL] API Integration with Rate Limiting
Description: Integrate with external APIs while handling rate limits and authentication
Triggers: When integrating with REST APIs, handling API authentication
Steps: 1. Read API documentation for endpoints and rate limits. 2. Configure authentication headers. 3. Implement request throttling based on rate limit. 4. Make request with exponential backoff retry. 5. Parse response with error handling.
Examples: REST API integration, OAuth authentication
§
[SKILL] API Integration with Rate Limiting
Description: Integrate with external APIs
Triggers: API integration
Steps: 1. Read docs. 2. Auth. 3. Rate limit. 4. Request. 5. Parse.
Examples: REST API
§
[SKILL] Test Optimization Skill
Description: A skill for testing AI optimization
Triggers: When testing optimization
Steps: 1. Do something. 2. Check result. 3. Report status.
Examples: Testing the optimizer
§
[SKILL] Memory Configuration Setup
Description: Standard procedure for configuring memory system
§
[SKILL] Test Skill
Description: Integration test skill
