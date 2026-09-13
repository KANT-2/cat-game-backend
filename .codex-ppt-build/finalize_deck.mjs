import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const SKILL_DIR = "C:/Users/tkdwo/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const workspaceDir = "C:/dev/cat-game-backend";
const candidatePath = path.join(workspaceDir, ".codex-ppt-build", "candidate.pptx");
const finalPath = path.join(workspaceDir, "output", "고양이게임_통합발표_프론트엔드_백엔드_17장.pptx");
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
const { finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });

const result = await finalizePresentation({
  explicitTotalSlideCount: 17,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: "C:/Users/tkdwo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: { basis: "design", families: ["Noto Sans KR"] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "cat-game-17slides.validation.json"),
});

console.log(JSON.stringify(result, null, 2));
