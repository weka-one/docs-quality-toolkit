/* =================================================================
   RENDERING — shared by every page. You shouldn't need to touch this;
   edit assets/data.js instead.

   Each page declares what it is on <body>:
     data-base  ""  at the root, "../" one level down
     data-page  "home" | "portfolio" | a project slug
   ================================================================= */
(function () {
  const $ = (sel, root) => (root || document).querySelector(sel);
  const body = document.body;
  const BASE = body.dataset.base || "";
  const PAGE = body.dataset.page || "home";
  const isHome = PAGE === "home";

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const home = (hash) => (isHome ? hash : BASE + "index.html" + hash);
  const project = (slug) => BASE + "portfolio/" + slug + ".html";

  /* ---------------------------------------------------------------
     Rail: identity, nav with the Portfolio disclosure, footer links
     --------------------------------------------------------------- */
  const rail = $(".rail");
  if (rail) {
    const items = [
      { label: "About", href: home("#about") },
      { label: "Portfolio", href: isHome ? "#portfolio" : BASE + "portfolio/index.html", group: true },
      { label: "Writing", href: home("#writing") },
      { label: "Experience", href: home("#experience") },
      { label: "Skills", href: home("#skills") },
      { label: "Contact", href: home("#contact") }
    ];

    const caret =
      '<svg viewBox="0 0 10 10" aria-hidden="true" focusable="false">' +
      '<path d="M3 1.5 L7 5 L3 8.5" fill="none" stroke="currentColor" ' +
      'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    const subItems = PROJECTS.map((p) => {
      const current = p.slug === PAGE ? ' aria-current="page"' : "";
      return `<li><a href="${esc(project(p.slug))}"${current}>${esc(p.nav)}</a></li>`;
    }).join("");

    rail.innerHTML = `
      <div>
        <p class="rail__name"><a href="${esc(home("#top"))}">Wesley Kao</a></p>
        <p class="rail__role">Technical writer, San Francisco Bay Area</p>
      </div>
      <nav class="nav" aria-label="Sections">
        <ol>
          ${items.map((it) => {
            if (!it.group) {
              return `<li><a href="${esc(it.href)}">${esc(it.label)}</a></li>`;
            }
            return `
              <li class="nav__group">
                <div class="nav__row">
                  <a href="${esc(it.href)}">${esc(it.label)}</a>
                  <button class="nav__toggle" type="button" id="navToggle"
                          aria-expanded="false" aria-controls="navPortfolio">
                    <span class="sr-only">Show portfolio projects</span>${caret}
                  </button>
                </div>
                <ul class="nav__sub" id="navPortfolio" hidden>${subItems}</ul>
              </li>`;
          }).join("")}
        </ol>
      </nav>
      <div class="rail__foot" id="railFoot">
        <a href="mailto:wesley.y.kao@gmail.com">Email</a>
        <a href="https://www.linkedin.com/in/wesley-kao-6a6779220/">LinkedIn</a>
      </div>`;

    /* Disclosure. Open by default in the wide rail, closed in the
       narrow top bar where it renders as a popover. */
    const toggle = $("#navToggle");
    const sub = $("#navPortfolio");
    const wide = window.matchMedia("(min-width: 901px)");

    /* In the narrow top bar the panel is position:fixed, because the
       nav list scrolls horizontally and would otherwise clip it. That
       means its coordinates have to be measured rather than inherited. */
    const group = $(".nav__group");
    const place = () => {
      if (wide.matches || sub.hidden) {
        sub.style.top = sub.style.left = "";
        return;
      }
      const r = group.getBoundingClientRect();
      const w = sub.offsetWidth;
      sub.style.top = Math.round(r.bottom + 8) + "px";
      sub.style.left =
        Math.round(Math.max(8, Math.min(r.left, window.innerWidth - w - 8))) + "px";
    };

    const setOpen = (open) => {
      toggle.setAttribute("aria-expanded", String(open));
      sub.hidden = !open;
      $(".sr-only", toggle).textContent =
        (open ? "Hide" : "Show") + " portfolio projects";
      place();
    };

    const syncToViewport = () => setOpen(wide.matches);
    syncToViewport();
    wide.addEventListener("change", syncToViewport);
    window.addEventListener("resize", place);
    $(".nav > ol").addEventListener("scroll", place);

    toggle.addEventListener("click", () => {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    /* In the narrow popover, dismiss on outside click or Escape. */
    document.addEventListener("click", (e) => {
      if (wide.matches) return;
      if (sub.hidden) return;
      if (e.target.closest(".nav__group")) return;
      setOpen(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || wide.matches || sub.hidden) return;
      setOpen(false);
      toggle.focus();
    });

    if (SITE.resumeUrl) {
      const a = document.createElement("a");
      a.href = BASE + SITE.resumeUrl;
      a.textContent = "Resume";
      $("#railFoot").prepend(a);
    }
  }

  /* ---------------------------------------------------------------
     Portfolio cards (home section and /portfolio/ index)
     --------------------------------------------------------------- */
  const cards = $("#cards");
  if (cards) {
    cards.innerHTML = PROJECTS.map((p, i) => `
      <a class="card" href="${esc(project(p.slug))}">
        <span class="card__num">${String(i + 1).padStart(2, "0")}</span>
        <div>
          <h3 class="card__title">${esc(p.title)}</h3>
          <span class="card__org">${esc(p.org)}</span>
          <p class="card__deck">${esc(p.deck)}</p>
          <ul class="card__tags">
            ${p.tags.map((t) => `<li>${esc(t)}</li>`).join("")}
          </ul>
        </div>
      </a>`).join("");
  }

  /* ---------------------------------------------------------------
     Writing index with category filters
     --------------------------------------------------------------- */
  const index = $("#index");
  if (index) {
    let active = "All";

    const rowMarkup = (s) => `
      <a class="row" href="${esc(s.url)}" target="_blank" rel="noopener">
        <span class="row__title">${esc(s.title)}</span>
        <span class="row__org">${esc(s.org)}</span>
        <span class="row__format">${esc(s.format)}</span>
        <p class="row__desc">${esc(s.desc)}</p>
      </a>`;

    const renderIndex = () => {
      const list = active === "All"
        ? SITE.samples
        : SITE.samples.filter((s) => s.category === active);
      index.innerHTML = list.length
        ? list.map(rowMarkup).join("")
        : `<p class="index__empty">Nothing filed under ${esc(active)} yet.</p>`;
    };

    const filters = $("#filters");
    ["All", ...SITE.categories].forEach((cat) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = cat;
      b.setAttribute("aria-pressed", String(cat === "All"));
      b.addEventListener("click", () => {
        active = cat;
        [...filters.children].forEach((x) =>
          x.setAttribute("aria-pressed", String(x === b)));
        renderIndex();
      });
      filters.append(b);
    });
    renderIndex();
  }

  /* ---------------------------------------------------------------
     Experience and skills
     --------------------------------------------------------------- */
  const jobs = $("#experience-list");
  if (jobs) {
    jobs.innerHTML = SITE.experience.map((j) => `
      <article class="job">
        <div class="job__when">${esc(j.when)}</div>
        <div>
          <h3 class="job__title">${esc(j.title)} <span class="job__org">· ${esc(j.org)}</span></h3>
          <ul>${j.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
        </div>
      </article>`).join("");
  }

  const cols = $("#skills-cols");
  if (cols) {
    cols.innerHTML = SITE.skills.map((g) => `
      <div>
        <h3>${esc(g.heading)}</h3>
        <ul>${g.items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>
      </div>`).join("");
  }

  /* ---------------------------------------------------------------
     Case study pager — previous / next, wrapping
     --------------------------------------------------------------- */
  const pager = $("#pager");
  if (pager) {
    const i = PROJECTS.findIndex((p) => p.slug === PAGE);
    if (i !== -1 && PROJECTS.length > 1) {
      const prev = PROJECTS[(i - 1 + PROJECTS.length) % PROJECTS.length];
      const next = PROJECTS[(i + 1) % PROJECTS.length];
      pager.innerHTML = `
        <a href="${esc(project(prev.slug))}">
          <span>Previous</span><strong>${esc(prev.nav)}</strong>
        </a>
        <a class="pager__next" href="${esc(project(next.slug))}">
          <span>Next</span><strong>${esc(next.nav)}</strong>
        </a>`;
    }
  }

  /* ---------------------------------------------------------------
     Scroll-spy on the rail nav (home only)
     --------------------------------------------------------------- */
  if (isHome && "IntersectionObserver" in window) {
    const links = [...document.querySelectorAll(".nav > ol > li > a, .nav__row > a")];
    const targets = links
      .map((a) => {
        const href = a.getAttribute("href");
        return href && href.startsWith("#") ? document.querySelector(href) : null;
      })
      .filter(Boolean);

    if (targets.length) {
      const seen = new Map();
      const io = new IntersectionObserver((entries) => {
        entries.forEach((e) => seen.set(e.target, e.intersectionRatio));
        let best = null, bestRatio = 0;
        seen.forEach((ratio, el) => {
          if (ratio > bestRatio) { bestRatio = ratio; best = el; }
        });
        links.forEach((a) => {
          const on = best && a.getAttribute("href") === "#" + best.id;
          if (on) a.setAttribute("aria-current", "true");
          else a.removeAttribute("aria-current");
        });
      }, { threshold: [0, .1, .25, .5, .75, 1], rootMargin: "-10% 0px -55% 0px" });
      targets.forEach((t) => io.observe(t));
    }
  }

  /* ---- Single page-load entrance ---- */
  const reveal = $(".reveal");
  if (reveal) requestAnimationFrame(() => reveal.classList.add("is-in"));
})();
