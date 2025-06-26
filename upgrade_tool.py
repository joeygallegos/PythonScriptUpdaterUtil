import json
import hashlib
import requests
import socket
import logging
from typing import Dict, Tuple, Optional


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def load_config(file_path: str = "upgrade_config.json") -> Dict:
    """Load JSON config from file."""
    with open(file_path, "r") as f:
        return json.load(f)


def save_config(config: Dict, file_path: str = "upgrade_config.json") -> None:
    """Save updated config to file."""
    with open(file_path, "w") as f:
        json.dump(config, f, indent=2)


def calculate_file_hash(file_path: str) -> Optional[str]:
    """Calculate SHA256 hash of a local file, streaming for large files."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        logging.warning(f"File not found: {file_path}")
        return None


def calculate_remote_file_hash(url: str) -> Tuple[str, bytes]:
    """Download remote file with no-cache headers and calculate SHA256."""
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "User-Agent": "UpgradeChecker/1.0",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    hasher = hashlib.sha256()
    hasher.update(response.content)
    return hasher.hexdigest(), response.content


def send_email(api_key: str, domain: str, to: str, subject: str, text: str) -> requests.Response:
    """Send an email via Mailgun API."""
    return requests.post(
        f"https://api.mailgun.net/v3/{domain}/messages",
        auth=("api", api_key),
        data={
            "from": f"Upgrade Checker <system-upgrades@{domain}>",
            "to": [to],
            "subject": subject,
            "text": text,
        },
    )


def upgrade_file(file_config: Dict) -> Tuple[str, Dict]:
    filename = file_config["filename"]
    url = file_config["url"]
    paused = file_config.get("paused", False)
    previous_hashes = file_config.setdefault("previous_hashes", [])
    status = {"status": "skipped", "reason": "Up-to-date"}

    logging.info(f"Checking for upgrades on {filename}")

    if paused:
        status["status"] = "skipped"
        status["reason"] = "Upgrade paused"
        logging.info(f"Upgrade paused for {filename}")
        return filename, status

    current_hash = calculate_file_hash(filename)
    if current_hash:
        logging.info(f"Current hash: {current_hash}")
    else:
        logging.info(f"No existing file: {filename}")

    try:
        remote_hash, remote_content = calculate_remote_file_hash(url)
        logging.info(f"Remote hash: {remote_hash}")
    except requests.RequestException as e:
        status["status"] = "skipped"
        status["reason"] = f"Error fetching {url}: {e}"
        logging.error(status["reason"])
        return filename, status

    if current_hash == remote_hash:
        logging.info(f"{filename} is up-to-date.")
    else:
        with open(filename, "wb") as f:
            f.write(remote_content)
        logging.info(f"{filename} updated.")

        if current_hash and current_hash not in previous_hashes:
            previous_hashes.append(current_hash)

        status["status"] = "completed"
        status["reason"] = "File updated"

    return filename, status


def main():
    config_path = "upgrade_config.json"
    config = load_config(config_path)
    mailgun_config = config.get("mailgun", {})
    files_config = config.get("files", [])
    statuses = {}

    for file_config in files_config:
        filename, status = upgrade_file(file_config)
        statuses[filename] = status

    # Save updated hashes back to config if needed
    save_config(config, config_path)

    hostname = socket.gethostname()
    email_subject = f"Upgrade Status on {hostname}"
    email_body = "Upgrade status report:\n\n"
    upgrades_found = False

    for filename, status in statuses.items():
        if status["status"] == "completed":
            upgrades_found = True
            email_body += f"Filename: {filename}\n"
            email_body += f"Status: {status['status']}\n"
            email_body += f"Reason: {status['reason']}\n\n"

    if upgrades_found and mailgun_config:
        try:
            response = send_email(
                mailgun_config["api_key"],
                mailgun_config["domain"],
                mailgun_config["email"],
                email_subject,
                email_body,
            )
            response.raise_for_status()
            logging.info("Upgrade notification email sent successfully.")
        except requests.RequestException as e:
            logging.error(f"Failed to send email: {e}")


if __name__ == "__main__":
    main()
