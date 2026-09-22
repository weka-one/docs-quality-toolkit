/* =================================================================
   CASE STUDIES — one entry per project in PROJECTS, keyed by slug.
   Each case page renders from here, and edit mode writes back here.
   ================================================================= */

const CASES = {
  "docs-quality-tooling": {
    "kicker": "Independent project · 2026",
    "title": "Checking documentation the way CI checks code",
    "deck": "Three tools that catch what a style guide can't enforce by hand — and what happened when I tried to measure whether they actually worked.",
    "description": "Three tools that check documentation automatically: a style linter that cut violations 36% across 553 pages, a freshness checker with zero false alarms, and a pipeline for docs that don't live in Git.",
    "meta": [
      {
        "label": "Role",
        "value": "Sole author — design, build, evaluation",
        "href": null
      },
      {
        "label": "Built with",
        "value": "Vale, GitHub Actions, OpenAPI, a headless browser",
        "href": null
      },
      {
        "label": "Measured on",
        "value": "Meilisearch documentation (MIT, pinned commit)",
        "href": null
      },
      {
        "label": "Tests",
        "value": "273 across the three tools",
        "href": null
      }
    ],
    "stats": [
      {
        "value": "553",
        "label": "pages of documentation I didn't write, used as the test corpus"
      },
      {
        "value": "36%",
        "label": "fewer style violations after the automated fixes ran"
      },
      {
        "value": "0",
        "label": "false alarms from the freshness checker at its shipping setting"
      },
      {
        "value": "23 of 40",
        "label": "style-guide rules a machine can check; the rest need a person"
      }
    ],
    "body": [
      {
        "t": "h2",
        "html": "Documentation breaks quietly"
      },
      {
        "t": "p",
        "html": "It breaks in two ways, and neither announces itself. It drifts out of house style — one heading capitalized differently, one product name written three ways. And it drifts out of sync with the product, which is worse: the endpoint moved, the parameter was renamed, and the page still confidently says otherwise."
      },
      {
        "t": "p",
        "html": "Both happen a page at a time. Neither shows up until a reader hits it. Code has linters and tests for exactly this problem; documentation usually has a style guide nobody has time to enforce by hand."
      },
      {
        "t": "p",
        "html": "I built three tools to close that gap."
      },
      {
        "t": "h2",
        "html": "What I built"
      },
      {
        "t": "ul",
        "items": [
          "<strong>A style linter</strong> — 40 rules covering heading case, requirement words, banned punctuation, and product-term drift. Runs on every pull request and annotates the diff.",
          "<strong>A freshness checker</strong> — reads the code samples, routes and parameter tables on a page, then checks each claim against the product's API definition. Does this endpoint still exist? Is this parameter still called that? Is this value still valid?",
          "<strong>A monitoring pipeline</strong> — runs both on a schedule, for documentation that lives in a CMS rather than Git, where there is no pull request to gate and no diff to check."
        ]
      },
      {
        "t": "h2",
        "html": "Measured on documentation I didn't write"
      },
      {
        "t": "p",
        "html": "A style rule tested against text you already agree with proves nothing. So I measured everything against 553 pages of the Meilisearch documentation — open source, pinned to a specific commit so the results reproduce — along with that project's official API definition. Nothing was hand-picked to pass, and several rules were retired once it turned out their output was mostly noise."
      },
      {
        "t": "p",
        "html": "Running the rules and applying the automated fixes cut style violations by 36%, from 1,092 to 704."
      },
      {
        "t": "h2",
        "html": "Four decisions that did most of the work"
      },
      {
        "t": "ol",
        "items": [
          "<strong>Rules are tested like code.</strong> 173 test cases pin down both what each rule catches and what it must never flag. A rule with no tests fails the build.",
          "<strong>Code samples are provably untouched.</strong> A linter that rewrites prose must never reach inside a code block. A separate check proves all 16,541 protected segments come through byte-identical — which is what makes it safe to let the automated fixes run without a human reading every diff.",
          "<strong>It fails on new problems, not old ones.</strong> A quality tool that blocks work on day one over 400 pre-existing issues gets switched off in week one. This one only fails a build on findings that weren't there before.",
          "<strong>Policy lives in a config file.</strong> Which heading case, which callout labels, which languages are allowed — all configuration. Pointing the tool at a different style guide is an edit, not a rewrite."
        ]
      },
      {
        "t": "h2",
        "html": "Zero false alarms, on purpose"
      },
      {
        "t": "p",
        "html": "At its shipping setting, the freshness checker reports 16 problems and all 16 are real."
      },
      {
        "t": "p",
        "html": "That is a deliberate trade, not a lucky result. Told to report everything, it finds 51 problems and 30 of them are wrong — three false alarms for every two real ones, which is precisely how a tool gets ignored by the second week. Raising the confidence bar gives up about a quarter of the real problems and leaves a queue a writer can trust completely."
      },
      {
        "t": "p",
        "html": "I would rather miss a few things than be the tool nobody believes. Making that trade visible, instead of guessing at it, is what the evaluation harness is for."
      },
      {
        "t": "h2",
        "html": "Being graded on my own homework"
      },
      {
        "t": "p",
        "html": "The first evaluation scored perfectly — full marks on both measures. That was a red flag, not a result."
      },
      {
        "t": "p",
        "html": "I had written the answer key by reading the tool's own output. Measured that way, a tool cannot miss anything, because anything it missed never made it into the answer key in the first place. The score was guaranteed before I ran it."
      },
      {
        "t": "pull",
        "items": [
          "So I built a second answer key by hand — checking every route and parameter on a sample of pages against the API definition, without looking at the tool at all. The first time I ran against it, the tool scored zero. That is what made it worth keeping."
        ]
      },
      {
        "t": "p",
        "html": "Breaking the results down per detector showed where the inaccuracy actually lived: three of the five were already perfect, and effectively every false alarm came from one detector reading endpoints that belonged to a different service. Knowing that is the difference between tuning one thing and distrusting the whole tool."
      },
      {
        "t": "h2",
        "html": "Documentation that doesn't live in Git"
      },
      {
        "t": "p",
        "html": "Both tools assumed a folder of Markdown that a pull request changes. Plenty of documentation doesn't work that way. It lives in a CMS — no pull request, no diff, no file on disk until something goes and fetches one."
      },
      {
        "t": "p",
        "html": "The checks were never the problem; they work on text. What needed replacing was the part that produces the text. There are now four ways in: a folder, a CMS read API, the published site, or a real browser for sites that assemble their pages on the fly. None of them hardcodes a particular CMS."
      },
      {
        "t": "p",
        "html": "That last option taught me the most. Sites built in the browser serve an empty shell to a plain fetch, so my first attempt mined the data embedded in the page and scored every string on how much it read like English. Run against a real developer site, it returned the newsletter blurb, a legal modal, and an unsubscribe line — the site's own interface copy, which is exactly where the long grammatical sentences live. The actual documentation was in fragments too short to score. The approach wasn't undertuned; it was guessing."
      },
      {
        "t": "p",
        "html": "Driving a real browser removed the guesswork and gave back something the data-mining never had: structure. A rendered page knows which part is navigation and which part is the article, so the checks can read the body and leave the furniture alone."
      },
      {
        "t": "p",
        "html": "The obvious version of that was slow. A four-page crawl took 35 seconds, because every short page sat out the full timeout waiting for content that had already arrived. Ending the wait when the text stops changing brought it to 3.6 seconds — under a second per page, which makes a 500-page site a half-hour unattended run."
      },
      {
        "t": "h2",
        "html": "What it doesn't do"
      },
      {
        "t": "p",
        "html": "Of 40 checkable items in the style guide, 23 are automated and 17 need a person. Voice, argument structure, and whether an example is actually useful are not lintable. Claiming otherwise would have made the tool untrustworthy in the places where it does work."
      },
      {
        "t": "p",
        "html": "Three other limits worth stating plainly:"
      },
      {
        "t": "ul",
        "items": [
          "The figure for how much the freshness checker <em>finds</em> rests on a small hand-built sample. The figure for how much of what it finds is <em>real</em> is solid; the other half of the picture is thinner.",
          "Everything was measured against one documentation set. How it performs on another, with different conventions, is unknown until someone runs it.",
          "The 36% is what the automated fixes achieved, not everything the rules found. The rest was deliberately left for a human."
        ]
      },
      {
        "t": "h2",
        "html": "What I'd build next"
      },
      {
        "t": "p",
        "html": "Not another detector. The freshness checker already knows an endpoint moved and knows what it moved to — which is enough to open a pull request with the correction rather than a ticket describing it."
      },
      {
        "t": "p",
        "html": "The evaluation harness is what makes that safe to attempt. A tool that is right 41% of the time must never be allowed to write anything. A tool that is right every time, over a deliberately narrowed set of findings, can."
      }
    ]
  },
  "tiktok-minis": {
    "kicker": "TikTok · TikTok for Developers · 2025–present",
    "title": "Documentation as the onboarding path for a developer platform",
    "deck": "The public documentation set for TikTok Minis and Mini Games — the self-service path that replaced manual developer onboarding during a seven-market expansion.",
    "description": "Authoring 108 pages of public documentation for TikTok Minis and Mini Games: the self-service onboarding path that took biweekly app launches from under 10 to over 200.",
    "meta": [
      {
        "label": "Role",
        "value": "Sole author of the public documentation set",
        "href": null
      },
      {
        "label": "Surface",
        "value": "TikTok Minis, Mini Games, Mini Dramas, Monetization",
        "href": null
      },
      {
        "label": "Worked with",
        "value": "Product, engineering, compliance, business development",
        "href": null
      }
    ],
    "stats": [
      {
        "value": "108",
        "label": "documentation pages authored and published across four folders"
      },
      {
        "value": "359",
        "label": "developers screened across 29 countries through the documented intake process"
      },
      {
        "value": "&lt;10 &rarr; 200+",
        "label": "app launches per two-week cycle after onboarding moved to self-service"
      },
      {
        "value": "4&times;",
        "label": "reduction in developer onboarding time"
      }
    ],
    "body": [
      {
        "t": "h2",
        "html": "Onboarding that could not scale"
      },
      {
        "t": "p",
        "html": "TikTok Minis is a platform for third-party developers building games, short-form drama apps, and booking integrations that run inside TikTok. Growing it means onboarding developers who are outside the company, in markets across the world, in time zones nobody is awake for."
      },
      {
        "t": "p",
        "html": "When onboarding is manual, each of those developers costs a person. A partner manager walks them through integration, answers the same questions that were answered last week, and chases the same compliance paperwork. That model produced fewer than 10 app launches per two-week cycle, and it had a ceiling set by headcount rather than by demand. Meanwhile the business was expanding into seven new markets."
      },
      {
        "t": "p",
        "html": "Documentation was the only thing that could absorb that load. Not as a reference for people who already knew the platform — as the onboarding path itself."
      },
      {
        "t": "h2",
        "html": "What I owned"
      },
      {
        "t": "p",
        "html": "I authored and published the entire public documentation set for TikTok Minis and Mini Games: the introduction and platform concepts, the Mini Games and Mini Dramas build guides, and the monetization documentation. Every public page a developer reads on their way from \"interested\" to \"launched\" came through me."
      },
      {
        "t": "table",
        "caption": "Counted from the published navigation. Where a folder page and its first child resolve to the same URL, the two are counted once.",
        "head": [
          "Section",
          "Pages"
        ],
        "rows": [
          [
            "Mini Games",
            "48"
          ],
          [
            "Mini Dramas",
            "36"
          ],
          [
            "TikTok Minis",
            "18"
          ],
          [
            "Monetization",
            "6"
          ],
          [
            "Total",
            "108"
          ]
        ]
      },
      {
        "t": "p",
        "html": "That scope is unusual and it mattered. A single author across the whole funnel means the integration guide and the monetization guide assume the same prior knowledge, use the same terms for the same things, and hand off to each other in the order a developer actually hits them. Documentation written by the team that owns each feature tends not to do that."
      },
      {
        "t": "pull",
        "items": [
          "The test of onboarding documentation is not whether it is accurate. It is whether a developer in a market you have never visited, working from a time zone where nobody is online to ask, can get to a launched app without talking to anyone."
        ]
      },
      {
        "t": "h2",
        "html": "The integration workflow"
      },
      {
        "t": "p",
        "html": "The core work was documenting the integration workflow end to end so it could be followed without a partner manager in the loop. Once that existed, intake stopped being a conversation and became a process: 359 developers were screened across 29 countries, and biweekly launches moved from fewer than 10 to more than 200."
      },
      {
        "t": "p",
        "html": "Onboarding time dropped by a factor of four. The mechanism is not mysterious — the questions that used to be asked in a thread were answered on a page, once, in the place the developer was already looking."
      },
      {
        "t": "h2",
        "html": "Compliance and KYB"
      },
      {
        "t": "p",
        "html": "Scaling a developer platform into new markets raises a problem that is the opposite of a growth problem: every additional developer is an additional entity you have to know something about. I wrote the end-to-end compliance and Know Your Business processes."
      },
      {
        "t": "p",
        "html": "This is the least glamorous documentation I have written and probably the highest-stakes. A build guide that is wrong costs a developer an afternoon. A KYB process that is wrong or out of date costs the platform its standing in a market. Writing it as a documented process rather than institutional knowledge is what let the catalog scale past a thousand mini games without loosening the standard applied to each one."
      },
      {
        "t": "h2",
        "html": "Monetization"
      },
      {
        "t": "p",
        "html": "The last stretch of the funnel is a developer making money, which on this platform means in-app purchases and in-app ads. I wrote the monetization documentation covering both, from ad placement and configuration through to subscription purchases."
      },
      {
        "t": "p",
        "html": "Ad monetization documentation has a property most developer documentation does not: the difference between a correct and an incorrect implementation shows up directly in the developer's revenue. Documenting the monetization APIs well enough that developers configured them properly contributed to an average ROAS increase for in-app ads of more than 100% in Q4."
      },
      {
        "t": "h2",
        "html": "What I would do differently"
      },
      {
        "t": "p",
        "html": "If documentation is the onboarding funnel, it should be instrumented like one, and this was not. We could see the top and the bottom — developers screened, apps launched — and nothing in between. When a developer stalled, no data told us which page lost them. I was reasoning about drop-off from support questions and intuition, which are the two worst available signals."
      },
      {
        "t": "p",
        "html": "The version I would build now treats each documented step as a funnel stage and joins page analytics to the onboarding milestones the platform already tracks, so \"developers stop after the capability configuration page\" is a finding rather than a hunch."
      },
      {
        "t": "p",
        "html": "The second thing is specific to the compliance material. KYB and compliance content goes stale in a way that is genuinely dangerous — a requirement changes in one market and the page keeps saying the old thing, confidently, to everyone. Those pages needed a named owner and a scheduled re-review with an explicit expiry, enforced by tooling rather than by someone remembering. Ordinary build guides can tolerate being reviewed when someone notices they are wrong. Regulatory content cannot, and I treated both the same way."
      }
    ]
  },
  "docs-platform-migration": {
    "kicker": "TikTok · Effect House · 2023–2025",
    "title": "Rebuilding a documentation platform and its information architecture",
    "deck": "Moving 300+ guides off WordPress onto Docusaurus — and restructuring what they said while they moved.",
    "description": "Moving 300+ Effect House guides off WordPress onto Docusaurus, rebuilding the information architecture in the same pass, and shipping 256 redirect rules so nothing broke.",
    "meta": [
      {
        "label": "Role",
        "value": "Migration lead; information architecture owner",
        "href": null
      },
      {
        "label": "Surface",
        "value": "Effect House learning resources",
        "href": null
      },
      {
        "label": "Worked with",
        "value": "Technical writing, design, engineering, QA",
        "href": null
      },
      {
        "label": "Stack",
        "value": "WordPress → Docusaurus, Markdown, Git",
        "href": null
      }
    ],
    "stats": [
      {
        "value": "300+",
        "label": "existing guides converted from WordPress to Markdown"
      },
      {
        "value": "70 → 140+",
        "label": "technical guides refactored into feature guides mapped to the tool"
      },
      {
        "value": "256",
        "label": "redirect rules written to keep inbound links working"
      },
      {
        "value": "50%",
        "label": "reduction in time spent on article creation and staging"
      }
    ],
    "body": [
      {
        "t": "h2",
        "html": "The problem was never just the CMS"
      },
      {
        "t": "p",
        "html": "Effect House documentation ran on WordPress. As a content management system it was fragile: publishing was slow, there was no real versioning, staging was awkward, and nothing about the workflow resembled how the engineers next to us shipped their own work."
      },
      {
        "t": "p",
        "html": "But the platform was only half of it. The information architecture had grown by accretion. Guides were organized around the order in which they had been written rather than around the tool a reader had open in front of them — someone looking at a panel in the editor had no reliable path from what they could see to the page that explained it. Beginners landed in an introduction that assumed they already knew what augmented reality authoring involved."
      },
      {
        "t": "p",
        "html": "Those two problems had a scheduling relationship that mattered. Migrating first and restructuring later would have meant moving 300+ pages into a structure we already knew was wrong, then moving them again. I argued for doing both in one pass."
      },
      {
        "t": "h2",
        "html": "What I owned"
      },
      {
        "t": "p",
        "html": "I spearheaded the restructure and ran the conversion. Concretely, that meant:"
      },
      {
        "t": "ul",
        "items": [
          "Converting 300+ existing guides from WordPress into Markdown.",
          "Building and maintaining the migration tracker — a page-by-page record of what had been converted, reviewed, and published, so nothing was quietly dropped on the way across.",
          "Designing the new information architecture and refactoring the content to fit it.",
          "Owning the redirect strategy.",
          "Clearing every content bug QA found before launch."
        ]
      },
      {
        "t": "h2",
        "html": "Restructuring around the tool, not around the docs"
      },
      {
        "t": "p",
        "html": "The central move was refactoring 70+ existing technical guides into 140+ feature guides organized to mirror the tool's own layout of objects, components, and assets. Splitting pages roughly doubled the page count, which sounds like the wrong direction until you look at what the old pages were: single documents covering several unrelated features because those features had happened to ship together. A reader with a component selected in the editor could now find exactly the page for that component."
      },
      {
        "t": "p",
        "html": "Alongside that:"
      },
      {
        "t": "ul",
        "items": [
          "<strong>Getting Started was rebuilt.</strong> I redesigned the \"Introduction to Effect House\" guide for readers with no AR background, and wrote new guides introducing the tool interface and the underlying AR concepts.",
          "<strong>The glossary became a page.</strong> Terminology work that had lived in an internal document was published into the docs themselves, so readers and writers worked from the same vocabulary.",
          "<strong>Existing guides were rewritten to fit the new structure</strong>, not just moved. <a href=\"https://effecthouse.tiktok.com/learn/guides/getting-started/technical-guidelines/technical-optimization\">Technical Optimization for Effects</a> is one of them — a guide that sits at the end of every creator's workflow, where being wrong or badly placed costs someone a rejected submission.",
          "<strong>New top-level categories were created for tool interface and AR concepts.</strong> These were deliberately forward-looking — at launch they were thin, but they gave beginner content somewhere to grow instead of forcing it into categories built for feature reference.",
          "<strong>The landing page was redesigned</strong> with the design team, so the entry point matched the new structure."
        ]
      },
      {
        "t": "pull",
        "items": [
          "The argument I had to make repeatedly was that a migration is the cheapest moment to fix structure, and the most expensive moment to postpone it. Every link, every redirect, and every reader habit gets re-cemented on the way across."
        ]
      },
      {
        "t": "h2",
        "html": "Not breaking the internet on the way"
      },
      {
        "t": "p",
        "html": "Effect House documentation was linked from inside the product, from email campaigns, and from blog posts — none of which we controlled or could retroactively edit. A URL change would have broken all of it silently."
      },
      {
        "t": "p",
        "html": "I wrote redirect rules for 256 URLs so every existing inbound link stayed backwards compatible with the new pages, and worked with engineering to close out the remaining broken-link risk. Before go-to-market I worked through 30 content bugs QA had filed — syntax errors, typos, broken internal links — so launch day was not the first time anyone read the pages in their new home."
      },
      {
        "t": "h2",
        "html": "What changed afterward"
      },
      {
        "t": "p",
        "html": "Docusaurus put the documentation in Git, which changed the team's working model more than it changed the reader's experience. Content could be versioned on branches. Drafts could be reviewed as pull requests instead of as comments on a staging URL. Writers could work the way the engineers they documented already worked."
      },
      {
        "t": "p",
        "html": "Time spent on article creation and staging dropped by 50%. The practices moved from improvised to something close to an industry-standard docs-as-code workflow, and the beginner categories we built as empty scaffolding have had content added to them since."
      },
      {
        "t": "h2",
        "html": "What I would do differently"
      },
      {
        "t": "p",
        "html": "The migration fixed the platform and it fixed the structure. It did not ship the thing that keeps either of them honest."
      },
      {
        "t": "p",
        "html": "What we ended up with was a good architecture maintained by attention — the 256 redirects were correct on the day I wrote them, the IA was correct on the day we launched, and staying correct afterward depended on people noticing. There was no link checker in CI, no staleness detection, no style linting at review time, no automated check that a page referencing a renamed UI element got flagged when the element was renamed."
      },
      {
        "t": "p",
        "html": "If I ran this migration again I would front-load that automation instead of treating it as a follow-up. The pull request workflow we adopted was the hard part; adding quality gates to a pipeline that already exists is comparatively cheap, and it is the difference between a docs estate that is accurate at launch and one that stays accurate."
      }
    ]
  },
  "editorial-standards": {
    "kicker": "TikTok · Effect House and TikTok for Developers · 2023–2025",
    "title": "Editorial standards for documentation written by many hands",
    "deck": "Two style guides, a shared glossary, and the contribution workflows that let several teams publish to one docs surface without it drifting apart.",
    "description": "Two style guides, a 40-term glossary, and the contribution workflows that let several teams publish to one documentation surface without it drifting apart.",
    "meta": [
      {
        "label": "Role",
        "value": "Standards author; workflow owner",
        "href": null
      },
      {
        "label": "Surface",
        "value": "Effect House learning resources; TikTok for Developers",
        "href": null
      },
      {
        "label": "Worked with",
        "value": "Technical writing, content design, engineering, localization",
        "href": null
      },
      {
        "label": "Artifacts",
        "value": "Internal — I can walk through them in detail",
        "href": null
      }
    ],
    "stats": [
      {
        "value": "2",
        "label": "style guides: TikTok for Developers written from scratch, Effect House substantially expanded"
      },
      {
        "value": "40+",
        "label": "UI terms standardized in a shared, published glossary"
      },
      {
        "value": "6",
        "label": "design and accessibility issues resolved on the new docs site from writer-side feedback"
      },
      {
        "value": "2",
        "label": "localization markets brought into the workflow with training documentation"
      }
    ],
    "body": [
      {
        "t": "h2",
        "html": "The failure mode of a growing docs team"
      },
      {
        "t": "p",
        "html": "By 2023 the technical writing function was expanding, several product teams were contributing to the same documentation surfaces, and there was no agreed standard for what a page should look like. The symptoms were ordinary and corrosive: the same UI element named three different ways across three guides, tables formatted differently on every page, in-tool navigation referenced inconsistently enough that a reader could not tell whether two guides were describing the same menu."
      },
      {
        "t": "p",
        "html": "Underneath the surface inconsistency was a process gap. There was no defined way for a writer to plug into the product's release cycle, no source of truth for how the team worked, and no archive of decisions — so every question got re-answered from scratch, differently."
      },
      {
        "t": "h2",
        "html": "The style guides"
      },
      {
        "t": "p",
        "html": "I wrote the TikTok for Developers style guide from scratch and applied it while reviewing API documentation and developer-facing responses on GitHub. For Effect House, I expanded the existing learning resources style guide with specifications it had been missing: table formatting, verbiage conventions, and — the one that mattered most for a tool-centric docs set — how to reference in-tool navigation so that every guide pointed at the interface the same way."
      },
      {
        "t": "p",
        "html": "I also wrote guidelines for Markdown formatting, which sounds trivial and is not. Once documentation lives in Git and multiple teams contribute through pull requests, formatting inconsistency becomes diff noise that buries the substantive review comments."
      },
      {
        "t": "h2",
        "html": "Terminology as shared infrastructure"
      },
      {
        "t": "p",
        "html": "Working with content design, I reviewed and finalized 40+ Effect House UI terms for use across the documentation. The decision I would defend hardest is that the glossary did not stay an internal reference — it was published as a page in the documentation itself."
      },
      {
        "t": "p",
        "html": "An internal-only glossary standardizes writers. A published one standardizes writers, support, the product team, and the readers who go on to write community tutorials. It also creates accountability: a term that is wrong in public gets reported."
      },
      {
        "t": "pull",
        "items": [
          "A standard nobody can follow is decoration. Most of the work was not writing the guides — it was building the surrounding process so that following them was the path of least resistance."
        ]
      },
      {
        "t": "h2",
        "html": "Making the standard operational"
      },
      {
        "t": "p",
        "html": "A style guide with no delivery mechanism gets read once. The surrounding system mattered more than the documents:"
      },
      {
        "t": "ul",
        "items": [
          "<strong>A defined release-cycle workflow.</strong> I specified how the writing team contributes to the major and minor release cycle, so documentation work had a known shape and a known entry point rather than being negotiated per release.",
          "<strong>A source-of-truth process document</strong> outlining how the team operated, so process questions had one answer.",
          "<strong>A centralized team workspace</strong> for storing and collaborating on documents, plus internal documentation of our workflows — deliberately written for posterity, so the reasoning survived turnover.",
          "<strong>Weekly standups</strong> that I established and ran, including delegating the week's work."
        ]
      },
      {
        "t": "h2",
        "html": "Extending it past the writing team"
      },
      {
        "t": "p",
        "html": "Standards that only bind the people who wrote them do not hold a shared surface together. Three efforts pushed the standard outward:"
      },
      {
        "t": "ul",
        "items": [
          "<strong>Localization.</strong> I opened the localization conversation with the team in Shanghai and wrote internal training documentation on Markdown formatting in Docusaurus for the Korean and Japanese localization stakeholders — so that translated content entered the same pipeline under the same conventions instead of arriving as a parallel content set.",
          "<strong>A content audit.</strong> I developed a proposal to audit learning resources for inaccurate and out-of-date content and ran the kickoff discussion with the writing team and our lead. Setting a standard raises an uncomfortable question — how much existing content violates it — and the audit was how I made that question answerable rather than rhetorical.",
          "<strong>Feedback into the platform itself.</strong> I was a primary contributor to feedback on the new learning resources website, flagging problems from the writer's and reader's side that resulted in 6 design and accessibility issues being resolved before they shipped."
        ]
      },
      {
        "t": "p",
        "html": "I also hosted a global content design and product writing event and built a digital yearbook for the team — lighter work, but part of the same effort to make a distributed writing function feel like one group with one standard."
      },
      {
        "t": "h2",
        "html": "What I would do differently"
      },
      {
        "t": "p",
        "html": "Everything above was enforced by review, which means it was enforced as consistently as the reviewer's attention on a given day. That is a real ceiling, and I hit it."
      },
      {
        "t": "p",
        "html": "A meaningful share of what these guides specify is mechanically checkable: approved terminology, table conventions, heading structure, how in-tool navigation is referenced, link health, whether a page has gone stale relative to the release it documents. None of it needed a human."
      },
      {
        "t": "p",
        "html": "What I would build now is the linter — terminology and structural rules encoded as automated checks running in CI on every pull request, with human review reserved for the things that actually require judgment: whether the explanation is correct, whether the page is aimed at the right reader, whether it should exist at all. The style guide stops being a document people are supposed to have read and becomes a property of the pipeline."
      }
    ]
  },
  "crash-course": {
    "kicker": "TikTok · Effect House · 2023–2025",
    "title": "Teaching AR authoring to people who have never opened the tool",
    "deck": "An instructional-design program built from scratch: the highest-performing Effect House video series to date, plus the creator mission around it.",
    "description": "Designing the Effect House Crash Course and the #MyFirstTikTokEffect mission: the highest-performing Effect House video series to date, built on explicit learning objectives.",
    "meta": [
      {
        "label": "Role",
        "value": "Lead writer; instructional designer",
        "href": null
      },
      {
        "label": "Surface",
        "value": "Effect House learning resources and YouTube",
        "href": null
      },
      {
        "label": "Worked with",
        "value": "Technical writing, content design, community, design, external video agency",
        "href": null
      },
      {
        "label": "Method",
        "value": "Bloom's taxonomy learning objectives, per module and program-wide",
        "href": null
      }
    ],
    "stats": [
      {
        "value": "#1",
        "label": "highest-performing Effect House YouTube series to date"
      },
      {
        "value": "7M+",
        "label": "newsletter subscribers reached by the accompanying mission page"
      },
      {
        "value": "312k+",
        "label": "views across the 16 tutorials in the two courses I designed"
      },
      {
        "value": "LinkedIn",
        "label": "approached us about featuring Crash Course as a LinkedIn Learning course with certification"
      }
    ],
    "body": [
      {
        "t": "h2",
        "html": "The gap at the top of the funnel"
      },
      {
        "t": "p",
        "html": "Effect House had reference documentation for people who already understood augmented reality authoring, and it had a product that a large number of TikTok creators could plausibly use and had never opened. Reference documentation does not convert that second group. Someone who does not yet know what a material or a visual script <em>is</em> cannot be helped by a well-written page explaining the Material Editor's options."
      },
      {
        "t": "p",
        "html": "Crash Course was built for that gap, and the <strong>#MyFirstTikTokEffect</strong> mission was built to give finishing the course a point — a concrete thing to make and publish at the end."
      },
      {
        "t": "h2",
        "html": "Designing it as a course, not a playlist"
      },
      {
        "t": "p",
        "html": "The distinction I cared about most was that this be an actual curriculum. Working closely with a colleague on content design, I used Bloom's taxonomy to write explicit learning objectives — for each module individually and for the program as a whole — before any script was written."
      },
      {
        "t": "p",
        "html": "That ordering does real work. Learning objectives determine what a module is allowed to assume the viewer already knows, which determines module order, which determines what has to be demonstrated versus merely mentioned. Without them a tutorial series drifts toward showing off the tool's capabilities in the order the writer finds them interesting. With them, the sequence is answerable to whether a beginner can actually follow it."
      },
      {
        "t": "pull",
        "items": [
          "A video series is easy to produce and hard to make someone finish. The learning objectives were the mechanism for deciding what to cut — anything that did not serve an objective was interesting, not necessary."
        ]
      },
      {
        "t": "h2",
        "html": "What I produced"
      },
      {
        "t": "p",
        "html": "As the key writer on the project I generated all of the video and written content for Crash Course:"
      },
      {
        "t": "ul",
        "items": [
          "<strong>Scripts</strong> for every module.",
          "<strong>Narrated screencasts</strong> at production quality, delivered as the source material the final videos were built from.",
          "<strong>Companion written guides</strong> for each module, carrying the same learning objectives, reviewed with content design — so the course worked for people who prefer to read and so it stayed searchable."
        ]
      },
      {
        "t": "p",
        "html": "Two of the published pieces are still live: the course's opening module, <a href=\"https://effecthouse.tiktok.com/learn/tutorials/eh-crash-course/introduction-to-visual-scripting\">Introduction to Visual Scripting</a>, and the <a href=\"https://effecthouse.tiktok.com/learn/library/template-tutorials/art-maker\">Art Maker template tutorial</a> — a walkthrough of an AI-driven template that restyles camera input, written for creators with no technical background."
      },
      {
        "t": "p",
        "html": "On the production side I ran the relationship with our external design agency: communicating requirements and coordinating weekly asset delivery against the schedule. The screencast-plus-script handoff was the part worth getting right — supplying narrated screencasts rather than written direction alone meant the agency was matching a demonstrated interaction instead of interpreting a description of one."
      },
      {
        "t": "h2",
        "html": "The mission around it"
      },
      {
        "t": "p",
        "html": "Crash Course alone would have been a learning resource. #MyFirstTikTokEffect turned it into a program with an outcome. Working with the design and community teams, I helped develop a mission page that went out in an email newsletter to more than 7 million subscribers, giving course completers a specific, public thing to do with what they had just learned."
      },
      {
        "t": "h2",
        "html": "How it did"
      },
      {
        "t": "p",
        "html": "The program outperformed expectations. Crash Course became the highest-performing Effect House YouTube series to date, and LinkedIn approached us about featuring it as a LinkedIn Learning course with certification on completion — external validation that the instructional design held up outside our own distribution."
      },
      {
        "t": "p",
        "html": "Internally, the more useful result was that it established e-learning as something the team could do deliberately. Both Crash Course and the mission were new initiatives, and their performance is what made planning further modules on more complex topics a reasonable proposal rather than a speculative one."
      },
      {
        "t": "h2",
        "html": "What I would do differently"
      },
      {
        "t": "p",
        "html": "We measured reach well and learning poorly. Views, newsletter distribution, and series performance were all tracked; whether someone who finished Crash Course could actually build and publish an effect was not, except indirectly through mission participation."
      },
      {
        "t": "p",
        "html": "The learning objectives were written in a form that made them assessable — that is much of the point of using Bloom's taxonomy — and we never assessed against them. A short check at the end of each module, or instrumenting how many people who started module one published a mission entry, would have told us which module was losing people. Right now I can say the series performed; I cannot say which module was the weakest, and I should be able to."
      }
    ]
  }
};
