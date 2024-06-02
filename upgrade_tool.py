import json
import hashlib
import requests
import socket


def load_config(file_path="upgrade_config.json"):
    with open(file_path, "r") as f:
        return json.load(f)


def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


def calculate_remote_file_hash(url):
    response = requests.get(url)
    response.raise_for_status()
    hasher = hashlib.sha256()
    hasher.update(response.content)
    return hasher.hexdigest(), response.content


def send_email(api_key, domain, to, subject, text):
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


def upgrade_file(file_config, mailgun_config):
    filename = file_config["filename"]
    url = file_config["url"]
    paused = file_config["paused"]
    previous_hashes = file_config["previous_hashes"]
    status = {"status": "skipped", "reason": "Up-to-date"}

    print(f"Checking for upgrades on {filename}")
    if paused:
        status["status"] = "skipped"
        status["reason"] = "Upgrade paused"
        print(f"Upgrade paused for {filename}")
        return filename, status

    try:
        current_hash = calculate_file_hash(filename)
        print("Current hash is " + current_hash)
    except FileNotFoundError:
        current_hash = None

    try:
        remote_hash, remote_content = calculate_remote_file_hash(url)
        print("Current hash is " + remote_hash)
    except requests.RequestException as e:
        status["status"] = "skipped"
        status["reason"] = f"Error fetching {url}: {e}"
        print(f"Error fetching {url}: {e}")
        return filename, status

    if current_hash == remote_hash:
        status["status"] = "skipped"
        status["reason"] = "Up-to-date"
        print(f"{filename} is up-to-date.")
    else:
        with open(filename, "wb") as f:
            f.write(remote_content)

        # Add current hash to old hashes
        previous_hashes.append(current_hash)

        status["status"] = "completed"
        status["reason"] = "File updated"
        print(f"{filename} updated.")

        return filename, status


def main():
    config = load_config()
    mailgun_config = config["mailgun"]
    files_config = config["files"]
    statuses = {}

    for file_config in files_config:
        filename, status = upgrade_file(file_config)
        statuses[filename] = status

    hostname = socket.gethostname()
    email_subject = f"Upgrade Status on {hostname}"
    email_body = "Upgrade status report:\n\n"
    upgrades_found = False

    for filename, status in statuses.items():
        if status['status'] == 'completed':
            upgrades_found = True
            email_body += f"Filename: {filename}\n"
            email_body += f"Status: {status['status']}\n"
            email_body += f"Reason: {status['reason']}\n\n"

    if upgrades_found:
        send_email(mailgun_config['api_key'], mailgun_config['domain'], mailgun_config['email'],
                   email_subject, email_body)

if __name__ == "__main__":
    main()
