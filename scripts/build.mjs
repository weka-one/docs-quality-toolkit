/* =================================================================
   Build for Cloudflare Pages.

   Cloudflare fails a deployment when the build command exits non-zero,
   so running the quality gate here is what keeps a broken link off the
   live site: the deploy stops and the previous version keeps serving.

   Then stage the site into _site/ — the pages and what they load, not
   the scripts, the workflows or the README.
   ================================================================= */
import { spawnSync } from "node:child_process";
import { rm, mkdir, cp } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "_site");
const SHIP = ["index.html", "assets", "portfolio"];

/* Before the gate, so a stale build is never what gets checked. */
await rm(OUT, { recursive: true, force: true });

const gate = spawnSync(process.execPath, [join(ROOT, "scripts/check.mjs")], {
  stdio: "inherit",
  cwd: ROOT,
});
if (gate.status !== 0) {
  console.error("\nQuality gate failed — nothing was built. "
    + "The live site keeps serving the last good version.");
  process.exit(gate.status ?? 1);
}

await mkdir(OUT, { recursive: true });
for (const entry of SHIP) {
  await cp(join(ROOT, entry), join(OUT, entry), { recursive: true });
}
console.log(`\nStaged ${SHIP.join(", ")} into _site/`);
