/* =================================================================
   Block tools for case studies: add an image after any block, remove
   a block, and set a figure's width, placement and alt text.

   Images upload to the artifact's own asset store and are referenced
   by "/_blob/<id>", a root-relative path that resolves from every page
   and every version. A pasted https URL works too, and is the option
   that survives moving the site off the artifact.

   Loaded only on case pages; does nothing where CASES is absent.
   ================================================================= */
window.EditImages = (function () {
  const SIZES = [["small", "Small"], ["full", "Text width"], ["wide", "Wide"], ["bleed", "Full bleed"]];
  const PLACE = [["", "In flow"], ["center", "Centered"], ["left", "Left"], ["right", "Right"]];

  let ctx = null;   // { slug, rerender, markDirty }
  let assets = null;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  /* ---- the panel that collects an image ---- */
  function openPicker(afterIndex) {
    const body = CASES[ctx.slug].body;
    const back = el("div", "sheet-back");
    const box = el("div", "sheet");
    box.innerHTML = `
      <h3>Add an image</h3>
      <label class="sheet__row">
        <span>Upload a file</span>
        <input type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml" id="img-file">
      </label>
      <p class="sheet__or">or</p>
      <label class="sheet__row">
        <span>Paste an image URL</span>
        <input type="url" id="img-url" placeholder="https://…">
      </label>
      <label class="sheet__row">
        <span>Alt text <em>— what the image shows, for screen readers</em></span>
        <input type="text" id="img-alt">
      </label>
      <label class="sheet__row">
        <span>Caption <em>— optional</em></span>
        <input type="text" id="img-cap">
      </label>
      <p class="sheet__status" id="img-status"></p>
      <div class="sheet__buttons">
        <button type="button" id="img-cancel">Cancel</button>
        <button type="button" id="img-add" class="is-primary">Add image</button>
      </div>`;
    back.append(box);
    document.body.append(back);

    /* Uploading needs the `assets` capability. Declaring it makes the
       artifact organization-internal, which blocked the page outright,
       so it is off: offer the URL field alone rather than a file input
       that cannot work. Re-declaring `assets` at publish turns the
       upload half back on with no other change. */
    if (!assets) {
      box.querySelector("#img-file").closest(".sheet__row").remove();
      box.querySelector(".sheet__or").remove();
      box.querySelector('label[for], .sheet__row input#img-url')
         .closest(".sheet__row").querySelector("span").textContent = "Image URL";
    }

    const status = box.querySelector("#img-status");
    const close = () => back.remove();
    back.addEventListener("click", (e) => { if (e.target === back) close(); });
    box.querySelector("#img-cancel").addEventListener("click", close);
    box.querySelector("#img-alt").focus();

    box.querySelector("#img-add").addEventListener("click", async () => {
      const fileInput = box.querySelector("#img-file");
      const file = fileInput ? fileInput.files[0] : null;
      const url = box.querySelector("#img-url").value.trim();
      const alt = box.querySelector("#img-alt").value.trim();
      const caption = box.querySelector("#img-cap").value.trim();

      if (!file && !url) {
        status.textContent = assets ? "Choose a file or paste a URL." : "Paste an image URL.";
        return;
      }
      if (!alt) { status.textContent = "Alt text is required — describe what the image shows."; return; }

      let src = url, assetId = null;
      if (file) {
        if (!assets) { status.textContent = "Uploading isn't available in this view. Paste a URL instead."; return; }
        status.textContent = "Uploading…";
        try {
          const res = await assets.upload(file, file.type ? undefined : { type: "image/png" });
          assetId = res.id;
          src = "/_blob/" + res.id;
        } catch (err) {
          const m = {
            too_large: "That file is over the size limit (20 MB, or 2 MB for SVG).",
            unsupported_type: "That file type isn't supported. Use PNG, JPEG, GIF, WebP or SVG.",
            quota_or_state: "The image store is full. Remove an unused image first.",
            rate_limited: "Uploading too often — wait a moment.",
            not_granted: "Uploading isn't available in this view. Paste a URL instead.",
            capability_disabled: "Uploading isn't available in this view. Paste a URL instead.",
            store_unavailable: "The image store is temporarily unavailable. Try again."
          };
          status.textContent = m[err && err.code] || "Upload failed. Paste a URL instead.";
          return;
        }
      }

      body.splice(afterIndex + 1, 0, { t: "figure", src, assetId, alt, caption, size: "full", align: "" });
      close();
      ctx.rerender();
      ctx.markDirty();
    });
  }

  /* ---- per-block controls ----
     ONE toolbar, fixed-position, owned by <body>. An earlier version
     appended a toolbar into each block; because those blocks are the
     editable fields, the button labels were read back as content and
     saved into the text. A toolbar that never lives inside an editable
     element cannot do that. */
  let bar = null, forIndex = -1, hideTimer = null, active = false, wired = null;

  function ensureBar() {
    if (bar) return bar;
    bar = el("div", "blocktools");
    bar.hidden = true;
    bar.addEventListener("mouseenter", () => clearTimeout(hideTimer));
    bar.addEventListener("mouseleave", scheduleHide);
    document.body.append(bar);
    return bar;
  }
  const scheduleHide = () => {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { if (bar) bar.hidden = true; forIndex = -1; }, 220);
  };

  function fill(i) {
    if (!bar) return;
    const body = CASES[ctx.slug].body;
    if (!body[i]) return;
    bar.replaceChildren();

    const add = el("button", "", "+ Image");
    add.type = "button";
    add.title = "Add an image after this block";
    add.addEventListener("click", () => openPicker(i));
    bar.append(add);

    const del = el("button", "", "Remove");
    del.type = "button";
    del.addEventListener("click", () => {
      const what = body[i].t === "figure" ? "this image" : "this block";
      if (!confirm(`Remove ${what}? Cancelling edit mode undoes it.`)) return;
      body.splice(i, 1);
      bar.hidden = true; forIndex = -1;
      ctx.rerender(); ctx.markDirty();
    });
    bar.append(del);

    if (body[i] && body[i].t === "figure") {
      const group = (opts, key, cur) => {
        bar.append(el("span", "blocktools__sep"));
        for (const [val, label] of opts) {
          const b = el("button", cur === val ? "is-on" : "", label);
          b.type = "button";
          b.addEventListener("click", () => {
            body[i][key] = val;
            bar.hidden = true; forIndex = -1;
            ctx.rerender(); ctx.markDirty();
          });
          bar.append(b);
        }
      };
      group(SIZES, "size", body[i].size || "full");
      group(PLACE, "align", body[i].align || "");
      const alt = el("button", "", "Alt text\u2026");
      alt.type = "button";
      alt.addEventListener("click", () => {
        const next = prompt("Alt text — what does this image show?", body[i].alt || "");
        if (next !== null) { body[i].alt = next.trim(); ctx.rerender(); ctx.markDirty(); }
      });
      bar.append(alt);
    }
  }

  function showFor(node, i) {
    if (!active || !bar || i < 0) return;
    if (i === forIndex && !bar.hidden) return;
    forIndex = i;
    fill(i);
    bar.hidden = false;
    const r = node.getBoundingClientRect();
    const w = bar.offsetWidth;
    bar.style.top = Math.max(8, Math.round(r.top - bar.offsetHeight - 6)) + "px";
    bar.style.left = Math.round(Math.min(r.right - w, window.innerWidth - w - 12)) + "px";
  }

  /* One delegated listener on the prose container, not one per block:
     blocks survive a re-render and leaving edit mode, so per-block
     listeners pile up and outlive the toolbar they point at. */
  function decorate(rootEl) {
    if (!ctx) return;
    active = true;
    ensureBar();
    const prose = rootEl.querySelector(".prose");
    if (!prose || wired === prose) return;
    wired = prose;

    const locate = (target) => {
      const node = target && target.closest ? target.closest(".prose > *") : null;
      if (!node || node.parentElement !== prose) return null;
      return { node, i: [...prose.children].indexOf(node) };
    };
    const enter = (e) => {
      if (!active) return;
      const hit = locate(e.target);
      if (!hit) return;
      clearTimeout(hideTimer);
      showFor(hit.node, hit.i);
    };
    prose.addEventListener("mouseover", enter);
    prose.addEventListener("focusin", enter);
    prose.addEventListener("mouseleave", scheduleHide);
  }

  function teardown() {
    active = false;
    clearTimeout(hideTimer);
    if (bar) { bar.remove(); bar = null; }
    forIndex = -1;
  }

  return {
    async init(context) {
      ctx = context;
      assets = await claude.use("assets");   // null on a read-only view
      return { canUpload: !!assets };
    },
    decorate,
    teardown,
    get ready() { return !!ctx; }
  };
})();
