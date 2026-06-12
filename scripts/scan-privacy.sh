#!/bin/bash
# Privacy scan script - runs before git commit to block sensitive data

set -e

# Get staged files from args or auto-detect. In CI there are no staged files,
# so fall back to scanning tracked files.
if [ $# -gt 0 ]; then
    files="$@"
else
    files=$(git diff --cached --name-only --diff-filter=ACM)
    if [ -z "$files" ]; then
        files=$(git ls-files)
    fi
fi

if [ -z "$files" ]; then
    exit 0
fi

# Files that intentionally document the blocked patterns.
filtered_files=""
for file in $files; do
    case "$file" in
        docs/privacy.md|scripts/scan-privacy.sh)
            continue
            ;;
        *)
            filtered_files="$filtered_files $file"
            ;;
    esac
done
files="$filtered_files"

if [ -z "$files" ]; then
    exit 0
fi

# Patterns to detect
patterns=(
    # Private IPv4 ranges. Require full dotted quads so timestamps like
    # 19:06:10.358137Z do not match the 10/8 rule.
    '(^|[^0-9])(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)'
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
