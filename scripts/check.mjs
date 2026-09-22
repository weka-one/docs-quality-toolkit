#!/usr/bin/env node
/**
 * Quality gate for the site. Runs on every push; see .github/workflows/checks.yml.
 *
 *   node scripts/check.mjs            all checks
 *   node scripts/check.mjs --warnings fail on warnings too
 *
 * Four groups of checks:
 *
 *   structure   every project declared in assets/data.js has a page, every
 *               page declares a slug that exists, base paths are right
 *   links       local hrefs resolve on disk, in-page anchors exist, link
 *               text says something
 *   metadata    title, description, og tags, skip link, shared assets
 *   editorial   terminology and style rules from scripts/terminology.json
 *
 * Editorial rules are data, not code — add them to terminology.json.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const STRICT = process.argv.includes("--warnings");

const problems = [];
const report = (severity, file, line, message) =>
  problems.push({ severity, file: relative(ROOT, file), line, message });
const error = (...a) => report("error", ...a);
const warn = (...a) => report("warn", ...a);

/* ---------------------------------------------------------------
   Collect pages
   --------------------------------------------------------------- */
const pages = [];
(function walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (entry === ".git" || entry === "node_modules") continue;
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) walk(path);
    else if (entry.endsWith(".html")) pages.push(path);
  }
})(ROOT);

if (!pages.length) {
  console.error("No HTML pages found — is this the right directory?");
  process.exit(1);
}

const read = (p) => readFileSync(p, "utf8");
const lineOf = (text, index) => text.slice(0, index).split("\n").length;

/**
 * Editorial rules apply to prose, not to markup or URLs. Blanking tags in
 * place would keep line numbers accurate but leave runs of spaces behind,
 * which a "no double space" rule would then flag on every indented line.
 * So pull the text nodes out instead and keep each one's offset.
 */
const textNodesOf = (html) => {
  const blanked = html
    .replace(/<script[\s\S]*?<\/script>/gi, (m) => m.replace(/[^\n]/g, " "))
    .replace(/<style[\s\S]*?<\/style>/gi, (m) => m.replace(/[^\n]/g, " "))
    .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "));
  const nodes = [];
  for (const m of blanked.matchAll(/>([^<]+)</g)) {
    if (m[1].trim()) nodes.push({ text: m[1], at: m.index + 1 });
  }
  return { source: blanked, nodes };
};

/* Run the terminology rules over {text, at} nodes of a source string. */
const lintProse = (file, source, nodes) => {
  for (const rule of terminology.rules) {
    const re = new RegExp(rule.pattern, "g");
    for (const node of nodes) {
      for (const m of node.text.matchAll(re)) {
        report(rule.severity, file, lineOf(source, node.at + m.index),
          `${rule.id}: "${m[0]}" — prefer ${rule.prefer}`);
      }
    }
  }
};

/* ---------------------------------------------------------------
   Structure — projects declared in data.js vs pages on disk
   --------------------------------------------------------------- */
const dataPath = join(ROOT, "assets/data.js");
const dataSrc = read(dataPath);
const slugs = [...dataSrc.matchAll(/"?slug"?:\s*"([^"]+)"/g)].map((m) => m[1]);

if (!slugs.length) error(dataPath, 1, "No projects declared in PROJECTS");

for (const slug of slugs) {
  const page = join(ROOT, "portfolio", `${slug}.html`);
  if (!existsSync(page)) {
    error(dataPath, lineOf(dataSrc, dataSrc.indexOf(`"${slug}"`)),
      `project "${slug}" has no page at portfolio/${slug}.html`);
  }
}

/* Every project needs a nav label and a deck, or the cards render empty.
   Scoped to the PROJECTS array — SITE.samples reuses some field names.
   Keys may be quoted or not: the repo's hand-written form uses bare keys,
   the form edit mode writes back is JSON. */
const projectsBlock = dataSrc.match(/const PROJECTS = \[([\s\S]*?)\n\];/)?.[1] ?? "";
if (!projectsBlock) error(dataPath, 1, "could not find the PROJECTS array");

for (const field of ["nav", "title", "deck", "org"]) {
  const count = [...projectsBlock.matchAll(new RegExp(`^\\s*"?${field}"?:`, "gm"))].length;
  if (count !== slugs.length) {
    error(dataPath, 1,
      `${slugs.length} projects but ${count} "${field}" fields — every project needs one`);
  }
}

/* ---------------------------------------------------------------
   Per-page checks
   --------------------------------------------------------------- */
const terminology = JSON.parse(read(join(ROOT, "scripts/terminology.json")));

const anchorsByPage = new Map();
for (const page of pages) anchorsByPage.set(page, new Set(
  [...read(page).matchAll(/id="([^"]+)"/g)].map((m) => m[1])
));

for (const page of pages) {
  const html = read(page);
  const { source: blanked, nodes } = textNodesOf(html);
  const depth = relative(ROOT, page).split(sep).length - 1;
  const expectedBase = "../".repeat(depth);

  /* --- metadata --- */
  if (!/<html[^>]+lang=/.test(html)) error(page, 1, "<html> has no lang attribute");
  if (!/<title>[^<]+<\/title>/.test(html)) error(page, 1, "missing or empty <title>");
  for (const name of ["description", "og:title", "og:description"]) {
    const attr = name.startsWith("og:") ? "property" : "name";
    if (!new RegExp(`<meta ${attr}="${name}"[^>]*content="[^"]+"`).test(html)) {
      error(page, 1, `missing <meta ${attr}="${name}">`);
    }
  }
  if (!/class="skip"/.test(html)) error(page, 1, "missing skip-to-content link");

  /* --- shared assets and base path --- */
  for (const asset of ["assets/site.css", "assets/data.js", "assets/site.js"]) {
    if (!html.includes(expectedBase + asset)) {
      error(page, 1, `does not load ${expectedBase}${asset}`);
    }
  }
  const declaredBase = html.match(/data-base="([^"]*)"/)?.[1];
  if (declaredBase === undefined) error(page, 1, 'missing data-base on <body>');
  else if (declaredBase !== expectedBase) {
    error(page, lineOf(html, html.indexOf("data-base=")),
      `data-base is "${declaredBase}" but this file is ${depth} level(s) deep — expected "${expectedBase}"`);
  }

  const declaredPage = html.match(/data-page="([^"]*)"/)?.[1];
  if (!declaredPage) error(page, 1, "missing data-page on <body>");
  else if (!["home", "portfolio"].includes(declaredPage) && !slugs.includes(declaredPage)) {
    error(page, lineOf(html, html.indexOf("data-page=")),
      `data-page="${declaredPage}" is not a slug declared in assets/data.js`);
  }

  /* --- headings --- */
  const h1s = [...html.matchAll(/<h1[\s>]/g)];
  if (h1s.length !== 1) {
    error(page, h1s.length ? lineOf(html, h1s[1].index) : 1,
      `expected exactly one <h1>, found ${h1s.length}`);
  }

  /* --- images --- */
  for (const m of html.matchAll(/<img\b(?![^>]*\balt=)[^>]*>/g)) {
    error(page, lineOf(html, m.index), "<img> without an alt attribute");
  }

  /* --- links --- */
  for (const m of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    const url = m[1];
    const line = lineOf(html, m.index);
    if (/^(https?:|mailto:|data:|\/\/)/.test(url)) continue;

    const [path, hash] = url.split("#");
    const target = path ? resolve(dirname(page), path) : page;

    if (path && !existsSync(target)) {
      error(page, line, `broken link: ${url}`);
      continue;
    }
    if (hash) {
      const anchors = anchorsByPage.get(target);
      /* Anchors on other pages are only knowable for pages we parsed. */
      if (anchors && !anchors.has(hash)) {
        error(page, line, `link points at #${hash}, which does not exist in ${relative(ROOT, target)}`);
      }
    }
  }

  /* --- link text --- */
  for (const m of html.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)) {
    const text = m[1].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim().toLowerCase();
    if (!text) continue;
    if (terminology.linkText.banned.includes(text)) {
      warn(page, lineOf(html, m.index),
        `link text "${text}" does not say where it goes`);
    }
  }

  /* --- editorial rules --- */
  lintProse(page, blanked, nodes);

  /* --- whitespace --- */
  html.split("\n").forEach((l, i) => {
    if (/\s+$/.test(l)) warn(page, i + 1, "trailing whitespace");
  });
}

/* ---------------------------------------------------------------
   Case pages render from assets/cases.js, but each shell keeps a
   static kicker/title/deck for crawlers and no-JS readers. Those two
   copies drift the moment someone edits the live site, so check them.
   --------------------------------------------------------------- */
const casesPath = join(ROOT, "assets/cases.js");
if (existsSync(casesPath)) {
  const casesSrc = read(casesPath);
  for (const slug of slugs) {
    const page = join(ROOT, "portfolio", `${slug}.html`);
    if (!existsSync(page)) continue;
    const pageSrc = read(page);
    const block = casesSrc.slice(casesSrc.indexOf(`"${slug}": {`));
    for (const [field, sel] of [["title", "case__title"], ["kicker", "case__kicker"], ["deck", "case__deck"]]) {
      const want = block.match(new RegExp(`"${field}":\\s*"((?:[^"\\\\]|\\\\.)*)"`))?.[1];
      const got = pageSrc.match(new RegExp(`class="${sel}"[^>]*>([\\s\\S]*?)<`))?.[1]?.trim();
      if (want === undefined || got === undefined) continue;
      const norm = (t) => t.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
        .replace(/\\u2014/g, "\u2014").replace(/\\"/g, '"').replace(/\s+/g, " ").trim();
      if (norm(want) !== norm(got)) {
        error(page, lineOf(pageSrc, pageSrc.indexOf(`class="${sel}"`)),
          `static ${field} has drifted from assets/cases.js — re-sync the shell`);
      }
    }
  }
}

/* ---------------------------------------------------------------
   The rail nav is generated by site.js, so its targets appear in no
   HTML file and the per-page link check never sees them — which is
   most of the internal links on the site.
   --------------------------------------------------------------- */
const sitePath = join(ROOT, "assets/site.js");
const siteSrc = read(sitePath);
const homeIds = anchorsByPage.get(join(ROOT, "index.html")) ?? new Set();

const navTargets = [
  ...siteSrc.matchAll(/home\("#([\w-]+)"\)/g),
  ...siteSrc.matchAll(/isHome \? "#([\w-]+)"/g)
];
if (!navTargets.length) {
  warn(sitePath, 1, "found no generated nav targets — has the nav been rewritten?");
}
for (const m of navTargets) {
  if (!homeIds.has(m[1])) {
    error(sitePath, lineOf(siteSrc, m.index),
      `nav links to #${m[1]}, which is not an id in index.html`);
  }
}

/* ---------------------------------------------------------------
   assets/data.js holds reader-facing copy too, so the same rules
   apply to its string literals — minus the ones that are URLs.
   --------------------------------------------------------------- */
/* Not every string is prose: slugs and URLs are identifiers, and a slug
   like "tiktok-minis" is correct lowercase. Skip those fields by the key
   that precedes them, and skip anything shaped like a URL. */
const IDENTIFIER_FIELDS = new Set(["slug", "url", "resumeUrl"]);

lintProse(dataPath, dataSrc, [...dataSrc.matchAll(/"((?:[^"\\]|\\.)*)"/g)]
  .filter((m) => {
    if (/^(?:https?:)?\/\//.test(m[1])) return false;
    const key = dataSrc.slice(0, m.index).match(/"?(\w+)"?\s*:\s*$/)?.[1];
    return !(key && IDENTIFIER_FIELDS.has(key));
  })
  .map((m) => ({ text: m[1], at: m.index + 1 })));

/* ---------------------------------------------------------------
   Report
   --------------------------------------------------------------- */
const errors = problems.filter((p) => p.severity === "error");
const warnings = problems.filter((p) => p.severity === "warn");

const byFile = new Map();
for (const p of problems) {
  if (!byFile.has(p.file)) byFile.set(p.file, []);
  byFile.get(p.file).push(p);
}
for (const [file, list] of [...byFile].sort()) {
  console.log(`\n${file}`);
  for (const p of list.sort((a, b) => a.line - b.line)) {
    console.log(`  ${String(p.line).padStart(4)}  ${p.severity.padEnd(5)}  ${p.message}`);
  }
}

const counts = `${pages.length} pages, ${slugs.length} projects — ` +
  `${errors.length} error(s), ${warnings.length} warning(s)`;
console.log(problems.length ? `\n${counts}` : `clean: ${counts}`);

process.exit(errors.length || (STRICT && warnings.length) ? 1 : 0);
