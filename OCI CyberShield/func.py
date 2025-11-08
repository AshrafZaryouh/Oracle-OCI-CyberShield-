# func.py - OCI CyberShield Pro
import oci
import json
import re
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

# Load OCI config
try:
    config = oci.config.from_file("~/.oci/config", "DEFAULT")
except:
    config = oci.config.from_file("/function/oci_config", "DEFAULT")

# OCI Clients
network_client = oci.core.VirtualNetworkClient(config)
identity_client = oci.identity.IdentityClient(config)

# === CONFIGURATION (EDIT THESE) ===
NSG_ID = "ocid1.networksecuritygroup.oc1..aaaaaaaaxxxxxxxx"  # CHANGE THIS
LOG_GROUP_ID = "ocid1.loggroup.oc1..aaaaaaaayyyyyyyy"           # CHANGE THIS
COMPARTMENT_ID = config.get("tenancy")
BLOCKED_IPS = set()
RATE_LIMIT = {}
DDoS_THRESHOLD = 150
BRUTE_FORCE_THRESHOLD = 5

# Attack Patterns
PATTERNS = {
    "brute_force": re.compile(r"Failed password for.*from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
    "port_scan": re.compile(r"refused connect from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
    "ssh_login": re.compile(r"Accepted password for.*from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
    "sql_injection": re.compile(r"(union select|drop table|';--)", re.IGNORECASE),
}

def rate_limit_check(ip):
    now = datetime.utcnow()
    if ip not in RATE_LIMIT:
        RATE_LIMIT[ip] = []
    # Clean old entries
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < timedelta(minutes=1)]
    RATE_LIMIT[ip].append(now)
    return len(RATE_LIMIT[ip])

def block_ip(ip):
    if ip in BLOCKED_IPS:
        return
    try:
        nsg = network_client.get_network_security_group(NSG_ID).data
        rules = nsg.security_rules or []
        if any(r.source == f"{ip}/32" for r in rules):
            return

        new_rule = oci.core.models.AddSecurityRuleDetails(
            direction="INGRESS",
            protocol="6",
            source=f"{ip}/32",
            source_type="CIDR_BLOCK",
            is_stateless=False,
            description=f"[CyberShield] Auto-block {ip} - {datetime.utcnow().isoformat()}Z"
        )
        network_client.add_security_rule(NSG_ID, new_rule)
        BLOCKED_IPS.add(ip)
        log.warning(f"BLOCKED: {ip}")
        send_notification(ip, "BLOCKED")
    except Exception as e:
        log.error(f"Block failed {ip}: {e}")

def send_notification(ip, action):
    # Optional: Integrate with OCI Notifications, Slack, Email
    log.info(f"ALERT: {action} - {ip}")

def extract_ip_from_message(message):
    for pattern in PATTERNS.values():
        match = pattern.search(message)
        if match:
            return match.group(1)
    return None

def analyze_log(log_entry):
    data = log_entry.get("data", {})
    message = data.get("message", "") or str(data)
    source_ip = data.get("source", {}).get("ipAddress")

    if not source_ip:
        source_ip = extract_ip_from_message(message)

    if not source_ip or not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", source_ip):
        return

    requests = rate_limit_check(source_ip)

    # DDoS Detection
    if requests > DDoS_THRESHOLD:
        block_ip(source_ip)
        return

    # Brute Force
    if "Failed password" in message and requests > BRUTE_FORCE_THRESHOLD:
        block_ip(source_ip)
        return

    # Port Scan
    if PATTERNS["port_scan"].search(message):
        block_ip(source_ip)

# Main handler (triggered by OCI Events)
def handler(ctx, data: str = None):
    if not data:
        return "No data"
    try:
        payload = json.loads(data)
        logs = payload.get("data", {}).get("logEntries", [])
        for log in logs:
            analyze_log(log)
        return "OK"
    except Exception as e:
        log.error(f"Error: {e}")
        return "Error"