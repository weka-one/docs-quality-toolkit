/* =================================================================
   Edit mode — only for viewers who can write this artifact.

   Every editable string on the page carries data-edit="PATH", where
   PATH addresses the value in assets/data.js (e.g.
   "SITE.about.paragraphs.0" or "PROJECTS.2.deck"). Turning edit mode
   on makes those elements contenteditable; Save collects them, writes
   the values back into a copy of the data, regenerates data.js and
   publishes it as the artifact's new version.

   Only the DATA FILE is republished — the page and stylesheet are
   untouched — so the document is never serialized from the live DOM.

   Outside a published artifact (opened from disk, or by a viewer who
   cannot write) claude.use("artifact") resolves null and this file
   does nothing: the page stays exactly as it was.
   ================================================================= */
(function () {

  const $ = (sel) => document.querySelector(sel);
  const fields = () => [...document.querySelectorAll("[data-edit],[data-edit-html]")];
  const isRich = (el) => el.hasAttribute("data-edit-html");
  const pathOf = (el) => el.dataset.editHtml || el.dataset.edit;

  /* Rich fields keep inline markup. Anything outside this allowlist —
     pasted styling, stray divs, scripts — is flattened to its text. */
  const ALLOWED = { STRONG: [], EM: [], CODE: [], BR: [], A: ["href"] };
  function sanitize(node) {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === Node.TEXT_NODE) continue;
      if (child.nodeType !== Node.ELEMENT_NODE) { child.remove(); continue; }
      const keep = ALLOWED[child.tagName];
      if (!keep) {
        sanitize(child);
        child.replaceWith(...child.childNodes);
        continue;
      }
      for (const attr of [...child.attributes]) {
        if (!keep.includes(attr.name)) child.removeAttribute(attr.name);
      }
      const href = child.getAttribute("href");
      if (href && !/^(https?:|mailto:|#|\.{0,2}\/)/i.test(href)) child.removeAttribute("href");
      sanitize(child);
    }
  }
  function cleanHtml(el) {
    const box = document.createElement("div");
    box.innerHTML = el.innerHTML;
    /* Belt and braces: editing chrome is never content. */
    for (const n of box.querySelectorAll(".blocktools,.sheet-back,.editbar")) n.remove();
    sanitize(box);
    return box.innerHTML.replace(/\s+/g, " ").trim();
  }

  /* ---- read and write a value by its dotted path ---- */
  const roots = () => (typeof CASES === "undefined" ? { SITE, PROJECTS } : { SITE, PROJECTS, CASES });
  function setPath(data, path, value) {
    const keys = path.split(".");
    let node = data[keys[0]];
    for (const k of keys.slice(1, -1)) node = node[k];
    node[keys[keys.length - 1]] = value;
  }

  /* ---- regenerate assets/data.js from the current data ---- */
  function serialize(data) {
    return `/* =================================================================
   CONTENT — the only file you need to edit to change what the site says.

   Last written by the site's own edit mode. Values here are plain data;
   the page renders from them, and edit mode writes back to them.
   ================================================================= */

const PROJECTS = ${JSON.stringify(data.PROJECTS, null, 2)};

const SITE = ${JSON.stringify(data.SITE, null, 2)};
`;
  }

  function serializeCases(cases) {
    return `/* =================================================================
   CASE STUDIES — one entry per project in PROJECTS, keyed by slug.
   Each case page renders from here, and edit mode writes back here.
   ================================================================= */

const CASES = ${JSON.stringify(cases, null, 2)};
`;
  }

  /* Publish only the data files whose content actually changed. A case
     page has both loaded; the home page has only data.js. */
  let baseline = null;
  function filesFor(data) {
    const next = { "assets/data.js": serialize(data) };
    if (data.CASES) next["assets/cases.js"] = serializeCases(data.CASES);
    const files = {};
    for (const [path, src] of Object.entries(next)) {
      if (!baseline || baseline[path] !== src) files[path] = src;
    }
    return files;
  }

  /* Block edits (adding an image, removing a block) change the data
     directly, so the page is redrawn from it and edit mode re-applied. */
  let dirty = false;
  function rerender() {
    const keep = editing;
    if (keep) setEditing(false);
    if (typeof renderCase === "function") {
      renderCase();
      if (typeof window.renderPager === "function") window.renderPager();
    }
    if (keep) setEditing(true);
  }
  const markDirty = () => { dirty = true; status("Unsaved changes", "warn"); };

  let artifact = null;
  let editing = false;
  const original = new Map();

  function setEditing(on) {
    editing = on;
    document.body.classList.toggle("is-editing", on);
    for (const el of fields()) {
      if (on) original.set(el, isRich(el) ? el.innerHTML : el.textContent);
      if (!on) el.classList.toggle("is-empty", el.textContent.trim() === "");
      el.contentEditable = on ? (isRich(el) ? "true" : "plaintext-only") : "inherit";
      if (!on) el.removeAttribute("contenteditable");
    }
    const prose = document.querySelector("#case");
    if (prose) {
      if (window.EditImages && EditImages.ready) {
        EditImages.teardown();
        if (on) EditImages.decorate(prose);
      }
    }
    $("#editbar").hidden = !on;
    $("#edit-toggle").textContent = on ? "Cancel" : "Edit text";
    if (!on) for (const [el, was] of original) {
      if (isRich(el)) el.innerHTML = was; else el.textContent = was;
    }
    if (!on) original.clear();
  }

  function status(text, tone) {
    const el = $("#edit-status");
    el.textContent = text;
    el.dataset.tone = tone || "";
  }

  async function save() {
    const btn = $("#edit-save");
    btn.disabled = true;
    status("Saving…");

    /* Deep-copy so a failed save leaves the live data untouched. */
    const data = JSON.parse(JSON.stringify(roots()));
    for (const el of fields()) {
      setPath(data, pathOf(el),
        isRich(el) ? cleanHtml(el) : el.textContent.replace(/\s+/g, " ").trim());
      el.classList.toggle("is-empty", el.textContent.trim() === "");
    }

    const files = filesFor(data);
    if (!Object.keys(files).length && !dirty) {
      setEditing(false);
      status("No changes", "ok");
      return;
    }

    try {
      await artifact.publish(files);
      /* The files form leaves this view running, so adopt the new data
         and re-render rather than reloading. */
      Object.assign(SITE, data.SITE);
      PROJECTS.length = 0;
      PROJECTS.push(...data.PROJECTS);
      if (data.CASES) Object.assign(CASES, data.CASES);
      dirty = false;
      setEditing(false);
      status("Saved", "ok");
      setTimeout(() => location.reload(), 600);
    } catch (err) {
      const code = err && err.code;
      if (code === "conflict") {
        status("Someone else saved first — reloading", "warn");
      } else if (code === "not_writer" || code === "not_granted" || code === "not_declared") {
        status("This view is read-only", "warn");
        teardown();
      } else if (code === "rate_limited") {
        status("Saving too often — wait a moment", "warn");
      } else if (code === "capability_disabled") {
        status("Saving isn't available in this view — your text is still here", "warn");
      } else if (code === "too_large") {
        status("Too large to save", "warn");
      } else {
        status("Save failed — your text is still here", "warn");
      }
      btn.disabled = false;
    }
  }

  function teardown() {
    setEditing(false);
    const t = $("#edit-toggle");
    if (t) t.remove();
  }

  function mount() {
    const bar = document.createElement("div");
    bar.className = "editbar";
    bar.id = "editbar";
    bar.hidden = true;
    bar.innerHTML =
      '<span class="editbar__hint">Click any text to edit it.</span>' +
      '<span class="editbar__status" id="edit-status" role="status"></span>' +
      '<button type="button" id="edit-save">Save</button>';
    document.body.append(bar);
    $("#edit-save").addEventListener("click", save);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.id = "edit-toggle";
    toggle.className = "edit-toggle";
    toggle.textContent = "Edit text";
    toggle.addEventListener("click", () => {
      status("");
      $("#edit-save").disabled = false;
      setEditing(!editing);
    });
    const foot = $("#railFoot");
    (foot || document.body).append(toggle);

    document.addEventListener("keydown", (e) => {
      if (!editing) return;
      if (e.key === "Escape") setEditing(false);
      if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); save(); }
    });
  }

  /* Off-platform (opened from disk, or any page without the viewer
     runtime) there is no `claude` global at all. */
  if (typeof claude === "undefined" || typeof claude.use !== "function") return;

  /* The rail is rendered by site.js; wait for it before mounting. */
  claude.use("artifact").then((ns) => {
    if (!ns) return;                       // read-only view, or opened off-platform
    artifact = ns;
    const snap = JSON.parse(JSON.stringify(roots()));
    baseline = { "assets/data.js": serialize(snap) };
    if (snap.CASES) baseline["assets/cases.js"] = serializeCases(snap.CASES);
    if (window.EditImages && typeof CASES !== "undefined" && CASES[document.body.dataset.page]) {
      EditImages.init({ slug: document.body.dataset.page, rerender, markDirty })
        .catch(() => {});
    }
    requestAnimationFrame(mount);
  });
})();
