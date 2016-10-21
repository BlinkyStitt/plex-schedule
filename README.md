Plex Schedule

# Quick Setup with Docker

1. Install Docker from https://www.docker.com/

2. Run the following commands in your terminal:
```bash
docker run -v ./data:/data --rm bwstitt/plex_schedule bootstrap
docker run -v ./data:/data --rm bwstitt/plex_schedule cron
```

3. Then add that last cron command to your crontab


# Developing

## Developing Without Docker

```bash
virtualenv -p python3 .pyenv
. .pyenv/bin/activate
pip install -U -r requirements.txt -e .
plex-schedule --help
```

Upgrading requirements:

```bash
pip install pip-tools
pip-compile requirements.in
pip install -U -r requirements.txt -e .
```

## Developing with Docker

```bash
docker build -t bwstitt/plex_schedule
```


# Todo:

 - [ ] better name
 - [ ] how do dev requirements work with pip tools? and how should pip tools track its own version?
 - [ ] pip-sync instead of pip install?
 - [ ] Ctrl+C while plex is connecting breaks. i dont think their threading likes it
 - [ ] better log format for human readability
 - [ ] document using the Dockerfile
 - [ ] upgrade requirements by using pip-tools inside docker
 - [ ] command for setting up crontab
 - [ ] use pip-sync instead of pip install


# Authors

- Bryan Stitt <bryan@stitthappens.com>


# License

The MIT License (MIT)
Copyright (c) 2015 Bryan Stitt

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
