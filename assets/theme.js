/* =================================================================
   Palette switching. Runs before render so the page never flashes
   the wrong colours. Each palette is a token block in site.css plus
   a Google Fonts request loaded on demand here.

   TEMPORARY: the picker is for choosing a palette. Once one is
   settled on, set DEFAULT below, delete the picker, and fold the
   winning font request into each page's <head>.
   ================================================================= */
(function () {
  const DEFAULT = "sage";

  const THEMES = [
    { id: "sage",      name: "Sage",      swatch: "#0F5A4C", fonts: null },
    { id: "vermilion", name: "Vermilion", swatch: "#C0411F",
      fonts: "family=Fraunces:opsz,wght@9..144,400;9..144,500&family=Inter:wght@400;500;600" },
    { id: "cobalt",    name: "Cobalt",    swatch: "#1F45D8",
      fonts: "family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&family=Space+Grotesk:wght@400;500;600" },
    { id: "plum",      name: "Plum",      swatch: "#8A2A6B",
      fonts: "family=Spectral:wght@300;400;500&family=DM+Sans:wght@400;500;700" },
    { id: "signal",    name: "Signal",    swatch: "#4F2FE8",
      fonts: "family=Manrope:wght@400;500;600;700" },
  ];

  const byId = (id) => THEMES.find((t) => t.id === id);

  /* Storage can throw in a private window; the site must still render. */
  const read = () => { try { return localStorage.getItem("palette"); } catch { return null; } };
  const save = (v) => { try { localStorage.setItem("palette", v); } catch { /* not fatal */ } };

  function loadFonts(theme) {
    if (!theme.fonts) return;                       // Sage ships in each page's <head>
    const id = "fonts-" + theme.id;
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?" + theme.fonts + "&display=swap";
    document.head.appendChild(link);
  }

  function apply(id) {
    const theme = byId(id) || byId(DEFAULT);
    document.documentElement.dataset.palette = theme.id;
    loadFonts(theme);
    return theme.id;
  }

  let current = apply(read() || DEFAULT);

  function buildPicker() {
    const bar = document.createElement("div");
    bar.className = "picker";
    bar.innerHTML = '<span class="picker__label">Theme</span>';
    THEMES.forEach((t) => {
      const b = document.createElement("button");
      b.type = "button";
      b.style.background = t.swatch;
      b.title = t.name;
      b.setAttribute("aria-label", "Use the " + t.name + " theme");
      b.setAttribute("aria-pressed", String(t.id === current));
      b.addEventListener("click", () => {
        current = apply(t.id);
        save(current);
        bar.querySelectorAll("button").forEach((x, i) =>
          x.setAttribute("aria-pressed", String(THEMES[i].id === current)));
      });
      bar.appendChild(b);
    });
    document.body.appendChild(bar);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildPicker);
  } else {
    buildPicker();
  }
})();
