from __future__ import annotations

import argparse
import sys
import textwrap

import paramiko

ATOMIC_COMMAND = r"""
set -euxo pipefail
sudo -n true
export DEBIAN_FRONTEND=noninteractive
sudo dpkg --configure -a
sudo apt-get update
sudo apt-get install -y wget apt-transport-https software-properties-common git curl ca-certificates
if ! command -v pwsh >/dev/null 2>&1; then
  tmpdeb=/tmp/packages-microsoft-prod.deb
  wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb -O "$tmpdeb"
  sudo dpkg -i "$tmpdeb"
  sudo apt-get update
  sudo apt-get install -y powershell
fi
pwsh -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
mkdir -p "$HOME/hermes-lab/atomic"
if [ ! -d "$HOME/hermes-lab/atomic/atomic-red-team/.git" ]; then
  git clone --depth 1 https://github.com/redcanaryco/atomic-red-team.git "$HOME/hermes-lab/atomic/atomic-red-team"
else
  git -C "$HOME/hermes-lab/atomic/atomic-red-team" pull --ff-only || true
fi
cat > "$HOME/hermes-lab/atomic/allowlist.json" <<'JSON'
{
  "scope": "Hermes isolated lab only",
  "execution_default": "do_not_execute_without_explicit_allowlist_runner",
  "allowed_platform": "linux",
  "notes": "Tooling preparation only. Actual Atomic tests require separate runner, prereq check, cleanup and snapshot awareness.",
  "techniques": []
}
JSON
printf '\n=== atomic status ===\n'
test -d "$HOME/hermes-lab/atomic/atomic-red-team/atomics" && echo ATOMIC_REPO_OK
pwsh -NoLogo -NoProfile -Command 'Write-Output "PWSH_OK"'
ls -l "$HOME/hermes-lab/atomic/allowlist.json"
printf 'ATOMIC_TOOLING_READY\n'
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
    status = run_remote(args.host, args.user, args.key, textwrap.dedent(ATOMIC_COMMAND).strip() + "\n")
    print(f"REMOTE_EXIT {status}")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
