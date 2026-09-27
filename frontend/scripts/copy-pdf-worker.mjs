// Copies pdf.js's worker into public/ as a plain static file, served
// directly by the browser's Worker() constructor. Bundling it through
// webpack instead (e.g. `new URL(..., import.meta.url)`) fails Next's
// production minifier, since the worker file uses top-level `import.meta`
// that Terser rejects outside of module code.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = join(
  __dirname,
  "..",
  "node_modules",
  "pdfjs-dist",
  "build",
  "pdf.worker.min.mjs"
);
const destDir = join(__dirname, "..", "public");
const dest = join(destDir, "pdf.worker.min.mjs");

mkdirSync(destDir, { recursive: true });
copyFileSync(source, dest);
console.log(`Copied pdf.js worker to ${dest}`);
