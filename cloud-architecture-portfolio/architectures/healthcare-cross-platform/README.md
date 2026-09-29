# Japan Medical — APPI Cross-Cloud Architecture

[← Portfolio](../../README.md) · [Cloud Networking](../../domains/cloud-networking.md)

**Featured** · AWS Tokyo + São Paulo · GCP · Terraform · 2026
**Repository:** [jastek69/Armageddon-C7-LAB4-SEIR](https://github.com/jastek69/Armageddon-C7-LAB4-SEIR) 🔒

> A multi-region, multi-cloud medical application where doctors anywhere can read and write patient records, but the records (PHI) are stored only in Japan, as Japan's privacy law (APPI) requires. *Global access doesn't require global storage.*

---

## Problem

- **Access is allowed; storage abroad isn't.** Japanese patient medical data must physically stay in Japan, even when the patient or doctor is overseas.
- **Doctors are on two clouds.** São Paulo staff run on AWS, and New York staff run on GCP.
- **Compliance needs visible paths.** Auditors have to be able to follow where every read and write travels.

## Solution

| Region | Role | Holds PHI? |
|---|---|---|
| 🇯🇵 **Tokyo** (AWS) | Data authority: RDS, TGW hub, Secrets Manager, logging, backups | **Yes, only here** |
| 🇧🇷 **São Paulo** (AWS) | Stateless compute: ASG + Transit Gateway spoke | No |
| 🇺🇸 **New York** (GCP) | Stateless compute: MIG behind an internal HTTPS load balancer, HA VPN + BGP to the AWS TGW | No |

- **Transit Gateway instead of VPC peering.** It gives centralized, auditable routing: a visible data corridor for compliance review.
- **Single global URL.** CloudFront terminates TLS, applies WAF, caches only content marked safe, and never stores PHI. Origins are cloaked behind CloudFront's managed prefix list.
- **If Tokyo is down, the system degrades, but residency is never violated.** That tradeoff is intentional: some latency in exchange for legal certainty.

## Architecture

```mermaid
flowchart LR
    DOC[Doctors worldwide] --> CF["CloudFront + WAF<br/>single global URL"]
    CF --> SP["São Paulo EC2 ASG<br/>stateless"]
    CF --> TKA[Tokyo ALB + app tier]
    SP --> TGWSP[TGW São Paulo] <-->|TGW peering| TGWTK[TGW Tokyo]
    NY["GCP New York MIG<br/>internal HTTPS ILB · no public IPs"] --> CR[Cloud Router BGP]
    CR <-->|"HA VPN · 4 tunnels · BGP<br/>tunnel rotation"| TGWTK
    TGWTK --> VPC[Tokyo VPC] --> RDS[("RDS — PHI<br/>KMS · Secrets Manager rotation")]
    TKA --> RDS
    RDS -. CloudWatch alarm .-> SNS[SNS] --> IR["Evidence bundle Lambda<br/>→ Bedrock incident report"]
```

### Full topology

![SEIR Medical topology: Tokyo data authority, São Paulo spoke, GCP New York over HA VPN, and the IR + translation pipeline](../../images/healthcare-cross-platform/seir-medical-topology.png)

### Data paths: PHI only in Tokyo

São Paulo and New York are stateless compute. Every PHI read and write crosses TGW peering or HA VPN into Tokyo.

```mermaid
flowchart LR
    D[Doctors worldwide] --> CF["CloudFront + WAF<br/>single URL · TLS · safe-only cache"]
    CF --> TALB[Tokyo ALB]
    CF --> SPA[São Paulo ALB]
    subgraph SP["🇧🇷 São Paulo — stateless"]
        SPA --> SPASG[EC2 ASG] --> SPTGW[TGW spoke]
    end
    subgraph NY["🇺🇸 New York GCP — stateless"]
        MIG["MIG · no public IPs"] --> ILB["Internal HTTPS ILB<br/>CAS certificate"]
        MIG --> BGP[Cloud Router — BGP]
    end
    subgraph TK["🇯🇵 Tokyo — data authority"]
        TALB --> TASG[App ASG]
        TTGW[TGW hub]
        TASG & TTGW --> RDS[("RDS — PHI<br/>KMS CMK")]
        SM[Secrets Manager + rotation Lambda] -.-> RDS
    end
    SPTGW <==>|TGW peering| TTGW
    BGP <==>|"HA VPN · 4 IPsec tunnels · BGP"| TTGW
```

### Origin cloaking

The ALB only answers CloudFront, and only when the secret origin header matches.

```mermaid
flowchart TD
    R[Request to ALB] --> SG{"Source in CloudFront<br/>managed prefix list?"}
    SG -->|no| DROP[SG drop — connection fails]
    SG -->|yes| H{"Secret origin header<br/>present and correct?"}
    H -->|no| BLK["Listener default rule → 403"]
    H -->|yes| APP[Forward to app target group]
```

### Auto incident response (human in the loop)

Bedrock drafts and Translate localizes. A human verifies alarm, logs, and config before the report is final.

```mermaid
sequenceDiagram
    autonumber
    participant CW as CloudWatch alarm
    participant SNS as SNS trigger topic
    participant L as IR Lambda
    participant B as Amazon Bedrock
    participant TR as Amazon Translate
    participant S3 as S3 IR reports (versioned, SSE)
    participant H as On-call human
    CW->>SNS: ALARM
    SNS->>L: invoke
    L->>L: collect evidence bundle<br/>(alarm metadata, Logs Insights, config sources)
    L->>B: draft incident report
    L->>TR: localized copy
    L->>S3: report JSON + MD
    L->>SNS: reports topic → notify
    H->>S3: retrieve report + evidence
    H->>H: verify alarm, raw logs, config (runbook steps 2–5)
    H->>S3: finalize and archive
```

### Stack dependencies (apply order)

Four independently deployable stacks, wired through remote state.

```mermaid
flowchart LR
    SEED[GCP seed] --> T[Tokyo/] --> G[global/] --> N[newyork_gcp/] --> S[saopaulo/]
    T -. remote state: TGW, VPC, RDS outputs .-> N & S & G
```

## Impact

- **About 310 Terraform resources** across two AWS regions and a GCP project, including KMS, Secrets Manager rotation with Lambda, a private CA-issued certificate on the GCP ILB, and private DNS.
- **Auto incident response (human-in-the-loop).** CloudWatch alarm → SNS → a Lambda that gathers an evidence bundle → a Bedrock-drafted incident report with translation. A documented six-step runbook has a human verify alarm metadata, logs, and config sources before finalizing.
- **Operational tooling.** Staged apply and destroy scripts, sanity checks run on instances over SSM, VPN tunnel-rotation and WIF runbooks, and a Jenkins pipeline.

## Engineering highlights

- **The GCP side has two separate Cloud Routers**, one for NAT and one for BGP to AWS, so VPN routing and outbound egress never share a failure domain.
- **Keyless cross-cloud identity.** Workload Identity Federation instead of service-account keys.
- **Cleanup is part of the design.** Region-by-region "must verify clean" checklists and a verification script cover resources that block `terraform destroy`.

## Technologies

Terraform · AWS Transit Gateway + peering · GCP HA VPN · Cloud Router (BGP) · Internal HTTPS Load Balancer · CloudFront · WAFv2 · ACM + GCP Certificate Authority Service · RDS · KMS · Secrets Manager rotation · CloudWatch · SNS · Lambda · Amazon Bedrock · Amazon Translate · SSM · Jenkins

## Repository links

- Code, deployment guide, and runbooks: [Armageddon-C7-LAB4-SEIR](https://github.com/jastek69/Armageddon-C7-LAB4-SEIR) 🔒
- Related: [Zion — Multi-Region Transit Gateway](../transit-gateway/README.md)
