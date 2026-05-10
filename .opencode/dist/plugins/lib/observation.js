import { execSync } from "child_process";
import * as crypto from "crypto";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
const SECRET_KEY_RE = /api[_-]?key|token|secret|password|authorization|credentials?|auth/i;
const SECRET_VALUE_RE = new RegExp(`(${SECRET_KEY_RE.source})` +
    `(?:["'\\s:=]+)` +
    `((?:[A-Za-z]+\\s+)?[A-Za-z0-9_\\-/.+=]{8,})`, "gi");
const HOMUNCULUS_DIR_NAME = "homunculus";
function getEccDataDir() {
    return process.env.ECC_DATA_DIR || path.join(os.homedir(), ".opencode");
}
function getGitRoot(cwd) {
    try {
        const result = execSync("git rev-parse --show-toplevel", {
            cwd,
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            timeout: 5000,
        });
        return result.trim().replace(/\/+$/, "");
    }
    catch {
        return null;
    }
}
function getGitRemoteUrl(projectRoot) {
    try {
        const result = execSync("git remote get-url origin", {
            cwd: projectRoot,
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
            timeout: 5000,
        });
        return result.trim();
    }
    catch {
        return "";
    }
}
function getProjectId(projectRoot) {
    const remoteUrl = getGitRemoteUrl(projectRoot);
    const hashSource = remoteUrl || projectRoot;
    return crypto.createHash("sha256").update(hashSource, "utf8").digest("hex").slice(0, 12);
}
function detectProject(worktree) {
    const eccDataDir = getEccDataDir();
    const homunculusDir = path.join(eccDataDir, HOMUNCULUS_DIR_NAME);
    const projectsDir = path.join(homunculusDir, "projects");
    const projectRoot = getGitRoot(worktree);
    if (!projectRoot) {
        return {
            id: "global",
            name: "global",
            root: "",
            projectDir: homunculusDir,
            observationsFile: path.join(homunculusDir, "observations.jsonl"),
        };
    }
    const projectId = getProjectId(projectRoot);
    const projectName = path.basename(projectRoot);
    const projectDir = path.join(projectsDir, projectId);
    return {
        id: projectId,
        name: projectName,
        root: projectRoot,
        projectDir,
        observationsFile: path.join(projectDir, "observations.jsonl"),
    };
}
function scrubArgs(args) {
    if (!args)
        return null;
    try {
        const str = JSON.stringify(args);
        return SECRET_VALUE_RE.test(str) ? str.replace(SECRET_VALUE_RE, "$1$2[REDACTED]") : str;
    }
    catch {
        return JSON.stringify(args);
    }
}
export function recordObservation(worktree, toolName, args) {
    const project = detectProject(worktree);
    fs.mkdirSync(project.projectDir, { recursive: true });
    const observation = {
        timestamp: new Date().toISOString(),
        event: "tool_complete",
        tool: toolName,
        args: scrubArgs(args),
        project_id: project.id,
        project_name: project.name,
    };
    fs.appendFileSync(project.observationsFile, JSON.stringify(observation) + "\n");
}
//# sourceMappingURL=observation.js.map