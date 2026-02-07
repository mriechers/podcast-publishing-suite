# GitHub Organization Handoff Guide

## Overview

This document outlines the process for transferring this repository from a personal/contractor account to a client-owned GitHub organization, ensuring clean ownership, ongoing access for contractors, and professional project management.

**Use Case:** Contractor builds project → Client owns organization → Contractor maintains access

**Benefits:**
- ✅ Client has full ownership and control
- ✅ Contractor retains necessary access during active work
- ✅ Easy to add future contractors or team members
- ✅ Professional appearance
- ✅ Clear separation of client vs. contractor work

---

## Prerequisites

**What You'll Need:**
- [ ] Client has a GitHub account (free or paid)
- [ ] Repository is in good state (code reviewed, documented)
- [ ] All secrets/credentials removed from code
- [ ] `.gitignore` properly configured
- [ ] README updated with project-specific information

**Estimated Time:** 30-45 minutes

---

## Phase 1: Create GitHub Organization

### Step 1: Client Creates Organization

**Who:** Client
**Time:** 5 minutes

1. **Navigate to GitHub Organizations**
   - Go to [github.com](https://github.com)
   - Click profile picture (top right) → "Your organizations"
   - Click "New organization"

2. **Choose Plan**
   - **Free Plan** (recommended for most projects)
     - Unlimited public repositories
     - Unlimited private repositories
     - 2,000 Actions minutes/month
     - 500 MB Packages storage
     - Community support

   - **Team Plan** ($4/user/month)
     - Everything in Free
     - Protected branches
     - Code owners
     - Draft pull requests
     - Team discussions
     - Email support

   **Recommendation for This Project:** Free plan is sufficient

3. **Organization Setup**
   ```
   Organization name: [client-name]-media
                      (or: [podcast-name], [brand-name], etc.)

   Contact email: client@example.com

   This organization belongs to: My personal account
   ```

4. **Add Organization Details**
   - Display name: "[Client Name] Media" or "[Podcast Name]"
   - Description: "Podcast publishing automation and web presence"
   - Website: (podcast website URL)
   - Location: (optional)

5. **Complete Setup**
   - Skip team invitations for now
   - Click "Complete setup"

**Result:** Organization is now created at `github.com/[org-name]`

---

### Step 2: Configure Organization Settings

**Who:** Client
**Time:** 10 minutes

1. **Navigate to Organization Settings**
   - Click organization avatar → Settings

2. **Configure Member Privileges**
   - Settings → Member privileges

   **Recommended Settings:**
   ```
   Base permissions: Read
   ├─ Members can create repositories: Yes
   ├─ Repository creation: Both public and private
   └─ Admin repository permissions: Enabled

   Repository forking: Enabled for private repos
   Pages creation: Enabled
   ```

3. **Configure Actions Settings**
   - Settings → Actions → General

   ```
   Actions permissions: Allow all actions and reusable workflows
   Workflow permissions: Read and write permissions
   Allow GitHub Actions to create and approve pull requests: Enabled
   ```

4. **Set Up GitHub Pages (Optional)**
   - If you'll host documentation on GitHub Pages
   - Settings → Pages
   - Enable Pages for organization

**Result:** Organization configured for collaborative development

---

## Phase 2: Transfer Repository

### Step 3: Prepare Repository for Transfer

**Who:** Contractor
**Time:** 10 minutes

1. **Audit Repository Contents**

   ```bash
   # Check for sensitive data
   git log --all --full-history --source --grep="password\|secret\|key\|token" -i

   # Check current files
   git ls-files | grep -E "\.(env|pem|key|cert)$"
   ```

2. **Clean Up Secrets** (if any found)

   ```bash
   # Remove from history if needed (DESTRUCTIVE - use with care)
   # Only if secrets were committed
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/secret/file" \
     --prune-empty --tag-name-filter cat -- --all

   # Force push (only if you cleaned history)
   git push --force --all
   ```

3. **Update README**

   Edit `README.md` to include:
   ```markdown
   # [Project Name]

   Automated podcast episode publishing from PRX Dovetail to Ghost CMS.

   ## Project Status

   - **Client:** [Client Name]
   - **Maintained by:** [Your Name/Company]
   - **Repository:** github.com/[org-name]/prx-to-ghost-publisher

   ## Quick Links

   - [Setup Documentation](docs/)
   - [Automation Design](docs/AUTOMATION_DESIGN.md)
   - [GitHub Organization Handoff](docs/GITHUB_ORG_HANDOFF.md)

   ## Contributors

   - [Your Name] ([@your-github-username](https://github.com/your-github-username)) - Initial development
   ```

4. **Verify `.gitignore`**

   Ensure `.gitignore` includes:
   ```gitignore
   # Secrets
   .env
   .env.local
   *.pem
   *.key
   secrets/

   # Python
   .venv*/
   __pycache__/

   # IDE
   .vscode/
   .idea/

   # OS
   .DS_Store
   ```

5. **Final Commit**

   ```bash
   git add README.md .gitignore
   git commit -m "docs: prepare repository for organization transfer"
   git push
   ```

**Result:** Repository is clean and ready for transfer

---

### Step 4: Transfer Repository Ownership

**Who:** Contractor (initiates) → Client (accepts)
**Time:** 5 minutes

1. **Initiate Transfer** (Contractor)

   - Navigate to repository: `github.com/[your-username]/prx-to-ghost-publisher`
   - Settings → scroll to "Danger Zone"
   - Click "Transfer ownership"

   ```
   New owner's GitHub username or organization name:
   [client-org-name]

   Type the repository name to confirm:
   prx-to-ghost-publisher
   ```

   - Click "I understand, transfer this repository"

2. **Accept Transfer** (Client)

   - Client receives email: "You've been invited to transfer a repository"
   - Click link in email or go to organization → Repositories
   - Click "Accept transfer"
   - Confirm transfer

3. **Verify Transfer**

   Both parties should verify:
   ```
   Old URL: github.com/[contractor-username]/prx-to-ghost-publisher
   New URL: github.com/[client-org]/prx-to-ghost-publisher

   GitHub automatically sets up redirect from old → new
   ```

**Result:** Repository now owned by client organization

---

## Phase 3: Set Up Team Access

### Step 5: Create Teams

**Who:** Client
**Time:** 5 minutes

1. **Navigate to Teams**
   - Organization page → Teams tab
   - Click "New team"

2. **Create "Maintainers" Team**

   ```
   Team name: Maintainers
   Description: Active contractors and developers

   Team visibility: Visible (recommended) or Secret

   Team notifications: Enabled
   ```

3. **Create "Administrators" Team** (Optional)

   ```
   Team name: Administrators
   Description: Organization owners and leads

   Team visibility: Visible
   ```

**Result:** Teams created for organizing access

---

### Step 6: Add Contractor to Team

**Who:** Client
**Time:** 3 minutes

1. **Invite Contractor**

   - Teams → Maintainers → Members
   - Click "Add a member"
   - Enter contractor's GitHub username: `@contractor-username`
   - Click "Invite"

2. **Contractor Accepts Invite**

   - Contractor receives email
   - Click "Join [org-name]"
   - Accept invitation

3. **Grant Team Repository Access**

   - Organization → Repositories
   - Click repository name
   - Settings → Manage access
   - Click "Add teams"
   - Select "Maintainers" team
   - Choose role: **"Maintain"** or **"Admin"**

   **Permission Levels:**
   ```
   Read      - Can view code, open issues
   Triage    - Can manage issues/PRs (no code write)
   Write     - Can push code, manage issues/PRs
   Maintain  - Can manage repo settings (no destructive actions)
   Admin     - Full access including deletion
   ```

   **Recommended for Contractor:** **Maintain** (during active work) or **Write** (for code-only work)

**Result:** Contractor has appropriate access to continue work

---

## Phase 4: Configure Repository Settings

### Step 7: Update Repository Settings

**Who:** Client (or Contractor with Admin access)
**Time:** 5 minutes

1. **Update Repository Details**

   - Repository → Settings → General

   ```
   Description: Automated publishing of podcast episodes from PRX to Ghost
   Website: [podcast or client website URL]
   Topics: podcast, automation, ghost-cms, prx, github-actions
   ```

2. **Configure Branch Protection** (Recommended)

   - Settings → Branches
   - Click "Add branch protection rule"

   ```
   Branch name pattern: main

   Protect matching branches:
   ☑ Require a pull request before merging
   ☑ Require approvals: 1
   ☑ Dismiss stale pull request approvals when new commits are pushed
   ☐ Require review from Code Owners (optional)
   ☑ Require status checks to pass before merging (if tests exist)
   ☐ Require branches to be up to date before merging
   ☐ Require conversation resolution before merging
   ☐ Require signed commits (optional)
   ☑ Include administrators (recommended for safety)
   ```

   **For Solo Contractor:** Can disable PR requirements during active development

3. **Update GitHub Actions Secrets**

   - Settings → Secrets and variables → Actions
   - Ensure these secrets exist (add if missing):

   ```
   GHOST_URL              - https://yourblog.ghost.io
   GHOST_ADMIN_KEY        - [from Ghost admin → Integrations]
   PRX_FEED_URL           - https://f.prxu.org/3329/feed-rss.xml
   RSS2JSON_API_KEY       - [if using RSS proxy, optional]
   ```

4. **Enable GitHub Actions**

   - Settings → Actions → General
   - Workflow permissions: **Read and write permissions**
   - Allow GitHub Actions to create and approve pull requests: **Enabled**

**Result:** Repository properly configured for development and automation

---

## Phase 5: Update Local Development

### Step 8: Update Local Git Remote

**Who:** Contractor
**Time:** 2 minutes

1. **Update Remote URL**

   ```bash
   cd prx-to-ghost-publisher

   # View current remote
   git remote -v
   # origin  https://github.com/[old-owner]/prx-to-ghost-publisher (fetch)
   # origin  https://github.com/[old-owner]/prx-to-ghost-publisher (push)

   # Update to new organization URL
   git remote set-url origin https://github.com/[client-org]/prx-to-ghost-publisher.git

   # Verify
   git remote -v
   # origin  https://github.com/[client-org]/prx-to-ghost-publisher (fetch)
   # origin  https://github.com/[client-org]/prx-to-ghost-publisher (push)
   ```

2. **Test Access**

   ```bash
   # Fetch to verify access
   git fetch origin

   # Should succeed if permissions are correct
   ```

3. **Update Documentation References** (if needed)

   ```bash
   # Find any hardcoded references to old repo URL
   grep -r "github.com/[old-owner]" .

   # Update as needed
   ```

**Result:** Local repository connected to new organization

---

## Phase 6: Post-Transfer Verification

### Step 9: Verification Checklist

**Who:** Both Client and Contractor
**Time:** 5 minutes

- [ ] Repository visible at new URL: `github.com/[client-org]/prx-to-ghost-publisher`
- [ ] GitHub automatically redirects old URL → new URL
- [ ] Contractor is member of organization
- [ ] Contractor is member of Maintainers team
- [ ] Contractor has Maintain or Admin access to repository
- [ ] All secrets are configured in new repository
- [ ] GitHub Actions workflows are enabled
- [ ] Branch protection rules are set (if desired)
- [ ] README reflects new ownership
- [ ] Local development environment works with new remote
- [ ] CI/CD pipeline works (test a push or manual workflow run)

**Test GitHub Actions:**
```bash
# Trigger a workflow manually
# Go to: Actions → [workflow name] → Run workflow
```

**Result:** Transfer complete and verified

---

## Ongoing Management

### Team Member Management

**Adding Future Contractors:**
1. Client → Organization → People → Invite member
2. Enter GitHub username or email
3. Choose role: Member (not Owner)
4. Add to "Maintainers" team
5. They get access to repository via team

**Changing Contractor Permissions:**
```
During active development: Admin or Maintain
After project handoff:     Write or Read
After contract ends:       Remove from organization
```

**Removing Access:**
1. Organization → People
2. Find user → Gear icon → Remove from organization
3. Confirms removal from all teams and repositories

---

### Repository Permissions Reference

| Role | Can Do | Use Case |
|------|--------|----------|
| **Read** | View code, clone, open issues | Client stakeholders, observers |
| **Triage** | Manage issues/PRs (no code) | Project managers, QA |
| **Write** | Push code, manage issues | Active developers |
| **Maintain** | Manage settings (not destructive) | Lead contractors, DevOps |
| **Admin** | Full control including deletion | Organization owners only |

**Recommended Access Levels:**
- **Client Owner:** Admin (always)
- **Active Contractor:** Maintain or Write
- **Former Contractor:** Remove or Read (for reference)
- **Future Contractors:** Write or Maintain

---

## Cost Implications

### GitHub Organization Costs

**Free Plan:**
- ✅ Unlimited public repositories
- ✅ Unlimited private repositories
- ✅ Unlimited contributors
- ✅ 2,000 Actions minutes/month
- ✅ 500 MB Packages storage
- ✅ Community support

**Free Plan is Sufficient For:**
- This project (PRX-to-Ghost publisher)
- Small teams (<5 active developers)
- Standard automation workflows
- Most client projects

**Upgrade to Team ($4/user/month) If:**
- Need protected branches without workarounds
- Want code owners feature
- Need email support
- Team discussions desired
- Multiple private repos with many collaborators

**Current Project Usage Estimate:**
- Repositories: 1
- Active contributors: 1-2
- Actions usage: ~300 minutes/month (workflow runs)
- **Recommended:** Free plan ✅

---

## Troubleshooting

### Issue: Contractor Can't Access Repository After Transfer

**Solution:**
1. Client: Check organization → People → verify contractor is member
2. Client: Check Teams → Maintainers → verify contractor is in team
3. Client: Check repository → Settings → Manage access → verify team has access
4. Contractor: Check email for pending invitation
5. Contractor: Go to `github.com/[org-name]` → Accept invitation

### Issue: GitHub Actions Fail After Transfer

**Solution:**
1. Check Settings → Actions → General → Workflow permissions
2. Verify all secrets are configured in new repository
3. Re-run failed workflow
4. Check if branch protection rules block workflow commits

### Issue: Old Repository URL Still Shows

**Solution:**
- GitHub automatically redirects, this is normal
- Update local remotes: `git remote set-url origin [new-url]`
- Update documentation references
- Bookmarks will redirect automatically

### Issue: Can't Transfer Due to Existing Repository Name

**Solution:**
1. Client: Rename existing repository in organization first
2. Then retry transfer
3. Or: Use different repository name during transfer

---

## Handoff Completion Checklist

### Technical Handoff
- [ ] Repository transferred to client organization
- [ ] All secrets configured
- [ ] GitHub Actions working
- [ ] Documentation updated
- [ ] Local development verified
- [ ] CI/CD pipeline tested

### Access & Permissions
- [ ] Contractor added to organization
- [ ] Contractor added to appropriate team
- [ ] Contractor has correct repository access
- [ ] Client verified as organization owner
- [ ] Team structure documented

### Documentation
- [ ] README updated with ownership information
- [ ] This handoff guide reviewed
- [ ] Architecture documentation current
- [ ] Maintenance procedures documented
- [ ] Contact information updated

### Future Planning
- [ ] Ongoing access level agreed upon
- [ ] Offboarding process discussed
- [ ] Knowledge transfer completed
- [ ] Support expectations clarified

---

## Templates

### Email Template: Notify Client of Transfer Readiness

```
Subject: GitHub Repository Ready for Transfer

Hi [Client Name],

The prx-to-ghost-publisher repository is ready to be transferred to
your GitHub organization. Here's what we need to do:

1. You create a GitHub organization (if you don't have one)
   - Name suggestion: [client-name]-media
   - Use the free plan (sufficient for this project)
   - Guide: [link to this doc, Phase 1]

2. I'll transfer the repository to your organization
   - Takes about 5 minutes
   - No downtime

3. You'll add me to your organization as a Maintainer
   - This lets me continue working on the project
   - You can adjust my access level anytime

I've prepared a complete handoff guide:
[link to this document]

Let me know when you're ready to proceed, or if you have any questions!

Best,
[Your Name]
```

### Email Template: Request Organization Invite

```
Subject: Ready to Join [Org Name] on GitHub

Hi [Client Name],

The repository has been transferred successfully! I can see it at:
https://github.com/[org-name]/prx-to-ghost-publisher

To continue development, please add me to your organization:

1. Go to: https://github.com/orgs/[org-name]/people
2. Click "Invite member"
3. Enter my username: @[your-github-username]
4. Add me to the "Maintainers" team (or create one)

Once I accept the invitation, I'll verify everything works and
resume development.

Thanks!
[Your Name]
```

---

## Quick Reference: URL Changes

After transfer, all URLs change:

| Old URL | New URL |
|---------|---------|
| `github.com/[contractor]/prx-to-ghost-publisher` | `github.com/[org]/prx-to-ghost-publisher` |
| `github.com/[contractor]/prx-to-ghost-publisher/issues` | `github.com/[org]/prx-to-ghost-publisher/issues` |
| `github.com/[contractor]/prx-to-ghost-publisher/actions` | `github.com/[org]/prx-to-ghost-publisher/actions` |
| Settings location | Now under organization settings |

**Git Remote:**
```bash
# Before
git@github.com:[contractor]/prx-to-ghost-publisher.git

# After
git@github.com:[org]/prx-to-ghost-publisher.git
```

**Note:** GitHub automatically redirects old → new for 90+ days

---

## Next Steps After Handoff

1. **Contractor:** Update local environment and verify access
2. **Contractor:** Resume development work
3. **Client:** Familiarize with GitHub organization dashboard
4. **Client:** Add other team members if needed
5. **Both:** Schedule regular check-ins on project progress
6. **Both:** Review access levels before contract completion

---

**Document Version:** 1.0
**Last Updated:** 2025-11-14
**Estimated Handoff Time:** 45 minutes
**Difficulty:** Easy (step-by-step)
**Recommended Review:** Before starting handoff process
