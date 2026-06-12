#!/bin/bash
# Privacy scan script - runs before git commit to block sensitive data

set -e

# Get staged files from args or auto-detect
if [ $# -gt 0 ]; then
    files="$@"
else
    files=$(git diff --cached --name-only --diff-filter=ACM)
fi

if [ -z "$files" ]; then
    exit 0
fi

# Patterns to detect
patterns=(
    # Private IPs
    '192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.'
    # Tokens and keys
    'github_pat_|ghp_|BEGIN .*PRIVATE KEY|----BEGIN.*PRIVATE KEY----'
    # Machine paths
    '/home/|/Users/|C:\\Users\\'
    # Hostnames
    'Tailscale|desktop-|[a-z]+-[a-z0-9]+\.(ts|tail)'
    # API keys
    'OPENAI_|ANTHROPIC_|DEEPSEEK_|XAI_|AWS_'
)

found=0
for pattern in "${patterns[@]}"; do
    match=$(echo "$files" | xargs grep -Hn -E "$pattern" 2>/dev/null || true)
    if [ -n "$match" ]; then
        echo "BLOCKED: $pattern"
        echo "$match"
        found=1
    fi
done

if [ $found -eq 1 ]; then
    exit 1
fi

exit 0
