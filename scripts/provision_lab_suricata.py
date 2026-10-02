from __future__ import annotations

import argparse
import sys
import textwrap

import paramiko

SURICATA_COMMAND = r"""
set -euxo pipefail
sudo -n true
export DEBIAN_FRONTEND=noninteractive
sudo dpkg --configure -a
sudo apt-get update
sudo apt-get install -y software-properties-common jq curl
sudo add-apt-repository -y universe || true
sudo apt-get update
if apt-cache policy suricata | grep -q 'Candidate: (none)'; then
  sudo add-apt-repository -y ppa:oisf/suricata-stable || true
  sudo apt-get update
fi
sudo apt-get install -y suricata jq curl
sudo mkdir -p /var/log/suricata /etc/suricata/rules
suricata --build-info | sed -n '1,25p'
sudo systemctl enable suricata || true
sudo systemctl restart suricata || true
sleep 2
printf '\n=== suricata status ===\n'
suricata -V
systemctl is-active suricata || true
sudo ls -ld /var/log/suricata /etc/suricata
sudo ls -l /var/log/suricata | sed -n '1,20p' || true
printf 'SURICATA_READY\n'
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
    status = run_remote(args.host, args.user, args.key, textwrap.dedent(SURICATA_COMMAND).strip() + "\n")
    print(f"REMOTE_EXIT {status}")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
