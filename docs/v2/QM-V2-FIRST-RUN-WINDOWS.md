# Windows first run

From a normal PowerShell terminal in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

The script detects Python, Git, Node/npm, AWS CLI, and Java before changing anything. Python 3.12 is preferred for parity with Lambda. It creates or repairs the project `.venv` and installs pinned Python requirements. If a prerequisite is missing, either install it from its official publisher or explicitly run:

```powershell
.\scripts\setup_windows.ps1 -InstallMissing
```

That switch uses exact `winget` package IDs for Python 3.12, Git, Node LTS, and AWS CLI, then asks for a fresh terminal. It does not install Android Studio or multi-gigabyte SDK components.

For Android, install Android Studio from the official Android developer site, select its bundled JDK 17 where compatible, install the SDK level declared by `android/app/build.gradle.kts`, copy `android/local.properties.example` to the ignored `android/local.properties`, and let Android Studio write `sdk.dir`. Firebase setup is separate and optional for non-FCM work.

Validation:

```powershell
.\scripts\validate.ps1
```

`SKIPPED` means a prerequisite was unavailable; it is not a pass. If `.venv` refers to a removed Python installation, setup rebuilds that generated environment with the selected interpreter.
MSYS2 Python is reported as unsuitable because its virtual-environment layout is not compatible with the repository's Windows launch scripts; install native Python 3.12 instead.
