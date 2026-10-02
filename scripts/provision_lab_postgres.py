from __future__ import annotations

import argparse
import sys
import textwrap

import paramiko

POSTGRES_COMPOSE = """
version: '3.3'
services:
  postgres:
    image: postgres:16-alpine
    container_name: hermes-lab-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: hermes_lab
      POSTGRES_PASSWORD: hermes_lab
      POSTGRES_DB: hermes_lab
    ports:
      - '127.0.0.1:15432:5432'
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U hermes_lab -d hermes_lab']
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - postgres_data:/var/lib/postgresql/data
volumes:
  postgres_data:
"""

REMOTE_COMMAND = """
set -euxo pipefail
mkdir -p "$HOME/hermes-lab"
cat > "$HOME/hermes-lab/docker-compose.yml" <<'YAML'
{compose}
YAML
cd "$HOME/hermes-lab"
sudo docker-compose up -d postgres
for i in $(seq 1 40); do
  if sudo docker exec hermes-lab-postgres pg_isready -U hermes_lab -d hermes_lab; then
    break
  fi
  sleep 2
done
sudo docker exec hermes-lab-postgres psql -U hermes_lab -d hermes_lab -v ON_ERROR_STOP=1 -c 'SELECT version();'
sudo docker ps --filter name=hermes-lab-postgres
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
    command = textwrap.dedent(REMOTE_COMMAND.format(compose=POSTGRES_COMPOSE.strip())).strip() + "\n"
    status = run_remote(args.host, args.user, args.key, command)
    print(f"REMOTE_EXIT {status}")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
