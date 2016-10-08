"""
I think rather than trying to be abstract in how to mark things unwatched, just be exact and have a few types.

1. Watch a movie once a year (with an x% chance?). Ex: Independence Day
2. Watch X movies out of a category every year (remember when last watched so we cycle through everything). Ex: Christmas movies
3. Mark an episode of an old series unwatched X years after it first aired


Independence Day (~1 week before every 4th of July)
Groundhog Day (every leap day)

"""
import datetime
import logging

from sqlalchemy import (
    Boolean,
    Column,
    create_engine,
    Date,
    ForeignKey,
    Integer,
    orm,
    String,
)
from sqlalchemy.ext.declarative import declarative_base


log = logging.getLogger(__name__)

Base = declarative_base()

Session = orm.sessionmaker()

DEFAULT_SHOW_SECTION = 'TV Shows'  # todo: make this configurable per server
DEFAULT_MOVIE_SECTION = 'Movies'  # todo: make this configurable per server. maybe per item?


def add_years(d, add_years, keep_leap_day=True, max_recurse=5):
    """Add `add_years` years to date `d`.

    Return a date that's `add_years` years after the date (or datetime)
    object `d`. Return the same calendar date (month and day) in the
    destination year, if it exists.

    If it does not exist, and `keep_leap_day` is True keep advancing the year
    until the next leap year.

    Otherwise, use the following day (thus changing February 29 to March 1).
    """
    try:
        return d.replace(year=d.year + add_years)
    except ValueError:
        if keep_leap_day:
            if max_recurse < 1:
                # todo: is this worth having?
                raise RuntimeError("Unable to find a future leap year!")

            log.debug("Keeping leap day")
            return add_years(d, add_years + 1, keep_leap_day=keep_leap_day, max_recurse=max_recurse - 1)
        else:
            log.debug("Next year is a leap day. Advancing 1 day")
            return d + (datetime.date(d.year + add_years, 1, 1) - datetime.date(d.year, 1, 1))


def get_db(db_uri='sqlite:///:memory:'):
    # todo: allow args here to customize location and enable echo only with debug
    engine = create_engine(db_uri, echo=False)
    Session.configure(bind=engine)
    return engine


class MarkUnwatchedAction(Base):
    __tablename__ = 'mark_unwatched_action'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    section = Column(String, nullable=True)
    date = Column(Date, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)

    action = Column(String(50))
    __mapper_args__ = {
        'polymorphic_identity': 'mark_unwatched',
        'polymorphic_on': action
    }

    def __str__(self):
        return self.name

    def get_library(self, plex_server):
        if self.section:
            lib = plex_server.library.section(self.section)
            lib.friendlyName = '%s:%s' % (plex_server.friendlyName, lib.title)
        else:
            lib = plex_server.library
            lib.friendlyName = plex_server.friendlyName

        return lib

    def get_item(self, plex_server):
        library = self.get_library(plex_server)
        try:
            log.debug("Searching for '%s' in '%s'", self.name, library.friendlyName)
            return library.get(self.name)
        except Exception:
            log.error("Unable to find '%s' in '%s'", self, library.friendlyName)
            return

    def act(self, plex_server, **kwargs):
        if self.completed:
            log.debug("Not acting. '%s' is already completed.", self)
            return (False, None)

        # todo: how should we handle leap days? ground hog day should skip if not leap day,
        #       but shows that happened to air that day should still show

        if self.date > datetime.date.today():
            log.debug("Not acting. '%s' is not due yet.", self)
            return (False, None)

        # time to act!

        item = self.get_item(plex_server)
        if not item:
            # todo: add this to a download list automatically
            return (False, None)

        try:
            # todo: include the section name in the log?
            log.info("Marking '%s' unwatched on '%s'", self, plex_server.friendlyName)
            # todo: global option for a dry run?
            item.markUnwatched()
        except Exception:
            # todo: include the section name in the log?
            log.exception("Unable to mark '%s' unwatched on '%s'", self, plex_server.friendlyName)
        else:
            self.completed = True

        return self.completed, item


class MarkUnwatchedAnuallyAction(MarkUnwatchedAction):
    __tablename__ = 'mark_unwatched_anually'

    id = Column(Integer, ForeignKey('mark_unwatched_action.id'), primary_key=True)
    every_x_years = Column(Integer, default=1, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'mark_unwatched_anually',
    }

    def act(self, plex_server, db_session, **kwargs):
        completed, item = super(MarkUnwatchedAnuallyAction, self).act(plex_server, section=DEFAULT_MOVIE_SECTION)

        if completed:
            # todo: this is error prone if we add new columns. figure out something more reliable
            next_action = self.__class__(
                name=self.name,
                date=add_years(self.date, self.every_x_years, keep_leap_day=True),
                completed=False,
                every_x_years=self.every_x_years,
            )
            log.info(
                "Queued next play of '%s' on %s",
                next_action,
                next_action.date,
            )
            db_session.add(next_action)

        return (completed, item)


class MarkSeriesUnwatchedDailyAction(MarkUnwatchedAction):
    __tablename__ = 'mark_series_unwatched_daily'

    id = Column(Integer, ForeignKey('mark_unwatched_action.id'), primary_key=True)
    episode_num = Column(Integer, default=0)
    every_x_days = Column(Integer, default=7, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'mark_series_unwatched_daily',
    }

    def __str__(self):
        if hasattr(self, '_plex_item'):
            i = self._plex_item
            return "{} - S{}E{} - {}".format(
                self.name,
                str(i.seasonNumber).zfill(2),
                str(i.index).zfill(2),
                i.title,
            )
        else:
            return "{} #{}".format(self.name, self.episode_num)

    def get_series_episodes(self, plex_server):
        library = self.get_library(plex_server)

        try:
            log.debug(
                "Searching for '%s' in '%s'",
                self.name, library.friendlyName,
            )
            series = library.get(self.name)
        except Exception:
            # todo: automatically add this to a download list?
            log.error(
                "'%s' not found in '%s'",
                self.name, library.friendlyName,
            )
            return

        return series.episodes()

    def get_item(self, plex_server, episode_num=None):
        # todo: can we do this more efficiently? do we really need to get all of them?
        episodes = self.get_series_episodes(plex_server)

        if episode_num is None:
            episode_num = self.episode_num

        try:
            episode = episodes[episode_num]
        except IndexError:
            return False

        if self.episode_num == episode_num:
            self._plex_item = episode

        return episode

    def act(self, plex_server, db_session, **kwargs):
        if self.episode_num > 0:
            previous_episode = self.get_item(plex_server, self.episode_num - 1)

            log.debug("previous_episode: %r", previous_episode)
            if not previous_episode:
                raise RuntimeError("Something went wrong fetching previous episode")

            if not previous_episode.isWatched:
                self.get_item(plex_server)  # fetch here for prettier logging
                log.info("Not touching '%s' because previous episode has not been watched", self)
                return (False, None)

        completed, item = super(MarkSeriesUnwatchedDailyAction, self).act(plex_server)

        if completed:
            next_episode_num = self.episode_num + 1
            next_episode = self.get_item(plex_server, next_episode_num)
            log.debug("next_episode: %r", next_episode)

            if not next_episode:
                # todo: send notification that the last episode is queued
                log.info(
                    "'%s' has no more episodes",
                    self.name,
                )
            else:
                # todo: this is error prone if we add new columns. figure out something more reliable
                next_action = self.__class__(
                    name=self.name,
                    episode_num=next_episode_num,
                    section=self.section,
                    date=self.date + datetime.timedelta(days=self.every_x_days),
                    completed=False,
                    every_x_days=self.every_x_days,
                )
                next_action._plex_item = next_episode  # todo: this is awkward. use a real cache

                log.info(
                    "Queued next play of '%s' on %s",
                    next_action,
                    next_action.date,
                )

                db_session.add(next_action)

        return (completed, item)
