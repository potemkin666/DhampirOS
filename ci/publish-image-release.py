#!/usr/bin/python3
"""AI-Assisted. One-shot publication after a committed, digest-bound boot review.

No guest image programs execute in this job. Write permission is isolated from
the source builder and VM verifier; this job copies and hashes reviewed data.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess

REPOSITORY = "potemkin666/DhampirOS"
TAG = "v0.1.0-alpha.1"
review_file = Path("release-reviews") / f"{TAG}.json"
review = json.loads(review_file.read_text())


def execute(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def gh_json(*args):
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def source_run(field, workflow):
    run_id = str(review[field])
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise SystemExit("Invalid reviewed Actions run")
    run = gh_json("api", f"repos/{REPOSITORY}/actions/runs/{run_id}")
    if (run["repository"]["full_name"] != REPOSITORY or
            run["head_repository"]["full_name"] != REPOSITORY or
            run["path"] != f".github/workflows/{workflow}" or run["conclusion"] != "success" or
            run["event"] not in ("push", "workflow_dispatch")):
        raise SystemExit("Reviewed run is not a successful authorized workflow")
    execute("git", "merge-base", "--is-ancestor", run["head_sha"], "HEAD")
    return run_id, run


build_id, build = source_run("candidate_run", "local-images.yml")
verification_id, verification = source_run("verification_run", "local-image-verification.yml")
if build["head_sha"] != review["source_commit"]:
    raise SystemExit("Reviewed source differs from the image build")
execute("git", "merge-base", "--is-ancestor", build["head_sha"], verification["head_sha"])
execute("gh", "run", "download", build_id, "--repo", REPOSITORY,
        "--pattern", "dhampiros-*-candidate", "--dir", "candidates")
execute("gh", "run", "download", verification_id, "--repo", REPOSITORY,
        "--pattern", "dhampiros-*-verification", "--dir", "verified")
for image in Path("candidates").rglob("DhampirOS-*.iso"):
    execute("gh", "attestation", "verify", image, "--repo", REPOSITORY,
            "--signer-workflow", f"{REPOSITORY}/.github/workflows/local-images.yml",
            "--source-digest", build["head_sha"])
for image in Path("candidates").rglob("DhampirOS-*.ova"):
    execute("gh", "attestation", "verify", image, "--repo", REPOSITORY,
            "--signer-workflow", f"{REPOSITORY}/.github/workflows/local-images.yml",
            "--source-digest", build["head_sha"])
execute("./ci/prepare-image-release.py", "--candidates", "candidates", "--verification", "verified",
        "--review", review_file, "--output", "prepared-release")

notes = Path("release-notes.txt")
notes.write_text(
    "Experimental DhampirOS alpha for AMD64, with the Nocturne artwork and native motion.\n\n"
    f"Exact image source: {build['head_sha']}\n"
    f"Build and provenance: {build['html_url']}\n"
    f"Independent verification: {verification['html_url']}\n\n"
    "Includes SHA256SUMS, a bounded verification report and an evidence archive with package "
    "inventories, vulnerability findings and reviewed BIOS/UEFI QEMU desktop captures.\n\n"
    "Independent Kicksecure-based derivative; not an official Kicksecure release. "
    "Not a security certification or guarantee. Physical hardware, Secure Boot and actual "
    "VirtualBox runtime remain unverified. Review the report before use.\n",
    encoding="utf-8",
)
existing = subprocess.run(["gh", "release", "view", TAG, "--repo", REPOSITORY,
                           "--json", "isDraft,targetCommitish"], capture_output=True, text=True)
if existing.returncode == 0:
    state = json.loads(existing.stdout)
    if not state["isDraft"] or state["targetCommitish"] != build["head_sha"]:
        raise SystemExit("Refusing to replace an existing public or differently sourced release")
else:
    execute("gh", "release", "create", TAG, "--repo", REPOSITORY, "--draft", "--prerelease",
            "--target", build["head_sha"], "--title", "DhampirOS 0.1.0 alpha 1",
            "--notes-file", notes)
files = sorted(path for path in Path("prepared-release").iterdir() if path.name != "catalogue-proposal.json")
execute("gh", "release", "upload", TAG, "--repo", REPOSITORY, "--clobber", *files)
release = gh_json("api", f"repos/{REPOSITORY}/releases/tags/{TAG}")
remote = {asset["name"]: asset for asset in release["assets"]}
for file in files:
    with file.open("rb") as payload:
        expected = "sha256:" + hashlib.file_digest(payload, "sha256").hexdigest()
    if remote.get(file.name, {}).get("digest") != expected or remote[file.name]["size"] != file.stat().st_size:
        raise SystemExit(f"Uploaded release asset integrity mismatch: {file.name}")
execute("gh", "release", "edit", TAG, "--repo", REPOSITORY, "--draft=false")
print(f"Published reviewed experimental files: https://github.com/{REPOSITORY}/releases/tag/{TAG}")
print("The website catalogue still requires public URL verification and a separate source update.")
