import datetime
import logging
import netrc
import os
import sys

from plexapi import myplex
import click
import yaml

from plex_schedule import db


log = logging.getLogger(__name__)


@click.group()
@click.option(
    "--home",
    default=lambda: os.environ.get('PLEX_SCHEDULE_HOME', os.path.expanduser('~/.plex_schedule')),
    type=click.Path(resolve_path=True),
)
@click.pass_context
def cli(ctx, home):
    # todo: setup varying logger verbosity levels
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    # make the third party loggers quieter
    logging.getLogger('plexapi').setLevel(100)  # disable this logger
    logging.getLogger('requests').setLevel(logging.WARNING)

    if not os.path.exists(home):
        log.debug("Creating plex_schedule directory: %s", home)
        os.makedirs(home)
        os.chmod(home, 0700)

    os.environ['PLEX_SCHEDULE_HOME'] = home

    db_path = os.path.join(home, 'plex_schedule.db')
    schedule_db = db.get_db('sqlite:///%s' % db_path)

    ctx.obj = db_session = db.Session()  # do this after calling get_db since get_db configures Session

    if not os.path.exists(db_path):
        log.info("Creating database: %s", schedule_db)
        db.Base.metadata.create_all(schedule_db)

        # todo: do bootstrapping of the database properly. maybe with a simple flat file format
        db_session.add(
            db.MarkUnwatchedAnuallyAction(
                name='Independence Day',
                date=datetime.date(year=2016, month=6, day=30),  # a few days before July 1
                section=db.DEFAULT_MOVIE_SECTION,
                every_x_years=1,
            )
        )
        db_session.add(
            db.MarkUnwatchedAnuallyAction(
                name='V for Vendetta',
                date=datetime.date(year=2016, month=11, day=1),  # a few days before Nov 5
                section=db.DEFAULT_MOVIE_SECTION,
                every_x_years=2,
            )
        )

        db_session.add(
            db.MarkSeriesUnwatchedDailyAction(
                name='Plebs',
                date=datetime.date.today(),
                section=db.DEFAULT_SHOW_SECTION,
                every_x_days=7,
            )
        )

        db_session.commit()


@cli.command()
@click.option('--server', prompt=True)
@click.pass_context
def bootstrap(ctx):
    config_dict = {}

    # todo: prompt for token or user and password
    token = user = password = None
    if user and password:
        log.info("Connecting to MyPlex as %s...", user)
        account = myplex.MyPlexAccount.signin(user, password)
        log.debug("account.email: %s", account.email)

        config_dict['plex_email'] = account.email

        token = NotImplemented

    config_dict['token'] = token

    # todo: write config dict
    # todo: set mode on the config

    click.echo(yaml.dumps(config_dict))


@cli.command()
@click.option('--server')
@click.pass_context
def cron(ctx, server):
    log.debug("hello, cron!")

    db_session = ctx.obj

    # todo: attempt to migrate the database

    # todo: do simple yaml config instead
    netrc_key = 'plex_schedule'
    if server:
        # todo: loop over all the servers if not server
        netrc_key += '_' + server
    user, _, password = netrc.netrc().authenticators(netrc_key)

    actions = []

    actions += db_session.query(db.MarkUnwatchedAction) \
        .filter_by(completed=False) \
        .filter(db.MarkUnwatchedAction.date <= datetime.date.today()) \
        .order_by(db.MarkUnwatchedAction.date) \
        .all()

    if not actions:
        log.info("No actions due")

        # todo: how should we handle movies?
        #       maybe automatically queue stuff for download if nothing to watch?

        currently_unwatched_show_hours = 0  # todo: actually do this
        if currently_unwatched_show_hours > 5:
            log.info("There are enough shows already unwatched. Exiting")
            return

        log.info("Checking for future actions...")
        # todo: what should the limit on this be?
        actions += db_session.query(db.MarkSeriesUnwatchedDailyAction) \
            .filter_by(completed=False) \
            .order_by(db.MarkSeriesUnwatchedDailyAction.date) \
            .limit(10) \
            .all()

        if not actions:
            log.info("Still no actions to take. I guess you should go outside")
            return

    log.info("Found %d action(s) to process!", len(actions))
    log.debug("actions: %s", actions)

    # todo: use the token instead
    log.info("Connecting to MyPlex as %s...", user)
    account = myplex.MyPlexAccount.signin(user, password)
    log.debug("account.email: %s", account.email)

    log.info("Connecting to %s as %s...", server, account.username)
    # todo: can we check the local IPs first?
    plex_server = account.resource(server).connect()
    log.debug("plex_server: %s", plex_server)

    # even though it is generally bad to commit in a loop, we call out to
    # external apis and need some atomicity. we also aren't doing this at giant scale
    actions_taken = 0
    for a in actions:
        try:
            action_taken, _ = a.act(plex_server, db_session=db_session)
            actions_taken += action_taken
        except:
            log.exception("Rolling back!")
            # Is this a legit use of a bare except?!
            db_session.rollback()
            ctx.fail("Something went wrong!")
        else:
            log.info("Saving...")
            db_session.commit()

    # todo: only do this if in debug mode
    # log.info("interactive time!")
    # import ipdb; ipdb.set_trace()  # noqa

    log.info("Completed %d/%d actions", actions_taken, len(actions))


@cli.command()
@click.option('--server', default=None)
@click.pass_context
def shell(ctx, server):
    plex_server = NotImplemented

    log.info(plex_server)
    raise NotImplemented("Open an interactive shell with the server ready")

"""
todo:
    select a series and offset it from today or from some arbitrary day
    select a movie and mark it unwatched every year around a given date (independence day always a week before july 4)
    mark any tv that aired or movie that released X years ago as unwatched if they weren't watched recently

"""


if __name__ == '__main__':
    cli()
