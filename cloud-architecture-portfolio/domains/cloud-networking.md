# Cloud Networking

[← Portfolio](../README.md)

Multi-region and multi-cloud network architecture in Terraform: Transit Gateway meshes, HA VPN with BGP, hub-and-spoke on Google Network Connectivity Center, and data-residency designs where *where data may travel* is the core requirement.

---

## Overview

Two of these projects answer the same regulatory question from different angles: **how do you serve users globally while keeping regulated data inside one country?**

- **Zion** keeps syslog and personal data in Japan while hosting apps in seven regions.
- **Japan Medical** keeps patient records (PHI) in Tokyo while doctors in São Paulo (AWS) and New York (GCP) read and write them.

In both, the answer is private routing that auditors can follow: Transit Gateway peering and HA VPN with BGP, never the public internet and never a replica abroad.

---

## Architecture themes

- **Transit Gateway over VPC peering.** Traffic paths are centralized and auditable, and they create a visible "data corridor" for compliance review.
- **BGP everywhere it matters.** Dynamic route exchange and automatic tunnel failover across AWS ↔ GCP and GCP ↔ GCP.
- **Modules instead of copy-paste.** Seven region stacks became one `regional-network` + `regional-site` pair driven by a `locals.sites` map.
- **Keyless identity.** GCP Terraform runs via service-account impersonation, never downloaded JSON keys.

---

## Featured projects

### [Zion — Multi-Region Transit Gateway](../architectures/transit-gateway/README.md)

Seven-city AWS footprint with Route 53 geolocation DNS and a Transit Gateway mesh into Tokyo. Durable syslog lands in Aurora in Japan only. Optional self-hosted Prometheus + Grafana + Loki ships its data over the same TGW paths.

`Terraform modules` `Transit Gateway` `Route 53 geo` `Aurora` `VPC endpoints` `Grafana / Loki`
→ **Repository:** [jastek69/tfe-zion-armageddon-bhoejm](https://github.com/jastek69/tfe-zion-armageddon-bhoejm)

### [Japan Medical — APPI Cross-Cloud](../architectures/healthcare-cross-platform/README.md)

PHI stored only in Tokyo RDS. São Paulo (AWS) and New York (GCP) run stateless compute over TGW peering and HA VPN with BGP and tunnel rotation. CloudFront is the single global URL. CloudWatch alarms feed a Bedrock auto-incident-report pipeline.

`Terraform` `Transit Gateway` `GCP HA VPN` `CloudFront` `RDS` `Secrets Manager rotation` `Bedrock`
→ **Repository:** [jastek69/Armageddon-C7-LAB4-SEIR](https://github.com/jastek69/Armageddon-C7-LAB4-SEIR) 🔒

---

## Supporting projects

### [GCP HA VPN Hub-and-Spoke](../architectures/gcp-hub-spoke/README.md) · *team project*

A six-project GCP mesh across four continents: HA VPN + BGP between spokes, Network Connectivity Center hubs, and bootstrap/infra separation with keyless service-account impersonation.

`Terraform` `GCP HA VPN` `Cloud Router` `Network Connectivity Center` `IAM custom roles`
→ **Repository:** [jastek69/gcp-ha-vpn-hub-spokes-SA-scaffolding](https://github.com/jastek69/gcp-ha-vpn-hub-spokes-SA-scaffolding)

### [AWS ↔ GCP HA VPN with BGP](../architectures/aws-gcp-ha-vpn/README.md) · *team project*

Four-tunnel HA VPN between an AWS VGW and a GCP Cloud Router, with BGP route exchange and a documented troubleshooting guide.
