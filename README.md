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
scripts/build.mjs           quality gate, then stage _site/ for deploy
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

## Deployment

Hosted on Cloudflare Pages, built from the private repository. Pushing
to `main` publishes; every pull request gets its own preview URL.

| Cloudflare setting | Value |
| --- | --- |
| Framework preset | None |
| Build command | `node scripts/build.mjs` |
| Build output directory | `_site` |
| Root directory | *(leave empty)* |
| `NODE_VERSION` | `22` |

`scripts/build.mjs` runs the quality gate first and exits non-zero if it
fails, which fails the Cloudflare build — so a broken link or a
terminology error never reaches the live site, and the previous
deployment keeps serving. Only then does it stage `index.html`,
`assets/` and `portfolio/` into `_site/`. The scripts, the workflow and
this README stay in the repository and off the web server.

`_site/` is generated and git-ignored. Run `node scripts/build.mjs`
locally to reproduce exactly what gets deployed.

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
