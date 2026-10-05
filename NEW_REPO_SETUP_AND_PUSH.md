# Create a New GitHub Repository and Push QuakeMesh Safely

These instructions assume you extracted the project and have already run the local validation.

## 1. Open PowerShell at the repository root

Example:

```powershell
cd "C:\Users\kasin\Projects\QuakeMesh"
```

Confirm you are in the correct directory:

```powershell
Get-ChildItem README.md, src, aws, android, docs
```

## 2. Run the pre-push security checks first

```powershell
.\.venv\Scripts\python.exe scripts\check_secrets.py
.\.venv\Scripts\python.exe -m pytest -q
```

The secret scan must say `clean`.

Also check for generated files yourself:

```powershell
Get-ChildItem -Recurse -Force |
  Where-Object {
    $_.Name -match 'private\.pem\.key|google-services\.json|runtime-config\.json|local\.properties'
  } |
  Select-Object FullName
```

Files under `artifacts/` may legitimately exist locally, but they must remain ignored.

## 3. Initialize Git

```powershell
git init
git branch -M main
```

Set identity if your machine does not already have it:

```powershell
git config user.name "Kasinath C A"
git config user.email "YOUR_GITHUB_EMAIL"
```

Use the email associated with the GitHub account you intend to push from.

## 4. Confirm ignore rules before staging

```powershell
git status --short
```

You should **not** see generated private certificates/keys, `artifacts/runtime-config.json`, Android `local.properties`, or `android/app/google-services.json` staged as normal project files.

A useful extra check:

```powershell
git check-ignore -v artifacts\runtime-config.json
```

If the file exists, Git should show the `.gitignore` rule responsible for ignoring it.

## 5. Stage and inspect

```powershell
git add .
git status
```

Before committing, inspect suspicious file extensions:

```powershell
git diff --cached --name-only |
  Select-String "\.(pem|key|p12|pfx|crt|db|zip)$|google-services\.json|local\.properties|runtime-config\.json"
```

The command should print nothing sensitive.

## 6. First commit

```powershell
git commit -m "Initial QuakeMesh V1 implementation"
```

## 7A. Create the repository using GitHub website

If GitHub CLI is not installed, this is simplest.

1. Sign in to GitHub.
2. Choose **New repository**.
3. Repository name: for example `quakemesh` or `quakemesh-cloud`.
4. Choose private/public as required by your course.
5. **Do not initialize** the GitHub repository with README, `.gitignore`, or license because this local repository already has them.
6. Create repository.
7. Copy the HTTPS remote URL GitHub displays.

Then in PowerShell:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Authenticate using GitHub’s supported browser/credential-manager flow if prompted. Do not put a personal access token inside project files.

## 7B. Alternative: GitHub CLI

If `gh` is installed and authenticated:

```powershell
gh auth status
gh repo create quakemesh --private --source . --remote origin --push
```

Replace `--private` with `--public` only if you intentionally want a public repository.

## 8. Verify the remote

```powershell
git remote -v
git status
git log --oneline -5
```

`git status` should show a clean working tree after the first push.

## 9. Final web check

Open the GitHub repository and verify:

- README renders;
- `docs/` is present;
- source/infrastructure/test directories are present;
- no `artifacts/iot-devices` private keys are visible;
- no `google-services.json`;
- no Android `local.properties`;
- no runtime API-key JSON;
- no accidental database files.

## 10. Normal future workflow

Before each push:

```powershell
.\scripts\validate.ps1
git status
git add .
git diff --cached --stat
git commit -m "Describe the change"
git push
```

## If a secret is accidentally committed

Do not merely delete the file in a later commit. Treat the credential as exposed:

- deactivate/delete the AWS IoT certificate if its private key was committed;
- rotate any AWS access key/API credential that was committed;
- rotate Firebase/service-account credentials if exposed;
- remove the secret from Git history using an appropriate history-rewrite tool;
- force-push only after understanding the effect on collaborators.

The safest approach is to run the included secret scan before every commit/push.
