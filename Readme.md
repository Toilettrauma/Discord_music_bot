# Discord music bot (RU)
## Table of Contents
* [Features](#features)
* [Using](#using)


## Features
Play music in channels with ANSI queue and buttons
* equalizer (needs to be improved)
* some settings (no multiguild)

## Using
1. (Optional) create venv
```
python -m venv venv
venv\Scripts\activate
```
2. Install all requirements
```
pip install -r requirements.txt
```
3. (Optional) place `cookies.txt` for youtube_dl (NETSCAPE)
4. (Optional) run `ydl_patch.py` in PATCH folder. Required to play music from youtube.com
5. Rename `Secrets.py.placeholder` to `Secrets.py` and fill it with your data
6. Run `Bot.py`