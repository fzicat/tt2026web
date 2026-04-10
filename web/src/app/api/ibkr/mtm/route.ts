import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";

const execFileAsync = promisify(execFile);

function resolveProjectRoot(): string {
  const cwd = process.cwd();
  return path.basename(cwd) === "web" ? path.resolve(cwd, "..") : cwd;
}

export async function POST() {
  try {
    const projectRoot = resolveProjectRoot();
    const pythonBin = process.env.PYTHON_BIN || "python3";
    const scriptPath = path.join(projectRoot, "cli", "quote_refresh.py");

    const { stdout, stderr } = await execFileAsync(pythonBin, [scriptPath], {
      cwd: projectRoot,
      env: process.env,
      timeout: 60_000,
      maxBuffer: 1024 * 1024,
    });

    if (stderr?.trim()) {
      console.warn("MTM refresh stderr:", stderr.trim());
    }

    const payload = JSON.parse(stdout.trim() || "{}") as {
      ok?: boolean;
      message?: string;
      statuses?: Record<string, number>;
      provider_messages?: string[];
      requested_equities?: number;
      requested_options?: number;
      invalid_contracts?: number;
      save_result?: Record<string, number>;
    };

    if (!payload.ok) {
      return NextResponse.json(
        { error: payload.message || "MTM update failed", details: payload },
        { status: 500 }
      );
    }

    return NextResponse.json(payload);
  } catch (err) {
    console.error("MTM update error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "MTM update failed" },
      { status: 500 }
    );
  }
}
