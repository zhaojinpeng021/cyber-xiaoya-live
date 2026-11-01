#!/usr/bin/env python3
"""Release OmniVoice / CUDA VRAM used by the digital-human TTS stack.

Killing the serving process is what actually returns GPU memory. This helper:
  1) reports nvidia-smi (if available)
  2) stops OmniVoice listeners on :9877 (omnivoice-demo / demo_flashinfer leftovers)
  3) best-effort torch.cuda.empty_cache in this process (only helps if you imported a model here)
  4) reports nvidia-smi again

Usage (WSL):
  python3 tools/release_cuda_vram.py
  python3 tools/release_cuda_vram.py --port 9877 --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import time
from typing import Iterable


DEFAULT_PATTERNS = (
    r"omnivoice-demo",
    r"omnivoice\.cli\.demo",
    r"demo_flashinfer",
)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def nvidia_smi() -> str:
    if not shutil.which("nvidia-smi"):
        return "(nvidia-smi not found)"
    cp = run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
            "--format=csv,noheader",
        ]
    )
    if cp.returncode != 0:
        return cp.stderr.strip() or cp.stdout.strip() or "(nvidia-smi failed)"
    return cp.stdout.strip()


def pids_listening_on(port: int) -> list[int]:
    if shutil.which("ss"):
        cp = run(["ss", "-ltnp"])
        if cp.returncode != 0:
            return []
        out = []
        for line in cp.stdout.splitlines():
            if f":{port}" not in line:
                continue
            for m in re.finditer(r"pid=(\d+)", line):
                out.append(int(m.group(1)))
        return sorted(set(out))
    if shutil.which("lsof"):
        cp = run(["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"])
        if cp.returncode != 0:
            return []
        return sorted({int(x) for x in cp.stdout.split() if x.isdigit()})
    return []


def pids_matching(patterns: Iterable[str]) -> list[int]:
    cp = run(["ps", "-eo", "pid=,args="])
    if cp.returncode != 0:
        return []
    compiled = [re.compile(p) for p in patterns]
    found: list[int] = []
    me = os.getpid()
    for line in cp.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == me:
            continue
        args = parts[1]
        if any(c.search(args) for c in compiled):
            found.append(pid)
    return sorted(set(found))


def kill_pids(pids: list[int], dry_run: bool) -> None:
    for pid in pids:
        if dry_run:
            print(f"[dry-run] would kill pid={pid}")
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[sigterm] pid={pid}")
        except ProcessLookupError:
            print(f"[gone] pid={pid}")
        except PermissionError as e:
            print(f"[deny] pid={pid}: {e}")
    if dry_run or not pids:
        return
    time.sleep(1.5)
    for pid in pids:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"[sigkill] pid={pid}")
        except ProcessLookupError:
            pass
        except PermissionError as e:
            print(f"[deny-kill] pid={pid}: {e}")


def empty_torch_cache() -> None:
    try:
        import torch  # type: ignore
    except Exception:
        print("[torch] not in this process (ok — kill is what frees server VRAM)")
        return
    if not torch.cuda.is_available():
        print("[torch] CUDA unavailable")
        return
    before = torch.cuda.memory_allocated()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()
    after = torch.cuda.memory_allocated()
    print(f"[torch] empty_cache: allocated {before} -> {after} bytes")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=9877, help="OmniVoice Gradio port")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-kill", action="store_true", help="only report + empty_cache")
    args = ap.parse_args()

    print("=== before ===")
    print(nvidia_smi())

    targets = sorted(set(pids_listening_on(args.port) + pids_matching(DEFAULT_PATTERNS)))
    print(f"targets port={args.port} pids={targets or '[]'}")
    if not args.no_kill:
        kill_pids(targets, args.dry_run)
        time.sleep(1.0)

    empty_torch_cache()

    print("=== after ===")
    print(nvidia_smi())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
