#!/bin/bash

# GitHub Actions Setup Script
# This script helps you set up secrets for GitHub Actions

set -e

echo "🚀 GitHub Actions Setup for Sprint Planning Copilot"
echo "=================================================="
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if logged in
if ! gh auth status &> /dev/null; then
    echo "Please login to GitHub CLI:"
    gh auth login
fi

echo "✅ GitHub CLI is ready"
echo ""

# Get current repo
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "📦 Repository: $REPO"
echo ""

echo "Creating GitHub Secrets..."
echo "=========================="
echo ""

# 1. Azure Credentials
echo "1️⃣ Creating Service Principal for Azure..."
echo ""
echo "Run this command to create a service principal:"
echo ""
echo "az ad sp create-for-rbac \\"
echo "  --name \"github-actions-sprint-copilot\" \\"
echo "  --role contributor \\"
echo "  --scopes /subscriptions/\$(az account show --query id -o tsv)/resourceGroups/jira-copilot-rg \\"
echo "  --sdk-auth"
echo ""
read -p "Press Enter after you've run the command above..."
echo ""
echo "Copy the entire JSON output and paste it below:"
read -r AZURE_CREDENTIALS
gh secret set AZURE_CREDENTIALS --body "$AZURE_CREDENTIALS"
echo "✅ AZURE_CREDENTIALS set"
echo ""

# 2. Azure Subscription ID
echo "2️⃣ Setting Azure Subscription ID..."
AZURE_SUB_ID=$(az account show --query id -o tsv)
gh secret set AZURE_SUBSCRIPTION_ID --body "$AZURE_SUB_ID"
echo "✅ AZURE_SUBSCRIPTION_ID set: $AZURE_SUB_ID"
echo ""

# 3. ACR Name
echo "3️⃣ Setting ACR Name..."
gh secret set ACR_NAME --body "jiracopilotacr"
echo "✅ ACR_NAME set"
echo ""

# 4. ACR Username
echo "4️⃣ Setting ACR Username..."
gh secret set ACR_USERNAME --body "jiracopilotacr"
echo "✅ ACR_USERNAME set"
echo ""

# 5. ACR Password
echo "5️⃣ Getting ACR Password..."
ACR_PASSWORD=$(az acr credential show --name jiracopilotacr --query "passwords[0].value" -o tsv)
gh secret set ACR_PASSWORD --body "$ACR_PASSWORD"
echo "✅ ACR_PASSWORD set"
echo ""

# 6. Azure AD Client ID (Frontend)
echo "6️⃣ Setting Azure AD Frontend Client ID..."
gh secret set VITE_AZURE_AD_CLIENT_ID --body "380da0ea-a299-4224-a856-32e88192ccef"
echo "✅ VITE_AZURE_AD_CLIENT_ID set"
echo ""

# 7. Azure AD Tenant ID
echo "7️⃣ Setting Azure AD Tenant ID..."
gh secret set VITE_AZURE_AD_TENANT_ID --body "70a47f1e-56e9-4450-8c04-30bf8e62c3e5"
echo "✅ VITE_AZURE_AD_TENANT_ID set"
echo ""

# 8. Azure AD Scopes
echo "8️⃣ Setting Azure AD Scopes..."
gh secret set VITE_AZURE_AD_SCOPES --body "api://20f2b27b-e2cd-41e7-a193-6b26740c5b53/api.access"
echo "✅ VITE_AZURE_AD_SCOPES set"
echo ""

echo "=================================================="
echo "✅ All secrets configured successfully!"
echo ""
echo "Next steps:"
echo "1. Commit the workflow files:"
echo "   git add .github/workflows/"
echo "   git commit -m \"Add GitHub Actions workflows\""
echo "   git push"
echo ""
echo "2. Make a small change to test:"
echo "   - Edit a file in frontend/ or backend/"
echo "   - Commit and push"
echo "   - Check Actions tab on GitHub"
echo ""
echo "3. View your workflows at:"
echo "   https://github.com/$REPO/actions"
echo ""
