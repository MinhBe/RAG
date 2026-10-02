from __future__ import annotations

import argparse
import sys
import textwrap

import paramiko

BASE_COMMAND = r"""
set -euxo pipefail
sudo -n true
export DEBIAN_FRONTEND=noninteractive
sudo dpkg --configure -a
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  jq \
  git \
  unzip \
  python3 \
  python3-venv \
  python3-pip \
  auditd \
  open-vm-tools \
  docker.io \
  docker-compose
sudo systemctl enable --now docker || true
sudo systemctl enable --now auditd || true
sudo usermod -aG docker ubuntu || true
printf '\n=== versions ===\n'
uname -a
python3 --version
docker --version || true
docker-compose --version || true
jq --version
printf '\n=== services ===\n'
systemctl is-active docker || true
systemctl is-active auditd || true
systemctl is-active open-vm-tools || true
"""


def run_remote(host: str, user: str, key: str, command: str) -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, key_filename=key, look_for_keys=False, allow_agent=False, timeout=8)
    stdin, stdout, stderr = client.exec_command("bash -s", get_pty=False)
    stdin.write(command)
    stdin.channel.shutdown_write()
    for line in iter(stdout.readline, ""):
        print(line.encode("ascii", "replace").decode("ascii"), end="")
    err = stderr.read().decode(errors="replace")
    if err:
        print(err.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
    status = stdout.channel.recv_exit_status()
    client.close()
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    args = parser.parse_args()
    status = run_remote(args.host, args.user, args.key, textwrap.dedent(BASE_COMMAND).strip() + "\n")
    print(f"REMOTE_EXIT {status}")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
