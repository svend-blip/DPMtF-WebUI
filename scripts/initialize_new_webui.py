#!/usr/bin/env python3
"""Initialize a new DPMtF-governed WebUI project from skeleton templates.

Creates a complete, runnable WebUI project in ~2 minutes.
Uses skeleton files from DPMtF-WebUI/templates/new-webui-skeleton/.

Usage:
    python3 scripts/initialize_new_webui.py \\
        --name my-project \\
        --port 9132 \\
        --title "My Project Title"

After running:
    cd /home/svend/my-project
    .venv/bin/uvicorn app:app --host 0.0.0.0 --port 9132 --reload &
"""

import sys
from pathlib import Path
# Ensure project root is in sys.path so 'import config' works
# regardless of where the script is invoked from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import config
import os
import shutil
import subprocess
import time

import json
import socket
import urllib.error
import urllib.request


# ── Constants ─────────────────────────────────────────

SKELETON_DIR = Path(__file__).resolve().parent.parent / "templates" / "new-webui-skeleton"
HOME = str(Path.home())
VALID_PORT_RANGE = range(9132, 9200)


# ── CLI ────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Initialize a new DPMtF-governed WebUI project"
    )
    parser.add_argument(
        "--name", required=True,
        help="Project name (lowercase, hyphenated, e.g. 'my-project')"
    )
    parser.add_argument(
        "--port", type=int, required=True,
        help="Port number (9132-9199)"
    )
    parser.add_argument(
        "--title", required=True,
        help="Project title (displayed in page title and heading)"
    )
    return parser.parse_args()


# ── Validation ─────────────────────────────────────────

def validate_name(name):
    """Project name must be lowercase-hyphenated, no spaces or special chars."""
    if not name:
        return "Project name is required"
    if " " in name:
        return "Project name must not contain spaces (use hyphens)"
    if name != name.lower():
        return "Project name must be lowercase"
    if not all(c.isalnum() or c == "-" for c in name):
        return "Project name must only contain letters, digits, and hyphens"
    return None


def validate_port(port):
    """Port must be in valid range and not in use."""
    if port not in VALID_PORT_RANGE:
        return f"Port must be in range {VALID_PORT_RANGE.start}-{VALID_PORT_RANGE.stop - 1}"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return None
        except OSError:
            return f"Port {port} is already in use"


def validate_title(title):
    """Title must be non-empty."""
    if not title or not title.strip():
        return "Project title is required"
    return None


def validate_not_exists(project_dir):
    """Project directory must not already exist."""
    if project_dir.exists():
        return f"Directory already exists: {project_dir}"
    return None


# ── Placeholder System ────────────────────────────────

def build_placeholders(args, project_dir):
    """Build the placeholder → value mapping."""
    return {
        "{PROJECT_NAME}": args.name,
        "{PROJECT_TITLE}": args.title,
        "{PROJECT_ROOT}": str(project_dir),
        "{PORT}": str(args.port),
        "{FATHER_PROJECT}": "DPMtF-WebUI",
        "{FATHER_PROJECT_ROOT}": str(Path(HOME) / "DPMtF-WebUI"),
        "{DATABASE}": f"{args.name}.db",
    }


def replace_placeholders(file_path, placeholders):
    """Replace all placeholders in a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    for placeholder, value in placeholders.items():
        content = content.replace(placeholder, value)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def rename_file(file_path, placeholders):
    """Rename a file if its name contains placeholders."""
    old_name = str(file_path)
    new_name = old_name
    for placeholder, value in placeholders.items():
        new_name = new_name.replace(placeholder, value)
    if new_name != old_name:
        os.rename(old_name, new_name)
        return Path(new_name)
    return file_path


# ── Main Flow ──────────────────────────────────────────

def main():
    args = parse_args()

    # 1. Validate inputs
    print("=" * 60)
    print(f"Initializing new WebUI: {args.name}")
    print("=" * 60)

    errors = []
    for validator, value, label in [
        (validate_name, args.name, "name"),
        (validate_port, args.port, "port"),
        (validate_title, args.title, "title"),
    ]:
        err = validator(value)
        if err:
            errors.append(f"  ❌ {label}: {err}")
        else:
            print(f"  ✅ {label}: {value}")

    project_dir = Path(HOME) / args.name
    err = validate_not_exists(project_dir)
    if err:
        errors.append(f"  ❌ {err}")
    else:
        print(f"  ✅ directory: {project_dir} (does not exist)")

    if errors:
        print("\nVALIDATION FAILED:")
        for e in errors:
            print(e)
        sys.exit(1)

    placeholders = build_placeholders(args, project_dir)

    # 2. Verify skeleton directory exists
    if not SKELETON_DIR.exists():
        print(f"\n❌ Skeleton directory not found: {SKELETON_DIR}")
        sys.exit(1)
    print(f"\n📁 Skeleton source: {SKELETON_DIR}")

    # 3. Create directory structure
    print("\n📂 Creating directory structure...")
    dirs = [
        project_dir,
        project_dir / "templates",
        project_dir / "static" / "js",
        project_dir / "static" / "css",
        project_dir / "scripts",
        project_dir / "databases",
        project_dir / "docs" / "dpmtf",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {d}")

    # 4. Copy skeleton files
    print("\n📋 Copying skeleton files...")
    copied = []
    for item in SKELETON_DIR.rglob("*"):
        if item.is_file() and "__pycache__" not in item.parts:
            rel = item.relative_to(SKELETON_DIR)
            dest = project_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            copied.append(dest)
            print(f"  ✅ {rel}")

    # 5. Replace placeholders in all copied files
    print("\n🔄 Replacing placeholders...")
    for file_path in copied:
        if file_path.suffix in (".py", ".html", ".js", ".css", ".ini", ".txt") or file_path.name == ".env":
            replace_placeholders(file_path, placeholders)

    # 6. Rename files with placeholder names
    print("\n🏷️ Renaming files...")
    for file_path in list(copied):
        new_path = rename_file(file_path, placeholders)
        if new_path != file_path:
            print(f"  ✅ {file_path.name} → {new_path.name}")

    # 7. Create venv
    print("\n🐍 Creating virtual environment...")
    result = subprocess.run(
        ["python3", "-m", "venv", str(project_dir / ".venv")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ❌ venv creation failed: {result.stderr}")
        sys.exit(1)
    print("  ✅ .venv created")

    # 8. Install dependencies
    print("\n📦 Installing dependencies...")
    pip = str(project_dir / ".venv" / "bin" / "pip")
    result = subprocess.run(
        [pip, "install", "-r", str(project_dir / "requirements.txt")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ❌ pip install failed: {result.stderr}")
        sys.exit(1)
    print("  ✅ Dependencies installed")

    # 9. Initialize database
    print("\n🗄️ Initializing database...")
    python = str(project_dir / ".venv" / "bin" / "python3")
    child_env = os.environ.copy()
    child_env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [python, str(project_dir / "scripts" / "init_db.py")],
        capture_output=True, text=True, cwd=str(project_dir),
        env=child_env,
    )
    if result.returncode != 0:
        print(f"  ❌ Database init failed: {result.stderr}")
        sys.exit(1)
    print(f"  {result.stdout.strip()}")

    # 10. Verify health endpoint
    print("\n🏥 Verifying health endpoint...")
    uvicorn_path = str(project_dir / ".venv" / "bin" / "uvicorn")
    server_proc = subprocess.Popen(
        [uvicorn_path, "app:app", "--host", "0.0.0.0", "--port", str(args.port)],
        cwd=str(project_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=child_env,
    )

    # Wait for server to start
    time.sleep(2)

    try:
        req = urllib.request.Request(f"http://localhost:{args.port}/api/health")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        print(f"  ✅ Health check: {data}")
    except Exception as e:
        print(f"  ❌ Health check failed: {e}")
        server_proc.terminate()
        sys.exit(1)
    finally:
        server_proc.terminate()
        server_proc.wait()

    # 11. Summary
    print("\n" + "=" * 60)
    print("✅ PROJECT INITIALIZED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Name:       {args.name}")
    print(f"  Title:      {args.title}")
    print(f"  Directory:  {project_dir}")
    print(f"  Port:       {args.port}")
    print(f"  Database:   {args.name}.db")
    print()
    print("Next steps:")
    print(f"  cd {project_dir}")
    print(f"  .venv/bin/uvicorn app:app --host 0.0.0.0 --port {args.port} --reload &")
    print(f"  Open http://localhost:{args.port}/")
    print()
    print("Add domain-specific panels and endpoints via prompts.")
    print("Governance files to create in docs/dpmtf/:")
    print("  - 10_PROJECT.md (project identity)")
    print("  - 11_SCOPE.md (current phase scope)")
    print()
    print("All other governance files (coding standards, validation, architecture,")
    print("file access, git policy, etc.) are referenced from the Father project:")
    print(f"  {config.get_project_root()}/docs/governance-templates-v2/")
    print("Child projects do NOT maintain copies of structural governance files.")


if __name__ == "__main__":
    main()
