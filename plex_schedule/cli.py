import datetime
import logging
import netrc
import os
import sys

from plexapi import myplex
import click

from plex_schedule import db


log = logging.getLogger(__name__)


@click.group()
@click.option(
    "--home",
    default=lambda: os.environ.get('PLEX_SCHEDULER_HOME', '~/.plex_schedule'),
    type=click.Path(resolve_path=True),
)
@click.pass_context
def cli(ctx, home):
    # todo: setup varying logger verbosity levels
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    # make the third party loggers quieter
    logging.getLogger('plexapi').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    if not os.path.exists(home):
        log.info("Creating home directory: %s", home)
        os.makedirs(home)

    db_path = os.path.join(home, 'plex_schedule.db')
    schedule_db = db.get_db('sqlite:///%s' % db_path)

    ctx.obj = db_session = db.Session()  # do this after calling get_db since get_db configures Session

    if not os.path.exists(db_path):
        log.info("Creating database...")
        db.Base.metadata.create_all(schedule_db)

        # todo: do bootstrapping of the database properly. maybe with a simple flat file format
        log.info("Creating example actions...")
        db_session.add(
            db.MarkUnwatchedAnuallyAction(
                name='Independence Day',
                date=datetime.date(year=2016, month=6, day=30),  # a few days before July 1
                section='Movies',
            )
        )
        db_session.add(
            db.MarkUnwatchedAnuallyAction(
                name='V for Vendetta',
                date=datetime.date(year=2016, month=11, day=1),  # a few days before Nov 5
                section='Movies',
            )
        )

        db_session.commit()


@cli.command()
@click.option('--server', prompt=True)
@click.pass_context
def cron(ctx, server):
    log.debug("hello, cron!")

    db_session = ctx.obj

    user, _, password = netrc.netrc().authenticators('plex_scheduler_' + server)

    actions = []

    # todo: use polymorphism on these
    actions += db_session.query(db.MarkUnwatchedAction) \
        .filter_by(completed=False) \
        .filter(db.MarkUnwatchedAction.date <= datetime.date.today()) \
        .all()

    # todo: search for various movie actions

    # todo: search for various show actions

    if not actions:
        log.info("No actions to take")
        return

    log.info("Found %d actions to check", len(actions))

    log.info("Connecting to MyPlex...")
    account = myplex.MyPlexAccount.signin(user, password)
    # todo: check for a token in an auth cache or load password from ~/.netrc

    log.info("Connecting to %s as %s...", server, account)
    plex_server = account.resource(server).connect()
    log.debug("plex_server: %s", plex_server)

    # even though it is generally bad to commit in a loop, we call out to
    # external apis so this will help that. we also aren't doing this at giant scale
    for a in actions:
        try:
            a.act(plex_server, db_session=db_session)
        except:
            log.exception("Rolling back!")
            # Is this a legit use of a bare except?!
            db_session.rollback()
            ctx.fail("Something went wrong!")
        else:
            log.info("Saving...")
            db_session.commit()
            log.info("Done!")

    # todo: only do this if in debug mode
    # log.info("interactive time!")
    # import ipdb; ipdb.set_trace()  # noqa


"""
todo:
    select a series and offset it from today or from some arbitrary day
    select a movie and mark it unwatched every year around a given date (independence day always a week before july 4)
    mark any tv that aired or movie that released X years ago as unwatched if they weren't watched recently

"""


if __name__ == '__main__':
    cli()
