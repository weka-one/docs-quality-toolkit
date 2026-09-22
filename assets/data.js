/* =================================================================
   CONTENT — the only file you need to edit to change what the site says.

   PROJECTS  drives the Portfolio section, the rail dropdown, the
             /portfolio/ index, and the prev/next pager on case pages.
             Adding a project here wires it into all four; you still
             write the case study page itself at portfolio/<slug>.html.

   SITE      drives about, the writing index, experience, and skills.
   ================================================================= */

const PROJECTS = [
  {
    slug: "docs-quality-tooling",
    title: "Checking documentation the way CI checks code",
    nav: "Docs quality tooling",
    org: "Independent project",
    deck: "Three tools that catch what a style guide can't enforce by hand — a style linter, a freshness checker that compares docs against the API they describe, and a pipeline that runs both against documentation that doesn't live in Git.",
    tags: ["Docs-as-code", "CI quality gates", "Evaluation", "Automation"]
  },
  {
    slug: "tiktok-minis",
    title: "Documentation as the onboarding path for a developer platform",
    nav: "TikTok Minis",
    org: "TikTok · TikTok for Developers",
    deck: "108 pages covering TikTok Minis, Mini Games, Mini Dramas, and Monetization — the self-service path that replaced manual developer onboarding during a seven-market expansion.",
    tags: ["Developer documentation", "Onboarding", "Compliance & KYB", "Monetization APIs"]
  },
  {
    slug: "docs-platform-migration",
    title: "Rebuilding a documentation platform and its information architecture",
    nav: "Platform migration",
    org: "TikTok · Effect House",
    deck: "Moving 300+ guides off WordPress onto Docusaurus — and restructuring what they said while they moved.",
    tags: ["Information architecture", "Docs-as-code", "Migration", "Redirect strategy"]
  },
  {
    slug: "editorial-standards",
    title: "Editorial standards for documentation written by many hands",
    nav: "Editorial standards",
    org: "TikTok · Effect House and TikTok for Developers",
    deck: "Two style guides, a shared glossary, and the contribution workflows that let several teams publish to one docs surface without it drifting apart.",
    tags: ["Style guides", "Terminology", "Contribution workflow", "Localization"]
  },
  {
    slug: "crash-course",
    title: "Teaching AR authoring to people who have never opened the tool",
    nav: "Crash Course",
    org: "TikTok · Effect House",
    deck: "An instructional-design program built from scratch: the highest-performing Effect House video series to date, plus the creator mission around it.",
    tags: ["Instructional design", "Curriculum", "Video production", "Bloom's taxonomy"]
  }
];

const SITE = {

  // Set to "resume.pdf" once you drop your resume PDF next to index.html.
  // Leave as null to hide the link.
  resumeUrl: null,

  // Order here is the order the filter buttons appear in.
  categories: ["Documentation", "E-learning", "Writing"],

  // Externally linkable published work. Case studies live in PROJECTS.
  samples: [
    {
      title: "Configure In-App Ads",
      org: "TikTok for Developers",
      format: "Developer guide",
      category: "Documentation",
      desc: "How developers set up in-app video advertising inside a TikTok mini app. Part of the monetization doc set supporting roughly $100k in daily GMV from mini games.",
      url: "https://developers.tiktok.com/doc/tiktok-minis-in-app-ads"
    },
    {
      title: "Develop Your Mini Drama",
      org: "TikTok for Developers",
      format: "Developer guide",
      category: "Documentation",
      desc: "End-to-end build guide for short-form drama apps on TikTok. One of 76 guides I wrote for the mini apps platform, supporting the launch of 50+ mini dramas and 250+ mini games.",
      url: "https://developers.tiktok.com/doc/tiktok-minis-develop-your-mini-app"
    },
    {
      title: "Managing BoMs for product variants",
      org: "Odoo",
      format: "User documentation",
      category: "Documentation",
      desc: "Configuring bills of materials for product variants in Odoo Manufacturing. Written in reStructuredText and shipped through GitHub pull requests.",
      url: "https://www.odoo.com/documentation/15.0/applications/inventory_and_mrp/manufacturing/management/product_variants.html"
    },
    {
      title: "Introduction to Visual Scripting",
      org: "TikTok Effect House",
      format: "Video curriculum",
      category: "E-learning",
      desc: "Opening module of the Effect House Crash Course. The two courses I designed published 16 tutorials and passed 312,000 views.",
      url: "https://effecthouse.tiktok.com/learn/tutorials/eh-crash-course/introduction-to-visual-scripting"
    },
    {
      title: "Art Maker template tutorial",
      org: "TikTok Effect House",
      format: "Tutorial",
      category: "E-learning",
      desc: "Walkthrough of an AI-driven template that restyles camera input into different art styles — written for creators with no technical background.",
      url: "https://effecthouse.tiktok.com/learn/library/template-tutorials/art-maker"
    },
    {
      title: "Manufacturing By-Products",
      org: "Odoo",
      format: "Tutorial script",
      category: "E-learning",
      desc: "Original script for a production video tutorial, one of 35 I wrote covering material requirements planning.",
      url: "https://media.journoportfolio.com/users/283874/uploads/3c2d8401-b80a-42b8-b892-4d4fc7c79ee6.pdf"
    },
    {
      title: "Material Requirements Planning",
      org: "Odoo",
      format: "White paper",
      category: "Writing",
      desc: "Client-facing white paper surveying MRP as a discipline and where Odoo Manufacturing fits into a production workflow.",
      url: "https://media.journoportfolio.com/users/283874/uploads/59590556-5a6c-4f94-a68a-0131d2e0c0e2.pdf"
    },
    {
      title: "Four reasons to upgrade to OpenSDK",
      org: "TikTok for Developers",
      format: "Blog post",
      category: "Writing",
      desc: "Developer-facing argument for migrating to a new SDK. I launched the TikTok for Developers blog and reviewed and published 56 posts on it.",
      url: "https://developers.tiktok.com/blog/4-reasons-to-upgrade-to-open-sdk"
    },
    {
      title: "Data Portability API",
      org: "TikTok for Developers",
      format: "Product landing page",
      category: "Writing",
      desc: "Landing page copy and supporting documentation for the API TikTok shipped to comply with the EU's Digital Markets Act.",
      url: "https://developers.tiktok.com/products/data-portability-api/"
    }
  ],

  experience: [
    {
      when: "Jun 2025 — Present",
      title: "Senior Technical Writer",
      org: "TikTok",
      points: [
        "Authored and published all 108 pages of public documentation for TikTok Minis and Mini Games, cutting developer onboarding time 4x and taking launches from under 10 to over 200 per two-week cycle.",
        "Published the monetization documentation behind roughly $100k in daily GMV from mini games through in-app purchases and ads.",
        "Delivered onboarding guides and API documentation for travel partners including Expedia and Booking.com launching hotel booking on TikTok.",
        "Shipped a quickstart guide, codebook, and 28 API reference pages for TikTok's research tools.",
        "Created and maintain TikTok's developer documentation style guide."
      ]
    },
    {
      when: "Jan 2023 — Jun 2025",
      title: "Technical Writer & Content Designer",
      org: "TikTok",
      points: [
        "Led the migration of the Effect House learning resources estate from WordPress to Docusaurus — 300+ guides converted, information architecture rebuilt, 256 redirect rules written, article creation and staging time cut 50%.",
        "Authored the TikTok for Developers style guide and expanded the Effect House learning resources style guide; standardized 40+ UI terms in a shared glossary.",
        "Defined how the writing team contributes to the major/minor release cycle and documented it as a team source of truth.",
        "Led documentation and content design for the Data Portability API, shipped to comply with the EU's Digital Markets Act.",
        "Launched the TikTok for Developers blog and reviewed and published 56 posts; wrote the copy for the redesigned TikTok for Developers homepage.",
        "Designed two e-learning courses for augmented reality software; 16 video tutorials, 312,000+ views."
      ]
    },
    {
      when: "Jan 2022 — Dec 2022",
      title: "Technical Content Writer",
      org: "Odoo, Inc.",
      points: [
        "Scripted 35 production-quality video tutorials for material requirements planning applications.",
        "Authored a client-facing white paper on MRP use cases and Odoo Manufacturing.",
        "Maintained multiple versions of user documentation on GitHub — reviewing pull requests, editing RST, and publishing new docs from scratch."
      ]
    }
  ],

  skills: [
    {
      heading: "Documentation systems",
      items: ["Information architecture", "Editorial standards & style guides", "Docs-as-code workflows", "Content audits & migrations", "Terminology management", "API documentation", "Localization readiness"]
    },
    {
      heading: "Tools & formats",
      items: ["Markdown", "reStructuredText", "HTML & CSS", "Git & GitHub", "Docusaurus", "Figma"]
    },
    {
      heading: "Working with teams",
      items: ["Stakeholder management", "Process design", "Instructional design", "Cross-cultural collaboration", "Mandarin Chinese (proficient)"]
    },
    {
      heading: "Education",
      items: [
        "UCSF School of Dentistry, 2019–2021 — D.D.S. candidate, honors standing in select coursework",
        "Cal Poly San Luis Obispo, 2015–2019 — B.S. Biochemistry, minor in Music, 4.0 GPA"
      ]
    }
  ]
};
