from __future__ import annotations

import argparse
import sys
import textwrap

import paramiko

REMOTE_SCRIPT = r'''
set -euxo pipefail
sudo -n true
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y apache2 libapache2-mod-security2 modsecurity-crs python3 curl
sudo a2enmod security2 unique_id headers proxy proxy_http >/dev/null || true
sudo mkdir -p /opt/hermes-lab /var/cache/modsecurity /var/log/hermes-lab

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

sudo tee /opt/hermes-lab/safe_bool_oracle.py >/dev/null <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z_\s().+\-*/<>=!]+$")
BETWEEN_RE = re.compile(
    r"^\s*(?P<x>\d+(?:\.\d+)?)\s+BETWEEN\s+(?P<a>\d+(?:\.\d+)?)\s+AND\s+(?P<b>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


def normalize_sqlish(expr: str) -> str:
    expr = expr.strip()
    match = BETWEEN_RE.match(expr)
    if match:
        x = match.group("x")
        a = match.group("a")
        b = match.group("b")
        return f"({a} <= {x} <= {b})"
    expr = re.sub(r"<>", "!=", expr)
    expr = re.sub(r"(?<![<>=!])=(?!=)", "==", expr)
    return expr


class SafeEval(ast.NodeVisitor):
    allowed_nodes = (
        ast.Expression,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Constant,
        ast.And,
        ast.Or,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Load,
    )

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, self.allowed_nodes):
            raise ValueError(f"disallowed_node:{type(node).__name__}")
        super().generic_visit(node)


def evaluate(expr: str) -> tuple[str, str]:
    if not expr or len(expr) > 160:
        return "", "invalid_length"
    if not ALLOWED_CHARS.match(expr):
        return "", "invalid_charset"
    lowered = expr.lower()
    blocked_words = ("select", "insert", "update", "delete", "drop", "union", "from", "where", "sleep", "pg_", "copy")
    if any(word in lowered for word in blocked_words):
        return "", "blocked_keyword"
    normalized = normalize_sqlish(expr)
    tree = ast.parse(normalized, mode="eval")
    SafeEval().visit(tree)
    result = eval(compile(tree, "<safe_bool_oracle>", "eval"), {"__builtins__": {}}, {})
    return ("TRUE" if bool(result) else "FALSE"), "ok"


class Handler(BaseHTTPRequestHandler):
    server_version = "HermesSafeBoolOracle/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/bool_oracle", "/health"}:
            self.send_json(404, {"backend_reached": True, "error": "not_found"})
            return
        if parsed.path == "/health":
            self.send_json(200, {"status": "ok", "backend_reached": True})
            return
        qs = parse_qs(parsed.query, keep_blank_values=True)
        probe_id = (qs.get("probe_id") or [""])[0][:128]
        expr = (qs.get("expr") or [""])[0]
        try:
            observed, status = evaluate(expr)
            code = 200 if status == "ok" else 400
            self.send_json(code, {
                "backend_reached": True,
                "probe_id": probe_id,
                "observed_truth": observed,
                "postgres_status": "safe_restricted_boolean_oracle",
                "error": "" if status == "ok" else status,
            })
        except Exception as exc:
            self.send_json(400, {
                "backend_reached": True,
                "probe_id": probe_id,
                "observed_truth": "",
                "postgres_status": "safe_restricted_boolean_oracle",
                "error": type(exc).__name__,
            })

    def send_json(self, code: int, body: dict) -> None:
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18081), Handler).serve_forever()
PY
sudo chmod 0755 /opt/hermes-lab/safe_bool_oracle.py

sudo tee /etc/systemd/system/hermes-safe-bool-oracle.service >/dev/null <<'UNIT'
[Unit]
Description=Hermes restricted Boolean oracle backend
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/hermes-lab/safe_bool_oracle.py
Restart=always
RestartSec=2
User=www-data
Group=www-data
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-safe-bool-oracle.service

if ! grep -q '^Listen 18080$' /etc/apache2/ports.conf; then
  printf '\nListen 18080\n' | sudo tee -a /etc/apache2/ports.conf >/dev/null
fi
sudo mkdir -p /var/www/hermes-lab
printf '%s\n' '<html><body>Hermes lab WAF endpoint</body></html>' | sudo tee /var/www/hermes-lab/index.html >/dev/null
sudo tee /etc/apache2/sites-available/hermes-lab-waf.conf >/dev/null <<'SITE'
<VirtualHost 127.0.0.1:18080>
    ServerName hermes-lab.local
    DocumentRoot /var/www/hermes-lab
    ErrorLog ${APACHE_LOG_DIR}/hermes_lab_error.log
    CustomLog ${APACHE_LOG_DIR}/hermes_lab_access.log combined
    ProxyPreserveHost On
    ProxyPass /bool_oracle http://127.0.0.1:18081/bool_oracle
    ProxyPassReverse /bool_oracle http://127.0.0.1:18081/bool_oracle
    ProxyPass /oracle_health http://127.0.0.1:18081/health
    ProxyPassReverse /oracle_health http://127.0.0.1:18081/health
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
curl -fsS 'http://127.0.0.1:18080/oracle_health'
printf '\n'
curl -fsS 'http://127.0.0.1:18080/bool_oracle?probe_id=deploy-smoke&expr=1%3D1'
printf '\nSAFE_BOOLEAN_ORACLE_READY\n'
'''


VERIFY_SCRIPT = r'''
set -euo pipefail
health="$(curl -fsS 'http://127.0.0.1:18080/oracle_health')"
true_case="$(curl -fsS 'http://127.0.0.1:18080/bool_oracle?probe_id=verify-true&expr=1%3D1')"
false_case="$(curl -fsS 'http://127.0.0.1:18080/bool_oracle?probe_id=verify-false&expr=1%3D2')"
printf '%s\n' "$health"
printf '%s\n' "$true_case"
printf '%s\n' "$false_case"
printf 'SAFE_BOOLEAN_ORACLE_VERIFY_OK\n'
'''


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
    parser = argparse.ArgumentParser(description="Deploy safe restricted Boolean oracle backend behind local ModSecurity.")
    parser.add_argument("--host", default="192.168.244.128")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--key", default=r"C:\Users\Admin\.ssh\hermes_lab_ed25519")
    parser.add_argument("--verify-only", action="store_true", help="Verify the existing backend without reinstalling packages or rewriting service files.")
    args = parser.parse_args()
    script = VERIFY_SCRIPT if args.verify_only else REMOTE_SCRIPT
    status = run_remote(args.host, args.user, args.key, textwrap.dedent(script).strip() + "\n")
    print(f"REMOTE_EXIT {status}")
    raise SystemExit(status)


if __name__ == "__main__":
    main()
