#!/bin/bash

# Ensure commit message is provided
if [ -z "$1" ]; then
    echo "❌ Error: Commit message is required."
    echo "Usage: ./secure_push.sh \"Your commit message here\""
    exit 1
fi

COMMIT_MSG=$1

# Ensure git remote is configured
REMOTE_URL=$(git config --get remote.origin.url)
if [ -z "$REMOTE_URL" ]; then
    echo "⚠️  Remote repository not configured."
    echo "Configuring remote: https://github.com/haadrehman/Secure-Vault-Agent.git"
    git remote add origin https://github.com/haadrehman/Secure-Vault-Agent.git
fi

# Stage all modifications
git add .

echo "🔍 Running Semgrep Security Scan..."
uv run semgrep scan --config=.semgrep.yaml --error
SEMGREP_EXIT=$?

if [ $SEMGREP_EXIT -ne 0 ]; then
    echo -e "\n❌ [ERROR] Semgrep scan failed! Vulnerabilities detected."
    echo "Reverting staged files to keep the remote clean..."
    git reset
    exit 1
fi

echo "🧪 Running Pytest Suite..."
uv run pytest
PYTEST_EXIT=$?

if [ $PYTEST_EXIT -ne 0 ]; then
    echo -e "\n❌ [ERROR] Pytest execution failed!"
    echo "Reverting staged files to keep the remote clean..."
    git reset
    exit 1
fi

echo "✅ All local security and testing checks passed."
echo "📦 Executing Git Commit..."
# The pre-commit hook will run again, but since we already verified locally, it should pass.
git commit -m "$COMMIT_MSG"

if [ $? -ne 0 ]; then
    echo "❌ [ERROR] Git commit failed (possibly due to pre-commit hook)."
    exit 1
fi

# Determine current branch
CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    # Default to main if on detached head or new repo
    CURRENT_BRANCH="main"
    git branch -M main
fi

echo "🚀 Pushing to remote GitHub repository ($CURRENT_BRANCH)..."
git push -u origin "$CURRENT_BRANCH"

if [ $? -eq 0 ]; then
    echo "🎉 Code successfully and securely pushed to GitHub!"
else
    echo "❌ [ERROR] Git push failed. Please check your network and credentials."
fi
