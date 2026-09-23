/* =================================================================
   CASE STUDIES — one entry per project in PROJECTS, keyed by slug.
   Each case page renders from here, and edit mode writes back here.
   ================================================================= */

const CASES = {
  "docs-quality-tooling": {
    "kicker": "Personal project · 2026",
    "title": "Turning a style guide into something a machine can check",
    "deck": "I wrote TikTok's developer style guide. I wanted to find out how much of it a machine could enforce on its own — and where that stops working.",
    "description": "A personal project encoding a developer style guide as automated checks, built with Claude Code and measured against 553 pages of public documentation. A proof of concept.",
    "meta": [
      {
        "label": "What this is",
        "value": "A personal project, and a proof of concept",
        "href": null
      },
      {
        "label": "Built with",
        "value": "Claude Code, Vale, OpenAPI",
        "href": null
      },
      {
        "label": "My part",
        "value": "The rules, the test design, and judging the results",
        "href": null
      },
      {
        "label": "Tested against",
        "value": "Meilisearch documentation — public, 553 pages",
        "href": null
      }
    ],
    "stats": [
      {
        "value": "553",
        "label": "pages of documentation I did not write, used as the test"
      },
      {
        "value": "36%",
        "label": "fewer style violations after the automatic fixes ran"
      },
      {
        "value": "16 of 16",
        "label": "problems the freshness checker reported that were real"
      },
      {
        "value": "23 of 40",
        "label": "style-guide rules a machine can check; the other 17 need a person"
      }
    ],
    "body": [
      {
        "t": "h2",
        "html": "The question"
      },
      {
        "t": "p",
        "html": "A style guide only works if somebody enforces it. Across a large documentation set that means a person reading every page and noticing that a heading is capitalized wrong, or that a product name is written three different ways. This is time consuming and therefore not often addressed."
      },
      {
        "t": "p",
        "html": "Linters can solve this problem: a tool reads your work, checks it against a list of rules, and flags anything that breaks one. It runs automatically every time, delivering consistent results."
      },
      {
        "t": "p",
        "html": "I wrote the TikTok for Developers style guide. This project was me finding out how much of it a linter could enforce, using a style guide I know well as the test case."
      },
      {
        "t": "h2",
        "html": "What it does"
      },
      {
        "t": "p",
        "html": "<strong>A style linter.</strong> 40 rules taken from the style guide — heading capitalization, which word to use for a requirement, banned punctuation, product names spelled consistently. It reads a page and flags anything that breaks one."
      },
      {
        "t": "p",
        "html": "<strong>A freshness checker.</strong> Documentation goes stale when the product changes and the page does not. This compares what a page claims about an API against the API's own definition, and reports where they disagree: an endpoint that moved, a parameter that was renamed, a value that no longer exists."
      },
      {
        "t": "p",
        "html": "<strong>A pipeline</strong> that runs both on a schedule, for documentation that does not live in a code repository."
      },
      {
        "t": "h2",
        "html": "How it actually works"
      },
      {
        "t": "p",
        "html": "<strong>The style linter is built on Vale</strong>, an open-source tool for checking prose. Each rule is a small configuration file: a pattern to look for and a message to show when it matches. Vale reads the Markdown and reports every hit with a line number. The work was translating the style guide into 40 of those, and deciding which ones were worth having at all."
      },
      {
        "t": "p",
        "html": "<strong>The freshness checker compares two descriptions of the same thing.</strong> An API has a machine-readable definition — an OpenAPI file listing every endpoint, parameter and valid value. The documentation describes that same API in prose and code samples. If the page says a parameter is called <code>user_id</code> and the definition says <code>userId</code>, the page is wrong. The checker reads both and reports the disagreements."
      },
      {
        "t": "h2",
        "html": "How I built it"
      },
      {
        "t": "p",
        "html": "I built these tools with Claude Code. I decided what the tools should do, wrote the rules, chose what to test them against, and said what evidence I wanted before believing any of it. Claude wrote the implementation. I read the output, ran it against real documentation, and decided what to keep."
      },
      {
        "t": "p",
        "html": "The most fascinating part of this project was not the code: it was working out what a machine can usefully check, what it cannot, and how to tell the difference, and that part does not come from the tool."
      },
      {
        "t": "h2",
        "html": "Testing it on documentation I did not write"
      },
      {
        "t": "p",
        "html": "A style rule tested against text you already agree with proves nothing. I needed a documentation set that was public, large, and not mine."
      },
      {
        "t": "p",
        "html": "I used the Meilisearch documentation: 553 pages, open source, pinned to a specific version so the results can be checked, along with its official API definition. Nothing was picked to make the tools look good, and several rules were dropped once it was clear their output was mostly noise."
      },
      {
        "t": "p",
        "html": "Running the rules and applying the automatic fixes cut style violations by 36%: 1,092 down to 704."
      },
      {
        "t": "h2",
        "html": "What the numbers mean"
      },
      {
        "t": "p",
        "html": "The tool has two main criteria:&nbsp;"
      },
      {
        "t": "ul",
        "items": [
          "<strong>Precision</strong> — of the problems it reported, how many were real.",
          "<strong>Recall</strong> — of the real problems, how many it found."
        ]
      },
      {
        "t": "p",
        "html": "Both are governed by a single dial. Every finding the checker produces carries a confidence score between 0 and 1, built out of what it was able to verify: whether it could tell which server the claim was aimed at, whether the claim came from a code sample or from looser prose, and whether the surrounding page looks like it is about this API at all. The tool reports only the findings that score above a set threshold."
      },
      {
        "t": "p",
        "html": "Nearly every false alarm traced back to one cause. A documentation page often discusses more than one API. A migration guide explaining how to move off Elasticsearch is full of Elasticsearch addresses, and none of those appear in Meilisearch's index, so each one looks like an endpoint that no longer exists. That single confusion accounts for effectively all 30 of the false positives below."
      },
      {
        "t": "table",
        "caption": "What the confidence threshold buys, measured on the Meilisearch corpus. The recall column carries a caveat, covered in the next section.",
        "head": [
          "Threshold",
          "Reported",
          "Real",
          "False alarms",
          "Precision",
          "Recall"
        ],
        "rows": [
          [
            "0.00 (report everything)",
            "51",
            "21",
            "30",
            "0.41",
            "1.00"
          ],
          [
            "0.45",
            "20",
            "16",
            "4",
            "0.80",
            "0.76"
          ],
          [
            "<strong>0.60 (what it ships with)</strong>",
            "<strong>16</strong>",
            "<strong>16</strong>",
            "<strong>0</strong>",
            "<strong>1.00</strong>",
            "<strong>0.76</strong>"
          ],
          [
            "0.70",
            "5",
            "5",
            "0",
            "1.00",
            "0.24"
          ]
        ]
      },
      {
        "t": "p",
        "html": "That table is the argument for 0.60. Reporting everything means three false alarms for every two real findings, which is how a tool gets switched off in its first week. Raising the bar from 0.45 to 0.60 costs nothing: the same 16 real findings survive and the last four false alarms disappear. Going further to 0.70 buys no additional precision and discards two thirds of what the tool found. 0.60 is the point where precision reaches 1.00 and recall has not yet started to fall."
      },
      {
        "t": "pull",
        "items": [
          "A writer with a short list they can trust will work through it. A writer with a long list that is wrong half the time stops opening it."
        ]
      },
      {
        "t": "h2",
        "html": "The mistake worth investigating"
      },
      {
        "t": "p",
        "html": "The first time I measured how well the freshness checker worked, it scored perfectly. That was a warning sign, not a result."
      },
      {
        "t": "p",
        "html": "To measure a tool you need an answer key — a list of the problems genuinely present in the documentation. I had built that list by reading the tool's own output. So of course it found everything on it: anything it missed never made it onto the list in the first place. The score was decided before I ran it."
      },
      {
        "t": "p",
        "html": "The fix was a second answer key, built by hand, checking pages against the API definition without looking at the tool at all. The first time I ran against that one, the tool scored zero."
      },
      {
        "t": "p",
        "html": "It is easy to produce a number that looks like evidence and is not, and I would rather be the person who caught it than the person who shipped it."
      },
      {
        "t": "h2",
        "html": "Where this stands: a proof of concept"
      },
      {
        "t": "p",
        "html": "The rules encode a real style guide and the results are measured on real documentation. But of 40 checkable items in that style guide, 23 can be automated and 17 need a person — voice, argument structure, whether an example is actually useful."
      },
      {
        "t": "p",
        "html": "The gap between this and something usable at work is the content itself. TikTok's developer documentation lives in an internal CMS, not a folder of Markdown that a pull request can check. The checks would work on the text; getting the text out of the CMS on a schedule, and getting findings back to writers somewhere they already look, is the part that would have to be built."
      },
      {
        "t": "p",
        "html": "The approach is demonstrated and the numbers are real. Putting this tool to work on TikTok's developer documentation is a continuing endeavor, but the foundation for it has been established."
      }
    ]
  },
  "tiktok-minis": {
    "kicker": "TikTok · TikTok for Developers · 2025–present",
    "title": "Documenting TikTok Minis so developers could onboard themselves",
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
        "value": "&lt;10 → 200+",
        "label": "app launches per two-week cycle after onboarding moved to self-service"
      },
      {
        "value": "4×",
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
        "t": "figure",
        "src": "/_blob/2b77511cb8cac2aba45e9a552a32a3d3",
        "assetId": "2b77511cb8cac2aba45e9a552a32a3d3",
        "alt": "TikTok Minis UI mobile",
        "caption": "",
        "size": "full",
        "align": ""
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
        "html": "I collaborated closely with engineering, operations, and product management stakeholders to develop and deliver the entire public documentation set for TikTok Minis and Mini Games: the introduction and platform concepts, the mini games and mini dramas build guides, and the monetization documentation. All requests for documentation came through me, and I was the sole publisher."
      },
      {
        "t": "table",
        "caption": "",
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
        ],
        "foot": true
      },
      {
        "t": "h2",
        "html": "The integration workflow"
      },
      {
        "t": "p",
        "html": "The core work was documenting the integration workflow end to end so it could be followed without a partner manager in the loop. The process itself included both configuration guidelines for our developer platform and technical specifications for API and SDK integrations. Once the comprehensive workflow was published, intake stopped being a conversation and became a process: 359 developers were screened across 29 countries, and biweekly launches moved from fewer than 10 to more than 200."
      },
      {
        "t": "h2",
        "html": "Compliance and business screening"
      },
      {
        "t": "p",
        "html": "Scaling a developer platform into new markets raises a problem that is the opposite of a growth problem: every additional developer is an additional entity you have to know something about. I wrote the end-to-end compliance and Know Your Business (KYB) processes."
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
        "html": "Ad monetization documentation has a property most developer documentation does not: the difference between a correct and an incorrect implementation shows up directly in the developer's revenue. Documenting the monetization APIs well enough that developers configured them properly contributed to an average ROAS increase for in-app ads of more than 100% in Q4 2025."
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
    "title": "Migrating a documentation platform, and rebuilding what it said",
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
        "t": "figure",
        "src": "/_blob/82544ece0406889491258418fbc2f52b",
        "assetId": "82544ece0406889491258418fbc2f52b",
        "alt": "Effect House tool",
        "caption": "Effect House program",
        "size": "full",
        "align": ""
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
        "html": "I wrote the TikTok for Developers style guide from scratch and applied it while reviewing API documentation. For Effect House, I expanded the existing learning resources style guide with specifications it had been missing: table formatting, verbiage conventions, and — the one that mattered most for a tool-centric docs set — how to reference in-tool navigation so that every guide pointed at the interface the same way. I also wrote guidelines for Markdown formatting."
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
        "t": "h2",
        "html": "What I would do differently"
      },
      {
        "t": "p",
        "html": "Everything above was enforced by review, which means it was enforced as consistently as the reviewer's attention on a given day. That is a real ceiling, and I hit it."
      },
      {
        "t": "p",
        "html": "A meaningful share of what these guides specify is mechanically checkable: approved terminology, table conventions, heading structure, how in-tool navigation is referenced, link health, whether a page has gone stale relative to the release it documents.&nbsp;"
      },
      {
        "t": "p",
        "html": "What I would build now is the linter — terminology and structural rules encoded as automated checks running in CI on every pull request, with human review reserved for the things that actually require judgment: whether the explanation is correct, whether the page is aimed at the right reader, whether it should exist at all. The style guide stops being a document people are supposed to have read and becomes a property of the pipeline."
      }
    ]
  },
  "crash-course": {
    "kicker": "TikTok · Effect House · 2023–2025",
    "title": "Crash Course, an AR curriculum for people who have never opened the tool",
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
        "html": "The distinction I cared about most was that this be an actual curriculum. Working closely with content design, I used Bloom's taxonomy to write explicit learning objectives — for each module individually and for the program as a whole — before any script was written."
      },
      {
        "t": "p",
        "html": "Learning objectives determined what a module is allowed to assume the viewer already knows, which determines module order, which determines what has to be demonstrated versus merely mentioned. Without them a tutorial series would have drifted toward showing off the tool's capabilities without substance. With them, the sequence is answerable to whether a beginner can actually follow it."
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
        "html": "The&nbsp;<a href=\"https://effecthouse.tiktok.com/learn/tutorials/eh-crash-course/introduction-to-visual-scripting\">Introduction to Visual Scripting</a>&nbsp;module is an example of a lesson written for creators with no technical background."
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
