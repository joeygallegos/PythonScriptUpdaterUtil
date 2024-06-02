# PythonScriptUpdaterUtil
This Python script allows you to configure a list of files/scripts that need to be checked for updates using Github "raw" URL. You can schedule this update tool using cron or run it manually.

I created this script because I have a library of shell scripts that get frequent tweaks, and I wanted to make sure that those updates got deployed without manual intervention.

## Cron
```shell
0 2 * * * python3 /home/upgrade_tool.py >> upgrade.log
```