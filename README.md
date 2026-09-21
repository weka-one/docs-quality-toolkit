# portfolio

Source for a personal portfolio site. Static HTML, CSS, and a little
JavaScript — no build step, no dependencies. Open `index.html` in a
browser and it works.

## Layout

```
index.html                  home
portfolio/index.html        portfolio index
portfolio/<slug>.html       one case study per project
assets/data.js              all content — the only file to edit for copy
assets/site.css             tokens, layout, components
assets/site.js              rail, cards, writing index, pager, scroll-spy
scripts/check.mjs           quality gate, run in CI
scripts/terminology.json    editorial rules the gate enforces
```

## Adding a project

Add an entry to `PROJECTS` in `assets/data.js`:

```js
{
  slug: "new-project",          // must match portfolio/new-project.html
  title: "Full title",          // used as the card heading
  nav: "Short label",           // used in the rail dropdown and pager
  org: "Organization · Surface",
  deck: "One sentence.",
  tags: ["Tag", "Tag"]
}
```

One entry wires the project into the rail dropdown, the home page
section, the portfolio index, and the prev/next pager on every case
page. Then copy an existing case study page, set `data-page` to the
slug, and write it.

Run `node scripts/check.mjs` before pushing.

## Quality gate

`scripts/check.mjs` runs on every push and pull request
(`.github/workflows/checks.yml`) and fails the build on errors. It is
plain Node with no dependencies.

**Structure** — every project declared in `data.js` has a page; every
page declares a slug that exists; `data-base` matches how deep the file
sits; every project has the fields the templates read.

**Links** — local links resolve on disk, and in-page anchors exist on
the page they point at. This includes the rail nav, which is generated
at runtime by `site.js` and so appears in no HTML file; its targets are
extracted from the source and checked against the home page.

**Metadata** — `lang`, `<title>`, meta description, Open Graph tags,
skip-to-content link, and the shared stylesheet and scripts, on every
page.

**Accessibility basics** — exactly one `<h1>` per page, `alt` on every
image, and link text that says where it goes.

**Editorial** — terminology and style rules from
`scripts/terminology.json`, applied to prose only, in both the HTML
pages and the reader-facing strings in `data.js`. Rules are data, not
code: add one to the JSON rather than to the script. Each rule carries
a severity — `error` fails the build, `warn` does not. Run with
`--warnings` to fail on warnings too.

Adding a rule:

```json
{ "id": "rule-name", "severity": "error",
  "pattern": "\\b(?:wrong|alsoWrong)\\b", "prefer": "Right" }
```
