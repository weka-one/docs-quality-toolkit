#!/usr/bin/env node
/**
 * Rewrite each case page's static fallback from assets/cases.js.
 *
 * A case page renders from the data file, but keeps a static kicker,
 * title and deck for crawlers and readers without JavaScript. Editing
 * the live site changes only the data file, so the two drift apart —
 * scripts/check.mjs fails when they do, and this puts them back.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const casesSrc = readFileSync(join(ROOT, "assets/cases.js"), "utf8");
const CASES = new Function(`${casesSrc}; return CASES;`)();
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

let changed = 0;
for (const [slug, c] of Object.entries(CASES)) {
  const file = join(ROOT, "portfolio", `${slug}.html`);
  if (!existsSync(file)) continue;
  const before = readFileSync(file, "utf8");

  const after = before
    .replace(/(<p class="case__kicker">)[\s\S]*?(<\/p>)/, `$1${esc(c.kicker)}$2`)
    .replace(/(<h1 class="case__title">)[\s\S]*?(<\/h1>)/, `$1${esc(c.title)}$2`)
    .replace(/(<p class="case__deck">)[\s\S]*?(<\/p>)/, `$1${esc(c.deck)}$2`)
    .replace(/(<title>)[\s\S]*?(<\/title>)/, `$1${esc(c.title)} — Wesley Kao$2`)
    .replace(/(<meta name="description" content=")[^"]*(")/, `$1${esc(c.description).replace(/"/g, "&quot;")}$2`)
    .replace(/(<meta property="og:title" content=")[^"]*(")/, `$1${esc(c.title).replace(/"/g, "&quot;")}$2`);

  if (after !== before) { writeFileSync(file, after); changed++; console.log(`  synced ${slug}`); }
}
console.log(changed ? `\n  ${changed} shell(s) updated` : "  shells already match the data");
