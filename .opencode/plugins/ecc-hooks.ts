/**
 * Everything Claude Code (ECC) Plugin Hooks for OpenCode
 *
 * This plugin translates Claude Code hooks to OpenCode's plugin system.
 * OpenCode's plugin system is MORE sophisticated than Claude Code with 20+ events
 * compared to Claude Code's 3 phases (PreToolUse, PostToolUse, Stop).
 *
 * Hook Event Mapping:
 * - PreToolUse → tool.execute.before
 * - PostToolUse → tool.execute.after
 * - Stop → session.idle / session.status
 * - SessionStart → session.created
 * - SessionEnd → session.deleted
 *
 * Superpowers-style features:
 * - config hook: registers skills/ path for skill tool auto-discovery
 * - experimental.chat.messages.transform: injects CLv2 bootstrap into first user message
 */

import type { PluginInput } from "@opencode-ai/plugin"
import * as fs from "fs"
import * as path from "path"
import { fileURLToPath } from "url"
import {
  initStore,
  recordChange,
  clearChanges,
} from "./lib/changed-files-store.js"
import changedFilesTool from "./tools/changed-files.js"
import { recordObservation } from "./lib/observation.js"

// Resolve project root by walking up from plugin dir until we find skills/
// This works regardless of runtime mode (TS source, compiled ESM) or install depth
const pluginDir = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = (() => {
  let dir = pluginDir
  for (let i = 0; i < 10; i++) {
    if (fs.existsSync(path.join(dir, "skills"))) return dir
    const parent = path.dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return pluginDir
})()
const projectSkillsDir = path.join(projectRoot, "skills")

// Simple frontmatter extraction (no dependencies needed at bootstrap time)
const extractAndStripFrontmatter = (content: string): { frontmatter: Record<string, string>; content: string } => {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  if (!match) return { frontmatter: {}, content }

  const frontmatter: Record<string, string> = {}
  for (const line of match[1].split("\n")) {
    const colonIdx = line.indexOf(":")
    if (colonIdx > 0) {
      const key = line.slice(0, colonIdx).trim()
      const value = line.slice(colonIdx + 1).trim().replace(/^["']|["']$/g, "")
      frontmatter[key] = value
    }
  }

  return { frontmatter, content: match[2].trimStart() }
}

type ECCHooksPluginFn = (input: PluginInput) => Promise<Record<string, unknown>>

export const ECCHooksPlugin: ECCHooksPluginFn = async ({
  client,
  $,
  directory,
  worktree,
}: PluginInput) => {
  type HookProfile = "minimal" | "standard" | "strict"

  const worktreePath = worktree || directory
  initStore(worktreePath)

  const editedFiles = new Set<string>()

  function resolvePath(p: string): string {
    if (path.isAbsolute(p)) return p
    return path.join(worktreePath, p)
  }

  function hasProjectFile(relativePath: string): boolean {
    try {
      return fs.existsSync(resolvePath(relativePath))
    } catch {
      return false
    }
  }

  const pendingToolChanges = new Map<string, { path: string; type: "added" | "modified" }>()
  let writeCounter = 0

  function getFilePath(args: Record<string, unknown> | undefined): string | null {
    if (!args) return null
    const p = (args.filePath ?? args.file_path ?? args.path) as string | undefined
    return typeof p === "string" && p.trim() ? p : null
  }

  // Helper to call the SDK's log API with correct signature
  const log = (level: "debug" | "info" | "warn" | "error", message: string) =>
    client.app.log({ body: { service: "ecc", level, message } })

  const normalizeProfile = (value: string | undefined): HookProfile => {
    if (value === "minimal" || value === "strict") return value
    return "standard"
  }

  const currentProfile = normalizeProfile(process.env.ECC_HOOK_PROFILE)
  const disabledHooks = new Set(
    (process.env.ECC_DISABLED_HOOKS || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  )

  const profileOrder: Record<HookProfile, number> = {
    minimal: 0,
    standard: 1,
    strict: 2,
  }

  const profileAllowed = (required: HookProfile | HookProfile[]): boolean => {
    if (Array.isArray(required)) {
      return required.some((entry) => profileOrder[currentProfile] >= profileOrder[entry])
    }
    return profileOrder[currentProfile] >= profileOrder[required]
  }

  const hookEnabled = (
    hookId: string,
    requiredProfile: HookProfile | HookProfile[] = "standard"
  ): boolean => {
    if (disabledHooks.has(hookId)) return false
    return profileAllowed(requiredProfile)
  }

  return {
    /**
     * Skills Path Registration (Superpowers-style)
     *
     * Registers the project skills/ directory so OpenCode's skill tool
     * auto-discovers all SKILL.md files. Currently registers:
     * - skills/continuous-learning-v2/ (CLv2)
     */
    config: async (config: Record<string, unknown>) => {
      // Register skills path (existing)
      const skillsConfig = (config.skills as Record<string, unknown>) || {}
      const paths = (skillsConfig.paths as string[]) || []
      if (!paths.includes(projectSkillsDir)) {
        paths.push(projectSkillsDir)
      }
      skillsConfig.paths = paths
      config.skills = skillsConfig

      // Register commands from commands/ directory
      // OpenCode does NOT read "command" from plugin-level opencode.json,
      // so we must register them via the config hook by mutating config.command.
      // See https://github.com/anomalyco/opencode/issues/24065
      const commandsDir = path.join(projectRoot, "commands")
      if (fs.existsSync(commandsDir)) {
        const commandConfig = ((config.command as Record<string, unknown>) || {})
        const files = fs.readdirSync(commandsDir)
        for (const file of files) {
          if (!file.endsWith(".md")) continue
          const name = file.replace(/\.md$/, "")
          // Don't override user-defined commands
          if (commandConfig[name]) continue
          const fullPath = path.join(commandsDir, file)
          const content = fs.readFileSync(fullPath, "utf8")
          const { frontmatter, content: body } = extractAndStripFrontmatter(content)
          commandConfig[name] = {
            template: body + "\n\n$ARGUMENTS",
            description: frontmatter.description || `ECC command: ${name}`,
          }
        }
        config.command = commandConfig
      }
    },

    /**
     * CLv2 Bootstrap Injection (Superpowers-style)
     *
     * Reads skills/continuous-learning-v2/SKILL.md and injects it into the
     * first user message so the AI is always aware of CLv2 capabilities.
     * Replaces the instructions field in opencode.json.
     */
    "experimental.chat.messages.transform": async (
      _input: unknown,
      output: { messages: Array<{ info: { role: string }; parts: Array<{ type: string; text: string }> }> }
    ) => {
      const skillPath = path.join(projectSkillsDir, "continuous-learning-v2", "SKILL.md")
      if (!fs.existsSync(skillPath)) return

      const fullContent = fs.readFileSync(skillPath, "utf8")
      const { content } = extractAndStripFrontmatter(fullContent)
      if (!content.trim()) return

      const bootstrap = `<EXTREMELY_IMPORTANT>
The CLv2 (Continuous Learning v2) skill content is included below. It is already loaded — you are following it. Do NOT use the skill tool to load it again — that would be redundant.

${content}
</EXTREMELY_IMPORTANT>`

      if (!output.messages?.length) return
      const firstUser = output.messages.find((m) => m.info?.role === "user")
      if (!firstUser || !firstUser.parts?.length) return
      // Only inject once per session
      if (firstUser.parts.some((p) => p.type === "text" && p.text.includes("EXTREMELY_IMPORTANT"))) return
      const ref = firstUser.parts[0]
      firstUser.parts.unshift({ ...ref, type: "text" as const, text: bootstrap })
    },

    /**
     * Prettier Auto-Format Hook
     * Equivalent to Claude Code PostToolUse hook for prettier
     *
     * Triggers: After any JS/TS/JSX/TSX file is edited
     * Action: Runs prettier --write on the file
     */
    "file.edited": async (event: { path: string }) => {
      editedFiles.add(event.path)
      recordChange(event.path, "modified")

      // Auto-format JS/TS files
      if (hookEnabled("post:edit:format", ["strict"]) && event.path.match(/\.(ts|tsx|js|jsx)$/)) {
        try {
          await $`prettier --write ${event.path} 2>/dev/null`
          log("info", `[ECC] Formatted: ${event.path}`)
        } catch {
          // Prettier not installed or failed - silently continue
        }
      }

      // Console.log warning check
      if (hookEnabled("post:edit:console-warn", ["standard", "strict"]) && event.path.match(/\.(ts|tsx|js|jsx)$/)) {
        try {
          const result = await $`grep -n "console\\.log" ${event.path} 2>/dev/null`.text()
          if (result.trim()) {
            const lines = result.trim().split("\n").length
            log(
              "warn",
              `[ECC] console.log found in ${event.path} (${lines} occurrence${lines > 1 ? "s" : ""})`
            )
          }
        } catch {
          // No console.log found (grep returns non-zero) - this is good
        }
      }
    },

    /**
     * TypeScript Check Hook
     * Equivalent to Claude Code PostToolUse hook for tsc
     *
     * Triggers: After edit tool completes on .ts/.tsx files
     * Action: Runs tsc --noEmit to check for type errors
     */
    "tool.execute.after": async (
      input: { tool: string; callID?: string; args?: { filePath?: string; file_path?: string; path?: string } },
      output: unknown
    ) => {
      const filePath = getFilePath(input.args as Record<string, unknown>)
      if (input.tool === "edit" && filePath) {
        recordChange(filePath, "modified")
      }
      if (input.tool === "write" && filePath) {
        const key = input.callID ?? `write-${++writeCounter}-${filePath}`
        const pending = pendingToolChanges.get(key)
        if (pending) {
          recordChange(pending.path, pending.type)
          pendingToolChanges.delete(key)
        } else {
          recordChange(filePath, "modified")
        }
      }

      if (hookEnabled("post:observe", ["standard", "strict"]) && input.tool !== "bash") {
        try {
          recordObservation(worktreePath, input.tool, input.args as Record<string, unknown> | undefined)
        } catch {
          // Observation failed silently
        }
      }

      // Check if a TypeScript file was edited
      if (
        hookEnabled("post:edit:typecheck", ["strict"]) &&
        input.tool === "edit" &&
        input.args?.filePath?.match(/\.tsx?$/)
      ) {
        try {
          await $`npx tsc --noEmit 2>&1`
          log("info", "[ECC] TypeScript check passed")
        } catch (error: unknown) {
          const err = error as { stdout?: string }
          log("warn", "[ECC] TypeScript errors detected:")
          if (err.stdout) {
            // Log first few errors
            const errors = err.stdout.split("\n").slice(0, 5)
            errors.forEach((line: string) => log("warn", `  ${line}`))
          }
        }
      }

      // PR creation logging
      if (
        hookEnabled("post:bash:pr-created", ["standard", "strict"]) &&
        input.tool === "bash" &&
        input.args?.toString().includes("gh pr create")
      ) {
        log("info", "[ECC] PR created - check GitHub Actions status")
      }
    },

    /**
     * Pre-Tool Security Check
     * Equivalent to Claude Code PreToolUse hook
     *
     * Triggers: Before tool execution
     * Action: Warns about potential security issues
     */
    "tool.execute.before": async (
      input: { tool: string; callID?: string; args?: Record<string, unknown> }
    ) => {
      if (input.tool === "write") {
        const filePath = getFilePath(input.args)
        if (filePath) {
          const absPath = resolvePath(filePath)
          let type: "added" | "modified" = "modified"
          try {
            if (typeof fs.existsSync === "function") {
              type = fs.existsSync(absPath) ? "modified" : "added"
            }
          } catch {
            type = "modified"
          }
          const key = input.callID ?? `write-${++writeCounter}-${filePath}`
          pendingToolChanges.set(key, { path: filePath, type })
        }
      }

      // Git push review reminder
      if (
        hookEnabled("pre:bash:git-push-reminder", "strict") &&
        input.tool === "bash" &&
        input.args?.toString().includes("git push")
      ) {
        log(
          "info",
          "[ECC] Remember to review changes before pushing: git diff origin/main...HEAD"
        )
      }

      // Block creation of unnecessary documentation files
      if (
        hookEnabled("pre:write:doc-file-warning", ["standard", "strict"]) &&
        input.tool === "write" &&
        input.args?.filePath &&
        typeof input.args.filePath === "string"
      ) {
        const filePath = input.args.filePath
        if (
          filePath.match(/\.(md|txt)$/i) &&
          !filePath.includes("README") &&
          !filePath.includes("CHANGELOG") &&
          !filePath.includes("LICENSE") &&
          !filePath.includes("CONTRIBUTING")
        ) {
          log(
            "warn",
            `[ECC] Creating ${filePath} - consider if this documentation is necessary`
          )
        }
      }

      // Long-running command reminder
      if (hookEnabled("pre:bash:tmux-reminder", "strict") && input.tool === "bash") {
        const cmd = String(input.args?.command || input.args || "")
        if (
          cmd.match(/^(npm|pnpm|yarn|bun)\s+(install|build|test|run)/) ||
          cmd.match(/^cargo\s+(build|test|run)/) ||
          cmd.match(/^go\s+(build|test|run)/)
        ) {
          log(
            "info",
            "[ECC] Long-running command detected - consider using background execution"
          )
        }
      }
    },

    /**
     * Session Created Hook
     * Equivalent to Claude Code SessionStart hook
     *
     * Triggers: When a new session starts
     * Action: Loads context and displays welcome message
     */
    "session.created": async () => {
      if (!hookEnabled("session:start", ["minimal", "standard", "strict"])) return

      log("info", `[ECC] Session started - profile=${currentProfile}`)

      // Check for project-specific context files
      if (hasProjectFile("CLAUDE.md")) {
        log("info", "[ECC] Found CLAUDE.md - loading project context")
      }
    },

    /**
     * Session Idle Hook
     * Equivalent to Claude Code Stop hook
     *
     * Triggers: When session becomes idle (task completed)
     * Action: Runs console.log audit on all edited files
     */
    "session.idle": async () => {
      if (!hookEnabled("stop:check-console-log", ["minimal", "standard", "strict"])) return
      if (editedFiles.size === 0) return

      log("info", "[ECC] Session idle - running console.log audit")

      let totalConsoleLogCount = 0
      const filesWithConsoleLogs: string[] = []

      for (const file of editedFiles) {
        if (!file.match(/\.(ts|tsx|js|jsx)$/)) continue

        try {
          const result = await $`grep -c "console\\.log" ${file} 2>/dev/null`.text()
          const count = parseInt(result.trim(), 10)
          if (count > 0) {
            totalConsoleLogCount += count
            filesWithConsoleLogs.push(file)
          }
        } catch {
          // No console.log found
        }
      }

      if (totalConsoleLogCount > 0) {
        log(
          "warn",
          `[ECC] Audit: ${totalConsoleLogCount} console.log statement(s) in ${filesWithConsoleLogs.length} file(s)`
        )
        filesWithConsoleLogs.forEach((f) =>
          log("warn", `  - ${f}`)
        )
        log("warn", "[ECC] Remove console.log statements before committing")
      } else {
        log("info", "[ECC] Audit passed: No console.log statements found")
      }

      // Desktop notification (macOS)
      try {
        await $`osascript -e 'display notification "Task completed!" with title "OpenCode ECC"' 2>/dev/null`
      } catch {
        // Notification not supported or failed
      }

      // Clear tracked files for next task
      editedFiles.clear()
    },

    /**
     * Session Deleted Hook
     * Equivalent to Claude Code SessionEnd hook
     *
     * Triggers: When session ends
     * Action: Final cleanup and state saving
     */
    "session.deleted": async () => {
      if (!hookEnabled("session:end-marker", ["minimal", "standard", "strict"])) return

      log("info", "[ECC] Session ended - cleaning up")
      editedFiles.clear()
      clearChanges()
      pendingToolChanges.clear()
    },

    /**
     * File Watcher Hook
     * OpenCode-only feature
     *
     * Triggers: When file system changes are detected
     * Action: Updates tracking
     */
    "file.watcher.updated": async (event: { path: string; type: string }) => {
      let changeType: "added" | "modified" | "deleted" = "modified"
      if (event.type === "create" || event.type === "add") changeType = "added"
      else if (event.type === "delete" || event.type === "remove") changeType = "deleted"
      recordChange(event.path, changeType)
      if (event.type === "change" && event.path.match(/\.(ts|tsx|js|jsx)$/)) {
        editedFiles.add(event.path)
      }
    },

    /**
     * Todo Updated Hook
     * OpenCode-only feature
     *
     * Triggers: When todo list is updated
     * Action: Logs progress
     */
    "todo.updated": async (event: { todos: Array<{ text: string; done: boolean }> }) => {
      const completed = event.todos.filter((t) => t.done).length
      const total = event.todos.length
      if (total > 0) {
        log("info", `[ECC] Progress: ${completed}/${total} tasks completed`)
      }
    },

    /**
     * Shell Environment Hook
     * OpenCode-specific: Inject environment variables into shell commands
     *
     * Triggers: Before shell command execution
     * Action: Sets PROJECT_ROOT, PACKAGE_MANAGER, DETECTED_LANGUAGES, ECC_VERSION
     */
    "shell.env": async () => {
      const instinctCliPath = path.join(
        projectRoot, "skills", "continuous-learning-v2", "scripts", "instinct-cli.py"
      )
      const env: Record<string, string> = {
        ECC_VERSION: "1.8.0",
        ECC_PLUGIN: "true",
        ECC_HOOK_PROFILE: currentProfile,
        ECC_DISABLED_HOOKS: process.env.ECC_DISABLED_HOOKS || "",
        ECC_INSTINCT_CLI: instinctCliPath,
        PROJECT_ROOT: worktreePath,
      }

      // Detect package manager
      const lockfiles: Record<string, string> = {
        "bun.lockb": "bun",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "package-lock.json": "npm",
      }
      for (const [lockfile, pm] of Object.entries(lockfiles)) {
        if (hasProjectFile(lockfile)) {
          env.PACKAGE_MANAGER = pm
          break
        }
      }

      // Detect languages
      const langDetectors: Record<string, string> = {
        "tsconfig.json": "typescript",
        "go.mod": "go",
        "pyproject.toml": "python",
        "Cargo.toml": "rust",
        "Package.swift": "swift",
      }
      const detected: string[] = []
      for (const [file, lang] of Object.entries(langDetectors)) {
        if (hasProjectFile(file)) {
          detected.push(lang)
        }
      }
      if (detected.length > 0) {
        env.DETECTED_LANGUAGES = detected.join(",")
        env.PRIMARY_LANGUAGE = detected[0]
      }

      return env
    },

    /**
     * Session Compacting Hook
     * OpenCode-specific: Control context compaction behavior
     *
     * Triggers: Before context compaction
     * Action: Push ECC context block and custom compaction prompt
     */
    "experimental.session.compacting": async () => {
      const contextBlock = [
        "# ECC Context (preserve across compaction)",
        "",
        "## Active Plugin: Everything Claude Code v2.0.0-rc.1",
        "- Hooks: file.edited, tool.execute.before/after, session.created/idle/deleted, shell.env, compacting, permission.ask",
        "- Tools: run-tests, check-coverage, security-audit, format-code, lint-check, git-summary, changed-files",
        "- Agents: 13 specialized (planner, architect, tdd-guide, code-reviewer, security-reviewer, build-error-resolver, e2e-runner, refactor-cleaner, doc-updater, go-reviewer, go-build-resolver, database-reviewer, python-reviewer)",
        "",
        "## Key Principles",
        "- TDD: write tests first, 80%+ coverage",
        "- Immutability: never mutate, always return new copies",
        "- Security: validate inputs, no hardcoded secrets",
        "",
      ]

      // Include recently edited files
      if (editedFiles.size > 0) {
        contextBlock.push("## Recently Edited Files")
        for (const f of editedFiles) {
          contextBlock.push(`- ${f}`)
        }
        contextBlock.push("")
      }

      return {
        context: contextBlock.join("\n"),
        compaction_prompt: "Focus on preserving: 1) Current task status and progress, 2) Key decisions made, 3) Files created/modified, 4) Remaining work items, 5) Any security concerns flagged. Discard: verbose tool outputs, intermediate exploration, redundant file listings.",
      }
    },

    /**
     * Permission Auto-Approve Hook
     * OpenCode-specific: Auto-approve safe operations
     *
     * Triggers: When permission is requested
     * Action: Auto-approve reads, formatters, and test commands; log all for audit
     */
    "permission.ask": async (event: { tool: string; args: unknown }) => {
      log("info", `[ECC] Permission requested for: ${event.tool}`)

      const cmd = String((event.args as Record<string, unknown>)?.command || event.args || "")

      // Auto-approve: read/search tools
      if (["read", "glob", "grep", "search", "list"].includes(event.tool)) {
        return { approved: true, reason: "Read-only operation" }
      }

      // Auto-approve: formatters
      if (event.tool === "bash" && /^(npx )?(prettier|biome|black|gofmt|rustfmt|swift-format)/.test(cmd)) {
        return { approved: true, reason: "Formatter execution" }
      }

      // Auto-approve: test execution
      if (event.tool === "bash" && /^(npm test|npx vitest|npx jest|pytest|go test|cargo test)/.test(cmd)) {
        return { approved: true, reason: "Test execution" }
      }

      // Everything else: let user decide
      return { approved: undefined }
    },

    tool: {
      "changed-files": changedFilesTool,
    },
  }
}

export default ECCHooksPlugin
