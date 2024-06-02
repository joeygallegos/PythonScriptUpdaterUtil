import json
import hashlib
import os
import requests
import subprocess


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

    print(f"Checking for upgrades on {filename}")
    if paused:
        print(f"Upgrade paused for {filename}")
        return False

    try:
        current_hash = calculate_file_hash(filename)
        print("Current hash is " + current_hash)
    except FileNotFoundError:
        current_hash = None

    try:
        remote_hash, remote_content = calculate_remote_file_hash(url)
        print("Current hash is " + remote_hash)
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return False

    if current_hash == remote_hash:
        print(f"{filename} is up-to-date.")
        return False
    else:
        with open(filename, "wb") as f:
            f.write(remote_content)

        # Add current hash to old hashes
        previous_hashes.append(current_hash)

        send_email(
            mailgun_config["api_key"],
            mailgun_config["domain"],
            mailgun_config["email"],
            f"File Updated: {filename}",
            f"The file {filename} was updated to a new version.",
        )
        print(f"{filename} updated.")
        return True


def main():
    config = load_config()
    mailgun_config = config["mailgun"]
    files_config = config["files"]

    for file_config in files_config:
        upgrade_file(file_config, mailgun_config)


if __name__ == "__main__":
    main()
