# Privacy Policy

## Overview

This is a public demo repository. The project demonstrates durable agent state management.

## What We Collect

This repository does not collect any user data. As a public demo project, it contains only example code and documentation.

## What We DON'T Collect

No private user data is collected, stored, or processed by this project.

## CI/CD Scanning

This repository uses automated CI/CD privacy scanning to prevent accidental commits of sensitive data. The scan blocks commits containing:

- **Private IP addresses**: 192.168.x.x, 10.x.x.x, 172.16–31.x.x
- **Tokens**: github_pat_, ghp_, aws_, OPENAI_, ANTHROPIC_
- **Private key markers**: BEGIN PRIVATE KEY
- **Machine paths**: /home/, C:\Users\
- **Tailscale hostnames**: Tailscale, desktop-, *.ts, *.tail

## Reporting

If you believe private data has been accidentally committed, please open an issue and we will address it promptly.
