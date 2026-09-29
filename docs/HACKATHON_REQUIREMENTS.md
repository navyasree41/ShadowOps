# Hackathon Requirements and Traceability

Status: Phase 0/1 planning. No application code has been implemented yet.

Source documents: the attached **Problem Statements: AI Agents That Learn Using Hindsight** and **Hindsight Hackathon Content Submission Guide**. The separate ShadowOps project brief is treated as the product/build specification, not as an official hackathon rule.

## A. Official Requirements

### Mandatory requirements

- Build an AI-powered application using Hindsight.
- Clearly demonstrate persistent memory and learning from past interactions; memory must be central to the value, not decorative.
- Solve a real professional/business problem. Avoid student-centric project concepts.
- Submit a clean, documented GitHub repository, a demo video, a live project demo to judges, content deliverables, and an explanation of how Hindsight is used.
- Every team member must submit an article and a social post. The team submits one video for the content contest. Content must be in English.
- Articles must be public and linkable. The project article must also be shared as a Reddit link post in one of the named subreddits.
- Article and social content must not mention the hackathon, including titles, body text, or hashtags.
- Submit the article, social post, and team video described in the Content Guide.

### Recommendations, not additional mandatory rules

- Use Hindsight Cloud or the open-source server; Groq is suggested, with `openai/gpt-oss-120b` and `qwen/qwen3-32b` as recommended models. Any LLM is permitted.
- Make memory visible with a before/after and a learning curve; demonstrate a value change quickly (the guide says the best stories are clear within 60 seconds).
- Prefer a real workflow the builders care about, tight scope, realistic data (real datasets where useful, or believable synthetic data), and a project suitable for a portfolio. The guide suggests asking whether a business might pay about $50/month as a rough project-selection test; it is not a pricing or judging requirement.
- The guide offers professional use-case categories/examples and the self-driving-agents repository for inspiration. These are examples, not requirements.
- Optional tools/resources include the Hindsight Community Slack; Code.in, Jules, and OpenCode as coding-agent options; and the official OpenClaw integration. Coding agents are optional; hand-coding is allowed.
- Cloud promo code `MEMHACK99` is an optional credit offer, applied after registration in the billing section; it is not a project requirement.

## B. Judging Criteria and Weights

| Criterion | Weight | What judges look for | Planned evidence |
|---|---:|---|---|
| Innovation | 30% | Fresh take on a real problem beyond an obvious chatbot | Incident response that carries failed and successful remediation across incidents |
| Use of Hindsight Memory | 25% | Memory is central; agent visibly improves over time | Real retain/recall, memory-backed recommendation, outcome/lesson timeline, controlled comparison |
| Technical Implementation | 20% | Clean, functional, well-architected implementation | Modular FastAPI/React app, validated tools, error handling, tests, repeatable demo |
| User Experience | 15% | Intuitive interaction, visible reasoning, compelling demo | Incident investigation view with evidence, tool progress, historical recall, and outcome actions |
| Real-world Impact | 10% | Genuine problem and adoption path | SRE/DevOps incident workflow using realistic simulated services and data |

No score or performance improvement is claimed by this plan.

## C. Required Technologies

- Hindsight is mandatory. Its retain/recall operations must provide meaningful persistent agent memory.
- The Problem Statement does not mandate a programming language, frontend framework, backend framework, or LLM provider. React, TypeScript, Tailwind CSS, Vite, FastAPI, Python, and Groq are proposed by the ShadowOps project brief; they are implementation choices, not official rules.
- Hindsight Cloud and the open-source version are both permitted by the Problem Statement.
- Any LLM provider is permitted. Groq is a recommendation only; the named models are `openai/gpt-oss-120b` and `qwen/qwen3-32b`. The Problem Statement also recommends handling function-calling errors.
- Optional resources include Hindsight Cloud or the open-source server, the Hindsight Community Slack, the official OpenClaw integration, and the self-driving-agents repository for inspiration. These do not add mandatory technologies or deliverables.

## D. Submission Requirements

1. GitHub repository with clean, documented code.
2. Demo video showing the agent in action.
3. Live project demo to judges.
4. Each team member's public article and social post, plus one team video, following the Content Guide.
5. An explanation of how Hindsight memory is used.
6. A public, linkable article; a Reddit link post to that article in one of: `r/llmdevs`, `r/sideproject`, `r/aiagents`, or `r/aimemory`.

## E. Content Requirements

The complete per-artifact checklist and the guide's internal inconsistencies are recorded in [CONTENT_REQUIREMENTS.md](CONTENT_REQUIREMENTS.md). Key requirements include public English-language articles, no hackathon references in article/social content, Hindsight links and project-specific evidence, screenshots/images, individual LinkedIn posts, and one public YouTube team video.

## F. Demo Requirements

Official guidance expects a concise story that makes the problem and memory benefit obvious. The content video is 2–5 minutes, 1080p minimum, screen-recorded with voiceover; talking head is preferred but optional. It should introduce builder/project, show the problem without memory, show a real interaction including retain/recall, and close with one takeaway. The live judge demo should also make the before/after memory behavior easy to see.

## G. Hindsight Requirements

- Use actual Hindsight operations, not a local imitation, vector database, or UI-only memory claim.
- Persist resolved incident learning and retrieve it on a later similar incident.
- Preserve evidence that distinguishes failed remediation from successful remediation.
- Use returned memory content as the historical evidence shown to the agent and UI. If Hindsight is unavailable or unconfigured, surface an explicit setup/error state; do not fabricate a memory response.
- The application may use a separate database for application state, but it does not replace Hindsight's long-term memory role.
- Hindsight recall ranking scores are relative ranking signals, not calibrated probabilities. Do not label them as percent similarity/confidence without an independently implemented, validated, clearly named metric.

## H. Risks / Things to Avoid

- A generic chatbot, an agent that only stores chat transcripts, or a UI that merely claims to have remembered an incident.
- Treating a recommendation as a proven remediation before recording a real simulated outcome.
- Hardcoded memory results, dashboard totals, outcome counts, similarity percentages, benchmarks, or performance claims.
- Claiming that all Hindsight calls succeeded when credentials, server, or LLM provider are missing.
- Using production/cloud infrastructure or production observability as a prerequisite for the core demo.
- Exposing provider keys or Hindsight credentials in the browser, logs, committed files, screenshots, or video.
- Promoting the hackathon in article/social content; the content guide says such content is disqualified.
- Submitting an unedited AI draft, a private/unlinkable article, a Google Drive-only video, or an article without screenshots/images.
- Treating optional recommendations (Groq, promo credits, talking head, named platforms) as mandatory requirements.

## I. Requirement Traceability Matrix

All implementation, evidence, and submission entries below are planned, not completed. Paths are proposed for the eventual application.

| Requirement | Planned implementation | Planned file/module | Demo evidence | Submission evidence |
|---|---|---|---|---|
| Build an AI application with required Hindsight | FastAPI agent calls Hindsight retain and recall on the incident loop | `backend/hindsight/`, `backend/agents/` | API status plus live memory recall | GitHub source and Hindsight explanation in README/article |
| Solve real professional problem; not student-centric | SRE incident diagnosis and remediation learning | `backend/incidents/`, `frontend/` | Checkout 503 incident story | Repository, article, and video |
| Innovation (30%) | Learn from failures and successes across incidents | `backend/services/learning.py` (planned) | Show generic response vs evidence-backed repeat response | Article and demo video |
| Hindsight central (25%) | Durable retain/recall in decision path; Hindsight retrieval is the only historical memory source | `backend/hindsight/`, `backend/agents/` | Show actual returned recall facts and source incident | Hindsight architecture doc, repository, video |
| Technical implementation (20%) | Modular architecture, schemas, bounded tools, error states, tests | `backend/`, `frontend/`, `tests/` | Tool calls, failure handling, testable demo scenario | GitHub repository and README |
| UX (15%) | Incident workspace, timeline, memory evidence, status | `frontend/src/` | Walk through one investigation and resolved outcome | Live demo/video/screenshots |
| Real-world impact (10%) | Realistic SRE scenario and feasible local/demo deployment | `data/`, `docs/DEMO_RUNBOOK.md` | Demonstrate checkout incident and repeat | Article and README |
| GitHub repository with clean documented code | Source, setup instructions, docs, env template, no committed secrets | Repository root and `README.md` | Run from documented setup | Public repository URL in submissions |
| Live project demo to judges | Deterministic simulated environment; no real production dependencies | `backend/tools/`, `frontend/` | Run through incident, action, outcome, repeat | Live judge presentation |
| Article for every member | Individual engineer-authored, edited public article | External publishing platform; draft artifact planned later | Article explains real workflow and Hindsight role | Public URL per member |
| Social post for every member | Individual LinkedIn post complying with content rules | External LinkedIn post | No app demo required | Post URL per member |
| One team video | Public 2–5 minute YouTube recording, minimum 1080p | External YouTube upload | Screen recording of real retain/recall and incident workflow | Public YouTube URL |
| Explain Hindsight use | State what is retained, when recalled, how outcomes influence the next recommendation | `docs/HINDSIGHT_ARCHITECTURE.md`, `README.md` | Show actual memory evidence | Repo docs and content |
| Article public/linkable, English, 800–1,500 words | Per-member article; use 1,200–1,500 words to satisfy the guide's intersecting word-count instructions | External article | N/A | Public article URL and word-count review |
| No hackathon mention in article title/body | Editorial check before publish | Article checklist | N/A | Final public article |
| Article has specific hook, problem, integration, code, before/after, lesson | Use the guide's story structure; include real code and one honest limitation | Article checklist | Screen evidence for factual claims | Final article |
| Article links to Hindsight GitHub, docs, and Vectorize agent-memory page | Include all three required URLs naturally | Article checklist | N/A | Link check on published article |
| Article screenshots/images | Add project/UI and/or terminal/code images and an architecture diagram | Article checklist, `docs/ARCHITECTURE.md` | Capture real app and retain/recall | Images embedded in public article |
| Article publication platform | Medium, Dev.to, Hashnode, Substack, LinkedIn Articles, or another public/linkable platform | External publisher | N/A | Public URL; not a Google Drive document |
| Reddit article link post | Link-post to one of four named subreddits | External Reddit post | N/A | Link-post URL |
| Tag Code.in on LinkedIn and articles | Include the requested mention/tag where platform supports it; verify final presentation | External article/post checklist | N/A | Visible tag/mention in published content |
| LinkedIn post: no hackathon mention; under 800 chars | Individual post; check character count and wording | External LinkedIn post | N/A | Public post URL |
| LinkedIn hook/body/hashtags | Curiosity-led first two lines with no hashtags/links; 3–7 technical takeaways; before/after; Hindsight positively mentioned; 3–5 hashtags on final line | External LinkedIn post | N/A | Final post reviewed against checklist |
| Project GitHub link in LinkedIn main post | Include project repository URL in main post | External LinkedIn post | N/A | Main post URL |
| Article URL as first comment; Hindsight GitHub as a comment | Add article link as first comment; add `https://github.com/vectorize-io/hindsight` in a comment | External LinkedIn comments | N/A | Visible comments |
| Video length, format, and content | 2–5 minutes, 1080p minimum, screen capture with voiceover; intro, problem, real demo, takeaway | External video; later `docs/DEMO_RUNBOOK.md` | Show real retain/recall and before/after | Public YouTube video |
| Video title and thumbnail | Choose a title; create 16:9 thumbnail using the supplied guide's Nano Banana prompt process | External video | N/A | Public YouTube thumbnail/video |
| Video posted publicly on YouTube | Publish public video, not a Drive-only link | External YouTube channel | N/A | Public video URL |
| Current product-specific learning story and learning curve | Real retained incident outcomes; demonstrate baseline and later recalls after 5/10/20 actual seeded or recorded interactions (the project brief allows adjusting exact counts) | `data/incidents/`, `backend/`, `docs/DEMO_RUNBOOK.md` | Repeatable live run with actual recall facts at selected history depths | Video and repo |

## Phase 1 Gate

The proposed design addresses each official deliverable and judging category without claiming implementation or results. It uses the only mandated technology, Hindsight, for meaningful cross-incident memory; keeps optional tool choices distinct from official rules; and makes content production a tracked per-member checklist. Implementation should begin only after the team accepts this plan and configures a real Hindsight endpoint/key (or local service) and its extraction LLM provider.
