from __future__ import annotations

import argparse
import sys
import textwrap

import paramiko

WAF_COMMAND = r"""
set -euxo pipefail
sudo -n true
export DEBIAN_FRONTEND=noninteractive
sudo dpkg --configure -a
sudo apt-get update
sudo apt-get install -y apache2 libapache2-mod-security2 modsecurity-crs curl jq
sudo a2enmod security2 unique_id headers rewrite >/dev/null || true
sudo mkdir -p /var/www/hermes-lab /var/cache/modsecurity /var/log/hermes-lab
printf '%s\n' '<html><body>Hermes lab WAF endpoint</body></html>' | sudo tee /var/www/hermes-lab/index.html >/dev/null
if [ -f /etc/modsecurity/modsecurity.conf-recommended ]; then
  sudo cp /etc/modsecurity/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
fi
sudo sed -i 's/^SecRuleEngine .*/SecRuleEngine DetectionOnly/' /etc/modsecurity/modsecurity.conf
sudo sed -i 's/^SecAuditEngine .*/SecAuditEngine On/' /etc/modsecurity/modsecurity.conf
sudo sed -i 's#^SecAuditLog .*#SecAuditLog /var/log/apache2/modsec_audit.log#' /etc/modsecurity/modsecurity.conf
if [ -f /usr/share/modsecurity-crs/crs-setup.conf.example ] && [ ! -f /etc/modsecurity/crs-setup.conf ]; then
  sudo cp /usr/share/modsecurity-crs/crs-setup.conf.example /etc/modsecurity/crs-setup.conf
fi
sudo tee /etc/apache2/mods-enabled/security2.conf >/dev/null <<'CONF'
<IfModule security2_module>
    SecDataDir /var/cache/modsecurity
    IncludeOptional /etc/modsecurity/*.conf
    IncludeOptional /usr/share/modsecurity-crs/owasp-crs.load
</IfModule>
CONF
if ! grep -q '^Listen 18080$' /etc/apache2/ports.conf; then
  printf '\nListen 18080\n' | sudo tee -a /etc/apache2/ports.conf >/dev/null
fi
sudo tee /etc/apache2/sites-available/hermes-lab-waf.conf >/dev/null <<'SITE'
<VirtualHost 127.0.0.1:18080>
    ServerName hermes-lab.local
    DocumentRoot /var/www/hermes-lab
    ErrorLog ${APACHE_LOG_DIR}/hermes_lab_error.log
    CustomLog ${APACHE_LOG_DIR}/hermes_lab_access.log combined
    <Directory /var/www/hermes-lab>
        Require all granted
    </Directory>
</VirtualHost>
SITE
sudo a2dissite 000-default >/dev/null || true
sudo a2ensite hermes-lab-waf >/dev/null
sudo apache2ctl configtest
sudo systemctl restart apache2
sleep 1
curl -fsS 'http://127.0.0.1:18080/?probe=health' >/dev/null
printf '\n=== waf status ===\n'
systemctl is-active apache2
sudo apache2ctl -M | grep -E 'security2|unique_id|headers' || true
ls -ld /usr/share/modsecurity-crs /var/log/apache2
printf 'WAF_READY\n'
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
    status = run_remote(args.host, args.user, args.key, textwrap.dedent(WAF_COMMAND).strip() + "\n")
    print(f"REMOTE_EXIT {status}")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
