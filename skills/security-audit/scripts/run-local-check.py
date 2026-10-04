"""Run one bounded, offline local check in an existing Linux Docker image.

This helper captures only a bounded result. It never promotes files from the
container scratch space into audit artifacts.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid


MAX_OUTPUT_BYTES = 65536
MAX_SECONDS = 120


def docker(*args, timeout=10):
    return subprocess.run(["docker", *args], capture_output=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Existing source directory to mount read-only")
    parser.add_argument("--image", required=True, help="Already available Linux toolchain image")
    parser.add_argument("--timeout", type=int, default=30, help="Wall time in seconds, 1–120")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Absolute executable and arguments after --")
    args = parser.parse_args()

    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not command[0].startswith("/"):
        parser.error("provide an absolute executable path after --")
    if not 1 <= args.timeout <= MAX_SECONDS:
        parser.error("timeout must be between 1 and 120 seconds")
    if not args.image or args.image.startswith("-"):
        parser.error("image must be a locally available image reference")
    target = Path(args.target).resolve(strict=True)
    if not target.is_dir():
        parser.error("target must be an existing directory")
    if "," in str(target) or "\n" in str(target) or "\r" in str(target):
        parser.error("target contains characters unsafe for Docker mount syntax")
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise RuntimeError("unset DOCKER_HOST and DOCKER_CONTEXT before using the local sandbox")

    try:
        info = docker("info", "--format", "{{json .SecurityOptions}}|{{.OSType}}")
        if info.returncode != 0 or not info.stdout.strip().endswith(b"|linux"):
            raise RuntimeError("a running Linux Docker engine is required")
        security_options = json.loads(info.stdout.split(b"|", 1)[0])
        if not any("seccomp" in option for option in security_options):
            raise RuntimeError("Docker seccomp protection is required")
        context = docker("context", "inspect", "--format", "{{.Endpoints.docker.Host}}")
        if context.returncode != 0 or not context.stdout.strip().startswith((b"npipe://", b"unix://")):
            raise RuntimeError("a local Docker context is required")
        image = docker("image", "inspect", args.image)
        if image.returncode != 0 or not image.stdout.strip():
            raise RuntimeError("the requested image must already exist locally")
        image_config = json.loads(image.stdout)[0]
        if not image_config.get("Id", "").startswith("sha256:") or image_config.get("Config", {}).get("Volumes"):
            raise RuntimeError("the image must have a digest and no declared writable volumes")
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Docker preflight failed") from error

    name = f"security-audit-check-{uuid.uuid4().hex}"
    docker_args = [
        "docker", "run", "--rm", "--name", name, "--pull=never", "--no-healthcheck",
        "--network=none", "--ipc=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true", "--pids-limit=64",
        "--memory=512m", "--memory-swap=512m", "--cpus=1",
        "--ulimit=fsize=16777216:16777216", "--user=65534:65534",
        f"--mount=type=bind,src={target},dst=/target,readonly",
        "--tmpfs=/scratch:rw,nosuid,nodev,noexec,size=64m,mode=1777",
        "--workdir=/target", "--entrypoint=/usr/bin/env", args.image,
        "-i", "HOME=/scratch", "TMPDIR=/scratch", "TMP=/scratch",
        "PATH=/usr/local/bin:/usr/bin:/bin", *command,
    ]

    output = bytearray()
    exceeded = threading.Event()

    def drain(pipe):
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                break
            remaining = MAX_OUTPUT_BYTES - len(output)
            output.extend(chunk[:remaining])
            if len(chunk) > remaining:
                exceeded.set()

    process = subprocess.Popen(
        docker_args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, env=os.environ.copy(),
    )
    reader = threading.Thread(target=drain, args=(process.stdout,), daemon=True)
    reader.start()
    deadline = time.monotonic() + args.timeout
    timed_out = False
    cleanup_failed = False
    try:
        while process.poll() is None and not exceeded.is_set():
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.05)
    finally:
        if process.poll() is None:
            try:
                removed = docker("rm", "-f", name, timeout=10)
                cleanup_failed = removed.returncode != 0
            except (OSError, subprocess.TimeoutExpired):
                cleanup_failed = True
            process.kill()
        process.wait(timeout=10)
        reader.join(timeout=5)

    print(json.dumps({
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "output_truncated": exceeded.is_set(),
        "cleanup_failed": cleanup_failed,
        "output": output.decode("utf-8", errors="replace"),
    }, ensure_ascii=True))
    return 1 if timed_out or exceeded.is_set() or cleanup_failed or process.returncode else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=True), file=sys.stderr)
        sys.exit(2)
