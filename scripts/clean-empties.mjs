#!/usr/bin/env node
/**
 * Remove content emptied on the live site.
 *
 *   node scripts/clean-empties.mjs            report what would be removed
 *   node scripts/clean-empties.mjs --write    remove it
 *
 * Edit mode can blank a field but cannot delete the thing that held it:
 * emptying a paragraph in a contenteditable leaves "<br>", and emptying
 * both halves of a definition row leaves an empty row. Both render as
 * gaps. This turns "I deleted that text" into "that block is gone".
 *
 * A value counts as empty when nothing survives stripping tags, entities
 * and whitespace.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const WRITE = process.argv.includes("--write");
const removed = [];

const isBlank = (v) =>
  typeof v === "string" &&
  v.replace(/<[^>]*>/g, "")
    .replace(/&nbsp;| /g, " ")
    .trim() === "";

function load(file, name) {
  const src = readFileSync(join(ROOT, file), "utf8");
  return { src, value: new Function(`${src}; return ${name};`)() };
}

/* ---- case studies ---- */
const cases = load("assets/cases.js", "CASES");
for (const [slug, c] of Object.entries(cases.value)) {
  for (const key of ["meta", "stats"]) {
    const before = c[key].length;
    c[key] = c[key].filter((row) => Object.values(row).some((v) => v && !isBlank(v)));
    if (c[key].length !== before) removed.push(`${slug}: ${before - c[key].length} empty ${key} row(s)`);
  }

  c.body = c.body.filter((b, i) => {
    if (b.t === "table") {
      if (isBlank(b.caption) && b.caption !== "") { b.caption = ""; removed.push(`${slug}: emptied table caption`); }
      return true;
    }
    if (b.items) {
      const before = b.items.length;
      b.items = b.items.filter((it) => !isBlank(it));
      if (b.items.length !== before) removed.push(`${slug}: ${before - b.items.length} empty item(s) in ${b.t}`);
      if (!b.items.length) { removed.push(`${slug}: empty ${b.t} block at ${i}`); return false; }
      return true;
    }
    if (b.t === "figure") {
      if (!b.src) { removed.push(`${slug}: figure with no image at ${i}`); return false; }
      return true;
    }
    if (isBlank(b.html)) { removed.push(`${slug}: empty <${b.t}> at ${i}`); return false; }
    return true;
  });
}

/* ---- home page ---- */
const data = load("assets/data.js", "SITE");
const SITE = data.value;
for (const [path, arr] of [["about.aside", SITE.about.aside], ["contact.lines", SITE.contact.lines]]) {
  const before = arr.length;
  const kept = arr.filter((r) => !isBlank(r.label) || !isBlank(r.value));
  if (kept.length !== before) {
    removed.push(`home: ${before - kept.length} empty ${path} row(s)`);
    arr.length = 0; arr.push(...kept);
  }
}
for (const g of SITE.skills) {
  const before = g.items.length;
  g.items = g.items.filter((i) => !isBlank(i));
  if (g.items.length !== before) removed.push(`home: ${before - g.items.length} empty skill item(s)`);
}
for (const j of SITE.experience) {
  const before = j.points.length;
  j.points = j.points.filter((p) => !isBlank(p));
  if (j.points.length !== before) removed.push(`home: ${before - j.points.length} empty experience bullet(s)`);
}
SITE.about.paragraphs = SITE.about.paragraphs.filter((p) => !isBlank(p));
const projects = load("assets/data.js", "PROJECTS").value;
for (const p of projects) p.tags = p.tags.filter((t) => !isBlank(t));

console.log(removed.length ? removed.map((r) => "  " + r).join("\n") : "  nothing to remove");

if (WRITE && removed.length) {
  writeFileSync(join(ROOT, "assets/cases.js"),
    cases.src.slice(0, cases.src.indexOf("const CASES = ")) +
    "const CASES = " + JSON.stringify(cases.value, null, 2) + ";\n");
  writeFileSync(join(ROOT, "assets/data.js"),
    data.src.slice(0, data.src.indexOf("const PROJECTS = ")) +
    "const PROJECTS = " + JSON.stringify(projects, null, 2) + ";\n\n" +
    "const SITE = " + JSON.stringify(SITE, null, 2) + ";\n");
  console.log("\n  written");
}
