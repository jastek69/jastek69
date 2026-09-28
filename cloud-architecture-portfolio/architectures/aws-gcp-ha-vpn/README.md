# AWS ↔ GCP Highly Available (HA) VPN Tunnel w/ BGP Configuration

![VPN Topology Diagram](/Screenshots/diagram.jpg)

![Badges](https://img.shields.io/badge/Cloud-AWS-blue?logo=amazon-aws)
![Badges](https://img.shields.io/badge/Cloud-GCP-red?logo=google-cloud)
![Badges](https://img.shields.io/badge/VPN-HA-green)
![Badges](https://img.shields.io/badge/Routing-BGP-informational)

This guide walks you through the complete deployment of a high-availability VPN tunnel between AWS and GCP using Terraform, leveraging Border Gateway Protocol (BGP) for dynamic route exchange, automatic failover, and multi-cloud scalability. By enabling BGP, the VPN connection becomes more resilient, adaptable, and easier to maintain—ensuring seamless traffic routing even in the face of tunnel outages or network changes.

---

## 📚 References

- [RFC 4271 – BGP-4](https://datatracker.ietf.org/doc/html/rfc4271)
- [GCP HA VPN with AWS Tutorial](https://cloud.google.com/network-connectivity/docs/vpn/tutorials/create-ha-vpn-connections-google-cloud-aws)

---

## 📁 Project Structure

```plaintext
├── Screenshots/
│   ├── aws-customer-gw-results.jpg
│   ├── aws-virtual-pgw-results.jpg
│   ├── aws-vpn-connection1-complete.jpg
│   ├── aws-vpn-connection1-first-section.jpg
│   ├── aws-vpn-connection1-last-section.jpg
│   ├── aws-vpn-connection1-tunnel1-section1.jpg
│   ├── aws-vpn-connection1-tunnel1-section2.jpg
│   ├── aws-vpn-connection1-tunnel1-section3.jpg
│   ├── aws-vpn-connection1-tunnel1-section4.jpg
│   ├── aws-vpn-connection1-tunnel2-section1.jpg
│   ├── aws-vpn-connection2-complete.jpg
│   ├── aws-vpn-connection2-first-section.jpg
│   ├── aws-vpn-connection2-last-section.jpg
│   ├── aws-vpn-connection2-tunnel3-section1.jpg
│   ├── aws-vpn-connection2-tunnel4-section1.jpg
│   ├── diagram.jpg
│   ├── gcp-bgp-tunnel1-complete.jpg
│   ├── gcp-bgp-tunnel1-section1.jpg
│   ├── gcp-bgp-tunnel1-section2.jpg
│   ├── gcp-bgp-tunnel2-complete.jpg
│   ├── gcp-bgp-tunnel2-section1.jpg
│   ├── gcp-bgp-tunnel2-section2.jpg
│   ├── gcp-bgp-tunnel3-complete.jpg
│   ├── gcp-bgp-tunnel3-section1.jpg
│   ├── gcp-bgp-tunnel3-section2.jpg
│   ├── gcp-bgp-tunnel4-complete.jpg
│   ├── gcp-bgp-tunnel4-section1.jpg
│   ├── gcp-bgp-tunnel4-section2.jpg
│   ├── gcp-cloud-router-build.jpg
│   ├── gcp-cloud-router-complete.jpg
│   ├── gcp-cloud-router-selection.jpg
│   ├── gcp-cloud-vpn-gateways.jpg
│   ├── gcp-cloud-vpn-tunnels.jpg
│   ├── gcp-ha-availability.jpg
│   ├── gcp-ha-vpn-gw.jpg
│   ├── gcp-peer-vpn-gateways.jpg
│   ├── gcp-peer-vpn-gw1.jpg
│   ├── gcp-peer-vpn-gw2.jpg
│   ├── gcp-vpn-tunnel-1.jpg
│   ├── gcp-vpn-tunnel-2.jpg
│   ├── gcp-vpn-tunnel-3.jpg
│   ├── gcp-vpn-tunnel-4.jpg
│   ├── gcp-vpn-tunnels-complete.jpg
│   ├── PSK.png
│   ├── teardown-aws-cgw-results.jpg
│   ├── teardown-aws-vpgw-results.jpg
│   └── teardown-aws-vpn-connections-results.jpg
├── .gitignore
├── 1-authentication.tf
├── 2-backend.tf
├── 3-variables.tf
├── 4-aws-vpn-connections.tf
├── 5-gcp-vpn-connections.tf
├── AWS-to-GCP BGP Configuration Template.txt
├── README.md
├── USER_GUIDE.md
```

---

## 🛠️ Terraform Configuration

### 🔑 `1-authentication.tf`

Handles provider authentication for both AWS and GCP.

- Uses environment variables or credentials file
- Includes provider blocks for `aws` and `google`

### ☁️ `2-backend.tf`

Sets up remote backend storage for Terraform state (e.g., GCS or S3).

- Configure appropriately to avoid state loss

### 🧮 `3-variables.tf`

Defines input variables for reusable deployment:

- VPC IDs
- Subnet CIDRs
- Tunnel CIDRs
- ASNs
- Region variables

### 🏗️ `4-aws-vpn-connections.tf`

Deploys the following AWS infrastructure:

- Customer Gateways (CGWs)
- Virtual Private Gateways (VGWs)
- Site-to-Site VPN connections (with BGP and logging)

### 🌐 `5-gcp-vpn-connections.tf`

Creates GCP resources required for HA VPN setup:

- Cloud Router
- HA VPN Gateway
- Peer VPN Gateway
- Tunnel interfaces
- BGP sessions

---

## 📋 Configuration Template (Preview)

The `AWS-to-GCP BGP Configuration Template.txt` file outlines:

- Pre-shared Key assignments
- ASN values for AWS and GCP
- Tunnel BGP IP mappings
- Placeholder sections for AWS/GCP public IP interfaces

**Example BGP Tunnels:**

```plaintext
Network 1:
  BGP Identifier:          169.254.0.8/30
  AWS Tunnel 1:            169.254.0.9
  GCP Tunnel 1:            169.254.0.10
  BGP Broadcast:           169.254.0.11

Network 2:
  BGP Identifier:          169.254.0.12/30
  AWS Tunnel 2:            169.254.0.13
  GCP Tunnel 2:            169.254.0.14
  BGP Broadcast:           169.254.0.15

Network 3:
  BGP Identifier:          169.254.0.16/30
  AWS Tunnel 2:            169.254.0.17
  GCP Tunnel 2:            169.254.0.18
  BGP Broadcast:           169.254.0.19

Network 4:
  BGP Identifier:          169.254.0.20/30
  AWS Tunnel 2:            169.254.0.21
  GCP Tunnel 2:            169.254.0.22
  BGP Broadcast:           169.254.0.23
```

You must update this file with actual interface IPs after tunnel provisioning.

---

## 🚀 Deployment Instructions

1. Generate Pre-shared Keys (PSK's) at [https://pskgen.com](https://pskgen.com)
   - Extract four (4) PSK's that will be used for the tunnels.
2. Customize `1-authentication.tf`, `2-backend.tf`, and `3-variables.tf` with your JSON credentials, bucket name, state file name, provider regions, provider zones, and IP configuration.
3. Run Terraform:

   ```bash
   terraform init
   terraform fmt
   terraform validate
   terraform plan
   terraform apply -auto-approve
   ```

---

## ✅ Post-Deployment Validation

- Validate VPN tunnel and BGP session status via:
  - AWS Console → VPN → Site-to-Site VPN Connections → `aws-to-gcp-vpn1` → Tunnel Details
  ![AWS VPN Connection 1](/Screenshots/aws-vpn-connection1-complete.jpg)
  - AWS Console → VPN → Site-to-Site VPN Connections → `aws-to-gcp-vpn2` → Tunnel Details
  ![AWS VPN Connection 2](/Screenshots/aws-vpn-connection2-complete.jpg)
  - GCP Console → VPN → Cloud VPN Tunnel Status
  ![GCP Cloud VPN Tunnels](/Screenshots/gcp-cloud-vpn-tunnels.jpg)

---

## 🧹 Teardown

Use Terraform to destroy the setup:

```bash
terraform destroy -auto-approve
```

---

## 🛠️ Troubleshooting

### 🔴 Tunnel Status Shows “DOWN” (AWS or GCP)

- ✅ **Check PSK Mismatch**: Ensure the pre-shared keys used in both AWS and GCP match exactly for each tunnel.
- ✅ **Validate IKE Versions**: Both sides must use IKEv2. AWS defaults to IKEv1 if not explicitly configured via API or Console.
- ✅ **Firewall Rules**:
  - **GCP**: Ensure TCP/UDP ports **500** and **4500** are allowed.
  - **AWS**: Review security groups and NACL settings for VGW-attached subnets.
- ✅ **Interface IP Misconfiguration**: Verify that tunnel inside IPs (169.254.x.x/30) match between AWS and GCP configurations.

### 🔴 BGP Sessions Not Establishing

- ✅ **ASN Mismatch**: AWS VGW should use ASN `65501`; GCP Cloud Router should use `65515`.
- ✅ **Incorrect BGP Peer IPs**: Double-check that each tunnel has the correct GCP and AWS BGP IPs as defined in your configuration template.
- ✅ **Route Advertisements**:
  - Ensure GCP Cloud Router is set to “Advertise all subnets.”
  - Confirm AWS VPN connection routing type is set to **Dynamic (BGP)**.

### ⚠️ Terraform Apply Errors

- ✅ **Credentials Misconfigured**:
  - Make sure AWS and GCP provider blocks are using valid credentials and configured correctly in `1-authentication.tf`.
- ✅ **API Enablement on GCP**:
  - Enable required APIs:
    - `compute.googleapis.com`
    - `networkconnectivity.googleapis.com`
- ✅ **Resource Naming Conflicts**:
  - Ensure VPNs, CGWs, and VGWs have unique names to avoid duplication errors.

### 🟡 VPN Tunnel Flaps (Intermittent Disconnects)

- ✅ **Check Dead Peer Detection (DPD)**:
  - Verify DPD timeout and action settings are consistent across AWS and GCP.
- ✅ **Review Logs**:
  - Use **AWS CloudWatch Logs** and **GCP Cloud Logging** to look for tunnel negotiation or BGP session failures.
- ✅ **Monitor Tunnel Health**:
  - Use metrics and monitoring dashboards to track latency, jitter, and tunnel uptime trends.

### 🧪 Useful Commands

```bash
# AWS - Check VPN telemetry (tunnel status)
aws ec2 describe-vpn-connections --query "VpnConnections[*].VgwTelemetry"

# GCP - Check router BGP session status
gcloud compute routers get-status gcp-to-aws-cloud-router --region=southamerica-east1
```

---

## ✍️ Authors & Acknowledgments

- **Author:** T.I.Q.S.
- **Group Leader:** John Sweeney

### 🙏 Inspiration

This project was built with inspiration, mentorship, and guidance from:

- Sensei **"Darth Malgus" Theo**
- Lord **Beron**
- Sir **Rob**
- Jedi Master **Derrick**

Their wisdom, vision, and unwavering discipline made this mission possible.

---
