# Plex Schedule

Automatically mark shows unwatched on a schedule.

**IMPORTANT!** This is not yet ready for use. The basics work, but there is a lot left. Some of the commands in the README are more aspirational than anything right now and do not yet work.

I wrote this to fix a few problems:

1. I always want to watch some movies every year and don't want to have to search for them
2. It is too easy to binge watch television. Sometimes it can be fun but in general I'd rather spread out my telivison watching and do other things.
3. I don't want to have to choose between a large selection of media; I only really want 2 to 4 choices of what to watch at a time. If I don't like any of my choices, maybe I shouldn't be watching TV or maybe I should skip the shows entirely and go do something else.
4. When I come back from vacation I don't want too many unwatched shows piled up.

You tell this tool what movies you want to watch anually and what shows you want to have marked watched when you have less than a configurable number of hours (4 by default) of unwatched shows in plex.

For example with movies, you might want to watch "Independence Day" every 4th of July.

For example with shows, instead of marking an entire series unwatched, you tell this tool to add it to its schedule. It will then mark the first episode of the series unwatched. It will not mark the next episode in the series unwatched until you've watched that first epise and at least a configurable number of days (1 by default) has passed.


# Quick Setup with Docker

1. Install Docker from https://www.docker.com/

2. Run the following commands in your terminal:
```bash
docker run -v plex_schedule_data:/data --rm -it bwstitt/plex_schedule
```

3. Then add a similar (but non-interactive) command to your crontab:
```
0 6 * * *   docker run -v plex_schedule_data:/data --rm bwstitt/plex_schedule
```


# Developing

## Developing Without Docker

```bash
virtualenv -p python3 .pyenv
. .pyenv/bin/activate
pip install -U -r requirements.txt -e .
plex-schedule --help
```

Automatically upgrading requirements.txt:

```bash
pip install pip-tools
pip-compile requirements.in
```

## Developing with Docker

```bash
docker build -t bwstitt/plex_schedule .
```


# Todo:

 * [ ] better name
 * [ ] how do dev requirements work with pip tools? and how should pip tools track its own version?
 * [ ] pip-sync instead of pip install?
 * [ ] Ctrl+C while plex is connecting breaks. i dont think their threading likes it
 * [ ] better log format for human readability
 * [ ] document using the Dockerfile
 * [ ] upgrade requirements by using pip-tools inside docker
 * [ ] command for setting up crontab
 * [ ] use pip-sync instead of pip install
 * [ ] make sure specials get sorted into a series by air date instead of being a special season at the end
 * [ ] how should multiple server support actually work? would it be better to just support easily moving from one server to another rather than updating multiple servers with one run? Probably since multiple runs can easily be setup with seperate configs
 * [ ] select a series and always make it available at a certain time instead of just the next day
 * [ ] take a series as input and mark all the episodes as watched except the oldest unwatched one and then proceed from there
 * [ ] push notification when shows are marked unwatched
 * [ ] push notification when the last show of a season/series is marked unwatched
 * [ ] integrate with sickbeard or an app like that
 * [ ] if a show is added to plex, ahead of where we are watching in a series, mark it watched so we dont get ahead by accident. this is probable to happen if we are catching up with a show that is still on the air


# Authors

- Bryan Stitt <bryan@stitthappens.com>


# License

The MIT License (MIT)
Copyright (c) 2016 Bryan Stitt

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
