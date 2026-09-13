import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/dev/cat-game-backend/.codex-ppt-build/source_48.pptx";
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({
  kind: "deck,slide,textbox,image,layout",
  include: "id,slide,name,title,text,textPreview,bbox,layoutId,isPlaceholder,alt",
  maxChars: 200000,
});
await fs.writeFile("C:/dev/cat-game-backend/.codex-ppt-build/source-inspect.ndjson", snapshot.ndjson, "utf8");
const help = presentation.help("slide delete remove duplicate move", {
  include: ["index", "examples", "notes"],
  maxChars: 12000,
});
await fs.writeFile("C:/dev/cat-game-backend/.codex-ppt-build/slide-help.txt", String(help), "utf8");
console.log(`slides=${presentation.slides.items.length}`);
console.log(`masters=${presentation.masters.items.length}`);
console.log(`layouts=${presentation.layouts.items.length}`);
