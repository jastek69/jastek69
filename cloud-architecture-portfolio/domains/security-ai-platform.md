# Security / AI Platform

[← Portfolio](../README.md)

Security automation and governed AI on AWS and GCP. This domain holds the portfolio's flagship: a serverless SOAR platform whose patterns carry into a legal drafting product, a GPU inference worker, a RAG corpus layer, and a policy-aware model router.

---

## Overview

The shared idea: **AI is useful for explaining, investigating, and drafting, and dangerous when it's allowed to authorize.** Every system here puts a deterministic, testable layer between the model and anything that matters:

| Concern | Who decides |
|---|---|
| Is this caller allowed? | Cognito scopes → Lambda claim check → IAM (three independent layers) |
| How severe is this finding? Which playbook applies? | Deterministic code (`fusion.py`, playbooks) |
| May this data go to this model? | Policy gate (Agent 11), redaction gateway enforced by IAM (Legal) |
| What does it mean, in plain language? | Bedrock / Vertex, with a templated fallback if the model is down |

---

## Architecture themes

- **MCP as the analyst's control plane.** SOAR exposes 26+ read and action tools, and the Legal AI project exposes the firm's own tool set. Both have stdio and hosted HTTP transports behind Cognito JWTs.
- **Agentic loops that are bounded.** Step Functions + Bedrock Converse choose from *read-only* tools until they submit structured findings. `human_review_required` stays true.
- **DynamoDB is the system's memory, S3 holds the evidence.** Event payloads are only addresses. Agents re-read authoritative state before acting, and conditional puts make redelivery a no-op.
- **One platform, many consumers.** The SOAR jobs API (Cognito/WAF-gated `POST /jobs`, SQS, DynamoDB) runs legal drafting and GPU image generation alike. Reusable GitHub Actions workflows validate every descendant repo.

---

## Featured projects

### [SEIR — Serverless SOAR](../architectures/serverless/README.md) · *parent platform*

Layered RBAC, token-lifecycle tracking, and autonomous WAF correlation feeding four response agents in parallel. Adds threat-intel enrichment (AbuseIPDB, CISA KEV, MITRE ATT&CK), an agentic investigation tier, and multilingual executive and compliance reporting.

`Terraform` `Lambda` `Cognito` `WAFv2` `Bedrock` `Step Functions` `DynamoDB` `MCP`
→ **Repository:** [jastek69/SEIR-Serverless-SOAR](https://github.com/jastek69/SEIR-Serverless-SOAR) 🔒

### [SEIR Legal AI](../architectures/legal-platform/README.md) · *child of SOAR*

An attorney-facing drafting fleet for an education-law practice: status reports, case digests, and Due Process Complaints drafted only from redacted records. It includes a Counsel Console SPA, a legal MCP server, and OpenSearch retrieval over legal authorities.

`Terraform` `Bedrock` `Comprehend Medical` `OpenSearch` `CloudFront` `Step Functions` `MCP`
→ **Repository:** [jastek69/SEIR-Serverless-SOAR-for-legal-agents](https://github.com/jastek69/SEIR-Serverless-SOAR-for-legal-agents) 🔒

---

## Supporting projects

### [Agent 11 — Policy-Aware Model Routing](../architectures/agent11/README.md)

An orchestration layer that routes reasoning requests across an external foundation model, a company cloud LLM, and an on-prem Llama. Policy, capability, service health, and network path are evaluated as four separate questions, and routing fails closed when no compliant route exists.

`Python` `MCP` `EC2` `Ollama / Llama` `typed domain models`
→ **Repository:** [jastek69/armageddon-12E-Agent11](https://github.com/jastek69/armageddon-12E-Agent11) 🔒

### [ComfyUI GPU Inference Worker](../architectures/comfyui-stability/README.md) · *child of SOAR*

A headless ComfyUI GPU instance on a Packer-baked AMI. All state lives in S3, so the EC2 is disposable. The instance doubles as a SOAR jobs-queue worker.

`Terraform` `Packer` `EC2 GPU` `S3` `Route 53` `SQS`
→ **Repository:** [jastek69/stability-matrix-headless-aws-infra](https://github.com/jastek69/stability-matrix-headless-aws-infra) 🔒

### [Vertex AI RAG Corpora](../architectures/vertex-rag/README.md)

Four Vertex AI RAG Engine corpora (~1,300 documents) queried from AWS Lambda through Workload Identity Federation, so no GCP keys are ever stored. The corpus registry lives in SOAR's SSM.

`Vertex AI RAG Engine` `text-embedding-005` `Workload Identity Federation` `Terraform` `Python`
→ **Repository:** not yet published

---

## Supporting articles and diagrams

- SOAR architecture diagrams: [auth flow](../diagrams/SEIR-Serverless-SOAR/Infra01-authflow.JPG) · [WAF flow](../diagrams/SEIR-Serverless-SOAR/Infra02-WAFflow.JPG) · [MCP flow](../diagrams/SEIR-Serverless-SOAR/Infra03-MCPflow.JPG) · [agent triggers](../diagrams/SEIR-Serverless-SOAR/Infra06-AgentsTriggerTop.JPG) · [DynamoDB memory](../diagrams/SEIR-Serverless-SOAR/Infra07-DynamoDBMemory.png)
- Vectors and seed variance: [notes](../vectors/README_vectors_and_seed_variance.md)
