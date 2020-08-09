# Reddit streaming for your 'following' users

# Usage

Insert the proper values in praw.ini. See https://praw.readthedocs.io/en/latest/getting_started/quick_start.html for a sample.

When using 2FA, put username/password into praw.ini. After getting a refresh_token on the first run, remove username/password and replace it with refresh_token=XXX

# Installation
```bash
pipx install git+ssh://git@github.com/mikeage/reddit-stalker
reddit-stalker
```
