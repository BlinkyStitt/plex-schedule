# plex_schedule
#

FROM python:3.5-alpine

# since we are using upstream's python image that installs python into /usr/local/bin, its fine to use /usr/local/bin/pip for this. we still use virtualenv for the app code so its all owned by the user
RUN pip3 install --no-cache-dir virtualenv

# create a user
RUN adduser -S plex_schedule

USER plex_schedule
ENV HOME=/home/plex_schedule
WORKDIR /home/plex_schedule
RUN virtualenv ~/pyenv \
 && . ~/pyenv/bin/activate

# install the code in a two step process to keep the cache smarter
ADD requirements.txt /tmp/requirements.txt
RUN . ~/pyenv/bin/activate \
 && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /home/plex_schedule/src/plex_schedule
# todo: i wish copy would keep the user...
USER root
RUN mkdir /data \
 && chown -R plex_schedule:nogroup \
    /data \
    /home/plex_schedule/src

ENV PLEX_SCHEDULE_HOME=/data

# install the app as the user, run the --help once to make sure it works, and create a dir for the data
USER plex_schedule
WORKDIR /home/plex_schedule/src/plex_schedule
RUN . ~/pyenv/bin/activate \
 && pip install --no-cache-dir -r requirements.txt -e . \
 && plex-schedule --help \

# setup volume for the config and database
VOLUME ["/data"]

ENTRYPOINT ["/home/plex_schedule/pyenv/bin/plex-schedule"]
CMD ["--help"]
