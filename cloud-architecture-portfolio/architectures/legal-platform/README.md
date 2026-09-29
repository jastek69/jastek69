# SEIR Legal AI: Legal Case Management AI Platform

[← Portfolio](../../README.md) · [Security / AI Platform](../../domains/security-ai-platform.md)

**Featured** · Child of [SEIR — Serverless SOAR](../serverless/README.md) · AWS `us-west-2` · 2026
**Repository:** [jastek69/SEIR-Serverless-SOAR-for-legal-agents](https://github.com/jastek69/SEIR-Serverless-SOAR-for-legal-agents) 🔒

> A legal case management AI platform, built as a **clone-and-layer** on the SOAR platform and first deployed for an education-law practice. Attorneys get drafted status reports, case digests, and Due Process Complaints. The models only ever see redacted records, and IAM enforces that, not a prompt.

**Three principles**

1. **Every matter has a board**: deadlines, drafts, and reminders. The platform is built and scaled out per practice area (construction, litigation, civil, and so on), and the same enum rules apply to each one.
2. **AI proposes; the firm decides.** Agents produce drafts and research aids, never filings.
3. **Security isn't bolted on.** The platform inherits SEIR's Cognito, WAF, and SOAR protection.

---

## Problem

- **Recurring deadlines are easy to miss.** Purchase-of-service renewals, IEP cadence, and status reports repeat across the whole caseload.
- **Drafting touches sensitive data.** A Due Process Complaint is assembled from IEPs, assessments, and notes that contain student identity, medical detail, and education records (PHI and FERPA).
- **Model-confident citations are a liability.** Special-education administrative decisions are poorly covered by mainstream legal search, and every citation has to be verifiable.
- **One "god role" doesn't fit a law firm.** Attorneys and paralegals need different entitlements on every surface: web, chat, and API.

## Solution

| Element | Design |
|---|---|
| **Redact before the model** | Agent roles are *denied* `s3:GetObject` on case documents. The only read path is a redaction gateway: Comprehend + Comprehend Medical produce a regenerated PDF. Scanned PDFs fail closed. |
| **Placeholders by construction** | Drafts use `[STUDENT]` / `[PARENT]` / `[DOB]` because workers *can't* read identity. An attorney re-identifies the final draft. |
| **Frozen jobs contract** | Drafting rides SOAR's shared jobs queues. Only attorneys may submit `dpc_draft`. New capability means a new job type, never a changed shape. |
| **Agentic DPC** | Optional Bedrock tool loop on Step Functions that picks which *redacted* documents to read. |
| **Monitors and dispatcher** | Deadline, payment, and case-hygiene monitors produce findings. A dispatcher plans work through applicability → policy → prerequisite → dedupe → budget. |
| **Graduated autonomy** | `observe` → `draft` → `notify`, set live in SSM. No tier ever files, serves, or emails anyone. |
| **Verifiable citations** | Drafts ship citation sidecars marked `[VERIFY]`. OpenSearch lexical (BM25) search covers administrative decisions, and semantic search fails closed until it beats lexical on a counsel-graded test set. |

## Architecture

```mermaid
flowchart LR
    subgraph Humans
        CC["Counsel Console<br/>CloudFront SPA · PKCE + MFA"]
        MCPc["Legal MCP<br/>Claude Code / Cursor"]
        API["REST /jobs"]
    end
    CC --> BFF[HTTP API BFF]
    BFF & MCPc & API --> AUTH["Cognito groups + scopes<br/>attorney / paralegal"]
    AUTH --> JOBS[(Shared SOAR jobs<br/>SQS + DynamoDB)]
    JOBS --> DW[Draft workers]
    JOBS --> SFN[Agentic DPC<br/>Step Functions + Bedrock]
    DW & SFN -->|only path to documents| RG["Redaction gateway<br/>Comprehend + Comprehend Medical"]
    RG --> S3[(S3 case data<br/>KMS · Object Lock audit)]
    DW & SFN --> BR[Amazon Bedrock]
    DW --> OUT["Draft PDF + citation sidecar [VERIFY]"]
    OS[(OpenSearch<br/>legal authorities)] --> MCPc & BFF
```

### RBAC: two layers

The same entitlements apply in the Counsel Console, over MCP, and on raw `/jobs` calls. Paralegals can't submit `dpc_draft`.

```mermaid
sequenceDiagram
  participant User as Attorney_or_Paralegal
  participant UI as Console_or_MCP_or_curl
  participant Cognito as Cognito_HostedUI
  participant APIGW as API_Gateway
  participant Lambda as BFF_or_submit_job
  participant SQS as Legal_job_queues

  User->>UI: Sign_in
  UI->>Cognito: Authorization_Code_PKCE
  Cognito->>User: MFA_TOTP
  Cognito->>UI: tokens_with_groups_and_scopes
  UI->>APIGW: Bearer_access_token
  APIGW->>APIGW: Layer1_scope_rbac_api_user
  APIGW->>Lambda: forward_JWT_claims
  Lambda->>Lambda: Layer2_cognito_groups_entitlements
  Note over Lambda: attorney_all_three_job_types
  Note over Lambda: paralegal_no_dpc_draft
  Lambda->>SQS: enqueue_if_entitled
```

### Backend: drafting, agentic DPC, MCP

Three control planes share one jobs module. Every worker path reads case documents only through the redaction agent.

```mermaid
flowchart LR
  subgraph control [Control_planes]
    MCP[legal_tools_MCP]
    REST[POST_jobs]
    PortalBFF[portal_BFF]
  end

  subgraph jobs [Shared_modules_jobs]
    Submit[submit_job]
    Status[get_job_status]
    Qsr[SQS_status_report]
    Qdpc[SQS_dpc_draft]
    Qdig[SQS_case_digest]
  end

  subgraph workers [Workers]
    DW[draft_worker]
    SFN[dpc_agent_SFN]
    Redact[redaction_agent]
  end

  MCP --> Submit
  REST --> Submit
  PortalBFF --> Submit
  MCP --> Status
  PortalBFF --> Status
  Submit --> Qsr
  Submit --> Qdpc
  Submit --> Qdig
  Qsr --> DW
  Qdig --> DW
  Qdpc --> DW
  DW -->|agentic| SFN
  DW --> Redact
  SFN --> Redact
  DW --> Bedrock[Bedrock_SSM_prompts]
  SFN --> Bedrock
```

### Frontend: Counsel Console

A CloudFront SPA with Cognito PKCE + MFA, a JWT-checked BFF, and lexical OpenSearch over administrative decisions.

```mermaid
flowchart TD
  browser[Browser] --> cf[CloudFront_SPA]
  cf --> s3web[S3_portal_assets]
  browser --> cognito[Cognito_HostedUI_PKCE_MFA]
  cognito --> browser
  browser --> bff[HTTP_API_BFF_JWT]
  bff --> cases[(case_tables)]
  bff --> submit[jobs_submit]
  bff --> status[jobs_status]
  bff --> oah[OpenSearch_OAH_lexical]
  bff --> drafts[S3_GetObject_drafts]
  status --> bff
  drafts --> browser
```

### Counsel Console screenshots

Shown with test and UAT data. The firm's name, logo, and matter IDs are masked.

**Every matter has a board**

![Matters list: status, attorney, and district per matter](../../images/legal-platform/legal-matters.webp)

![Activity: drafting jobs by agent and matter, parent reminders, and upcoming deadlines](../../images/legal-platform/legal-activity.webp)

**AI proposes; the firm decides**

![Drafts: attorney-only Due Process Complaint with [STUDENT] placeholders](../../images/legal-platform/legal-draft-dpc.webp)

| Legal agents | |
|---|---|
| [Control board](../../images/legal-platform/legal-agents-overview.webp) | Fifteen agents with live status and AI usage |
| [Roster and workflow graph](../../images/legal-platform/legal-agents-detail.webp) | Intake → redact → draft → Bedrock / OAH / MCP, with the dispatcher and agentic DPC path |

**Security isn't bolted on**

| SEIR under the console | |
|---|---|
| [SOAR agents](../../images/legal-platform/soar-agents-overview.webp) | Token tracking, WAF correlation, response, and compliance guarding auth and the edge |
| [SOAR workflow and evidence](../../images/legal-platform/soar-agents-workflow.webp) | Auth → WAF → correlate → SOAR, with reports to S3 under Object Lock |

## Impact

- **Built for a real practice, not a lab sketch.** It serves attorney and paralegal workflows across two case types with different funding and retention rules.
- **About 460 Terraform resources** in one apply. It shares the SOAR Cognito pool, WAF, REST API, and jobs module.
- **238 pytest tests** (all passing) plus a separate retrieval golden-eval set. CI runs through SOAR's reusable validate workflow, plus an upstream-drift job that flags when the parent platform moves.
- The **same control plane can serve other practice areas**: swap prompts, corpora, and obligation catalogs without forking the orchestration.

## Engineering highlights

- **Privacy is an IAM property.** Redaction isn't a best-effort pre-processing step. Model-facing roles have no path to unredacted objects at all.
- **Psychometric scores mis-tagged as ages** by entity recognition are suppressed, so drafts don't invent figures.
- **`DISPATCHED ≠ COMPLETED`.** Deferred work is an open obligation, not a skip.
- **Retrieval is honest about quality.** Lexical search passed its gold set, and embedding-based search stays disabled until it beats lexical on counsel-graded queries.

## Technologies

Terraform · Cognito · API Gateway · Lambda · Step Functions · Amazon Bedrock · Comprehend / Comprehend Medical · OpenSearch · DynamoDB · S3 Object Lock · KMS · CloudFront · SES · EventBridge · MCP (stdio + hosted HTTP) · Clio API bridge

## Repository links

- Code, operator runbook, and design deep-dives: [SEIR-Serverless-SOAR-for-legal-agents](https://github.com/jastek69/SEIR-Serverless-SOAR-for-legal-agents) 🔒
- Parent platform: [SEIR — Serverless SOAR](../serverless/README.md)
