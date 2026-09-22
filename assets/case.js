/* =================================================================
   Case study rendering. Each portfolio/<slug>.html is a shell; its
   content lives in assets/cases.js under that slug, so edit mode can
   write it back by republishing the data file rather than the page.

   Two kinds of editable field:
     data-edit       plain text  — read and written as textContent
     data-edit-html  rich text   — inline <strong>/<em>/<a>/<code>
   ================================================================= */
(function () {
  const slug = document.body.dataset.page;
  const root = document.getElementById("case");
  if (!root || typeof CASES === "undefined" || !CASES[slug]) return;

  const c = CASES[slug];
  const esc = (s) => String(s).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const p = (...keys) => `CASES.${slug}.${keys.join(".")}`;

  /* Keep the tab title and description in step with the edited copy. */
  document.title = `${c.title} — Wesley Kao`;
  const desc = document.querySelector('meta[name="description"]');
  if (desc && c.description) desc.setAttribute("content", c.description);

  const block = (b, i) => {
    switch (b.t) {
      case "h2":
      case "h3":
        return `<${b.t} data-edit-html="${p("body", i, "html")}">${b.html}</${b.t}>`;
      case "p":
        return `<p data-edit-html="${p("body", i, "html")}">${b.html}</p>`;
      case "ul":
      case "ol":
        return `<${b.t}>${b.items.map((it, k) =>
          `<li data-edit-html="${p("body", i, "items", k)}">${it}</li>`).join("")}</${b.t}>`;
      case "pull":
        return `<div class="pull">${b.items.map((it, k) =>
          `<p data-edit-html="${p("body", i, "items", k)}">${it}</p>`).join("")}</div>`;
      case "table":
        return `<table class="tbl">
          ${b.caption ? `<caption data-edit-html="${p("body", i, "caption")}">${b.caption}</caption>` : ""}
          <thead><tr>${b.head.map((h, k) =>
            `<th scope="col" data-edit="${p("body", i, "head", k)}">${esc(h)}</th>`).join("")}</tr></thead>
          <tbody>${b.rows.slice(0, -1).map((row, r) =>
            `<tr>${row.map((cell, k) =>
              `<td data-edit-html="${p("body", i, "rows", r, k)}">${cell}</td>`).join("")}</tr>`).join("")}</tbody>
          <tfoot>${b.rows.slice(-1).map((row, r) =>
            `<tr>${row.map((cell, k) =>
              `<td data-edit-html="${p("body", i, "rows", b.rows.length - 1, k)}">${cell}</td>`).join("")}</tr>`).join("")}</tfoot>
        </table>`;
      default:
        return "";
    }
  };

  root.innerHTML = `
    <a class="case__back" href="index.html">&larr; Portfolio</a>
    <p class="case__kicker" data-edit="${p("kicker")}">${esc(c.kicker)}</p>
    <h1 class="case__title" data-edit="${p("title")}">${esc(c.title)}</h1>
    <p class="case__deck" data-edit="${p("deck")}">${esc(c.deck)}</p>

    <dl class="meta">
      ${c.meta.map((row, i) => `
        <div>
          <dt data-edit="${p("meta", i, "label")}">${esc(row.label)}</dt>
          <dd>${row.href
            ? `<a href="${esc(row.href)}" data-edit="${p("meta", i, "value")}">${esc(row.value)}</a>`
            : `<span data-edit="${p("meta", i, "value")}">${esc(row.value)}</span>`}</dd>
        </div>`).join("")}
    </dl>

    <dl class="stats">
      ${c.stats.map((s, i) => `
        <div>
          <dt data-edit-html="${p("stats", i, "value")}">${s.value}</dt>
          <dd data-edit="${p("stats", i, "label")}">${esc(s.label)}</dd>
        </div>`).join("")}
    </dl>

    <div class="prose">${c.body.map(block).join("\n")}</div>

    <nav class="pager" id="pager" aria-label="More projects"></nav>`;
})();
