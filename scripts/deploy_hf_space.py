"""
Deploy (or redeploy) the app to a Hugging Face Docker Space.

Run it after logging in with `hf auth login` and committing your changes:

    venv\\Scripts\\python scripts\\deploy_hf_space.py <username>/<space-name>

It uploads exactly what is committed in git (HEAD), so .env, local data and
screenshots never leave this computer, and it creates the Space (public, Docker)
the first time. Set the Space's secrets with scripts/hf_space_secrets.py.
"""
import io
import os
import subprocess
import sys
import tarfile

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Files Hugging Face manages itself in every Space
KEEP_REMOTE = {".gitattributes"}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def committed_files():
    """{path: bytes} for every file in HEAD, with Linux line endings (the Space builds on Linux)"""
    files = {}
    # Git on Windows usually converts to CRLF when exporting; keep the LF endings stored in the repository
    tar = git("-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar", "HEAD")
    with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        for member in archive.getmembers():
            if member.isfile():
                files[member.name] = archive.extractfile(member).read()
    return files


def main():
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        print(__doc__)
        sys.exit(1)
    space = sys.argv[1]

    if git("status", "--porcelain", "--untracked-files=no").strip():
        print("Note: you have uncommitted changes. Only committed work is deployed; commit first to include them.")
    files = committed_files()
    if any(os.path.basename(path) == ".env" for path in files):
        sys.exit("Refusing to deploy: a .env file is committed in git. Remove it from git first (it holds your secrets).")

    api = HfApi()
    api.create_repo(space, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    remote = set(api.list_repo_files(space, repo_type="space"))
    operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=data) for path, data in sorted(files.items())]
    operations += [CommitOperationDelete(path_in_repo=path) for path in sorted(remote - set(files) - KEEP_REMOTE)]

    commit = git("rev-parse", "--short", "HEAD").decode().strip()
    api.create_commit(space, repo_type="space", operations=operations, commit_message=f"Deploy {commit}")
    host = api.space_info(space).host or f"https://huggingface.co/spaces/{space}"
    print(f"Uploaded {len(files)} files from commit {commit}. The Space is building now (a few minutes).")
    print(f"Build logs: https://huggingface.co/spaces/{space}?logs=build")
    print(f"App: {host}")


if __name__ == "__main__":
    main()
