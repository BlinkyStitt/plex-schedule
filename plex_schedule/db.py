"""
I think rather than trying to be abstract in how to mark things unwatched, just be exact and have a few types.

1. Watch a movie once a year (with an x% chance?). Ex: Independence Day
2. Watch X movies out of a category every year (remember when last watched so we cycle through everything). Ex: Christmas movies
3. Mark an episode of an old series unwatched X years after it first aired


Independence Day (~1 week before every 4th of July)
Groundhog Day (every leap day)

"""
from copy import copy
import datetime
import logging
import random

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

DEFAULT_SHOWS_SECTION = 'TV.Shows'  # todo: make this configurable per server
DEFAULT_MOVIE_SECTION = 'Movies'  # todo: make this configurable per server. maybe per item?


def add_years(d, add_years, keep_leap_day=True):
    """Add `add_years` years to date `d`.

    Return a date that's `add_years` years after the date (or datetime)
    object `d`. Return the same calendar date (month and day) in the
    destination year, if it exists. Otherwise if `keep_leap_day` keep advancing
    the yearuse the following day
    (thus changing February 29 to March 1).

    """
    try:
        return d.replace(year=d.year + add_years)
    except ValueError:
        if keep_leap_day:
            log.info("Keeping leap day")
            # todo: do something to make sure we don't recurse forever
            return self.add_years(d, add_years + 1, keep_leap_day=keep_leap_day)
        else:
            log.info("Next year is a leap day. Advancing 1 day")
            return d + (date(d.year + add_years, 1, 1) - date(d.year, 1, 1))


def get_db(db_uri='sqlite:///:memory:'):
    # todo: allow args here to customize location and enable echo only with debug
    engine = create_engine(db_uri, echo=False)
    Session.configure(bind=engine)
    return engine


class MarkUnwatchedAction(Base):
    __tablename__ = 'mark_unwatched_action'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    probability = Column(Integer, default=100, nullable=False)

    action = Column(String(50))
    __mapper_args__ = {
        'polymorphic_identity': 'mark_unwatched',
        'polymorphic_on': action
    }

    def __str__(self):
        return self.name

    def act(self, plex_server, section=None, **kwargs):
        if self.completed:
            log.debug("Not acting. %r is already completed.", self)
            return False

        if random.randint(1, 100) > self.probability:
            log.info("Probability missed. Marking action completed without marking unwatched")
            self.completed = True
            return self.completed

        # todo: how should we handle leap days? ground hog day should skip if not leap day,
        #       but shows that happened to air that day should still show

        if self.date > datetime.date.today():
            log.debug("Not acting. %r is not due yet.", self)
            return False

        # time to act!
        if section is None:
            plex_library = plex_server.library
        else:
            plex_library = plex_server.library.section(section)

        try:
            log.info("Querying plex server for %s in %s", self.name, plex_library)
            item = plex_library.get(self.name)
        except Exception:
            item = None
        if not item:
            log.error("Unable to find %r in %r", self, plex_library)
            return False

        # todo: check that we haven't already watched this in the last X months
        # if we have, mark completed = True and return without marking unwatched

        try:
            log.info("WOULD HAVE MARKED '%s' UNWATCHED", self)
            # item.markUnwatched()
        except Exception:
            log.exception("Unable to mark '%s' unwatched", self)
        else:
            self.completed = True

        return self.completed


class MarkUnwatchedAnuallyAction(MarkUnwatchedAction):
    __tablename__ = 'mark_unwatched_anually'

    id = Column(Integer, ForeignKey('mark_unwatched_action.id'), primary_key=True)
    every_x_years = Column(Integer, default=1, nullable=False)

    section = Column(String, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'mark_unwatched_anually',
    }

    def act(self, plex_server, db_session, **kwargs):
        completed = super(MarkUnwatchedAnuallyAction, self). \
            act(plex_server, section=DEFAULT_MOVIE_SECTION)

        if completed:
            new_date = copy(self.date)
            new_date = add_years(new_date, self.every_x_years)

            new_action = self.__class__(
                name=self.name,
                date=new_date,
                completed=False,
                probability=self.probability,
                every_x_years=self.every_x_years,
            )
            log.info("Created new action: %r", new_action)
            db_session.add(new_action)

        return completed
