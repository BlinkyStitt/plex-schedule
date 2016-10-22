import datetime
import functools
import logging
import os
import pprint
import sys
import code

from plexapi import myplex, server
import click
import yaml

from plex_schedule import db


log = logging.getLogger(__name__)


@functools.lru_cache()
def get_config(home):
    config_path = os.path.join(home, 'config.yml')
    if not os.path.exists(config_path):
        log.info("Config does not exist!")
        return

    log.info("Loading config from %s", config_path)
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_plex_account(plex_user, plex_pass):
    log.info("Connecting to MyPlex as %s...", plex_user)
    return myplex.MyPlexAccount.signin(plex_user, plex_pass)


def get_plex_server(plex_account, plex_server_name):
    log.info("Connecting to %s as %s...", plex_server_name, plex_account.username)

    # TODO: can we make it check the local IPs first? the external IP always fails since this is local

    plex_server = plex_account.resource(plex_server_name).connect()
    log.debug("plex_server: %s", plex_server)

    return plex_server


def get_plex_server_with_token(plex_baseurl, plex_token):
    log.info("Connecting to %s...", plex_baseurl)
    return server.PlexServer(plex_baseurl, plex_token)


@click.group(invoke_without_command=True)
@click.option(
    "--home",
    default=lambda: os.environ.get('PLEX_SCHEDULE_HOME', os.path.expanduser('~/.plex_schedule')),
    type=click.Path(resolve_path=True),
)
@click.option(
    "--verbose/--quiet",
    default=None,
)
@click.pass_context
def cli(ctx, home, verbose):
    # TODO: setup varying logger verbosity levels
    if verbose is True:
        log_level = logging.DEBUG
    elif verbose is False:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO
    logging.basicConfig(stream=sys.stderr, level=log_level)

    # make the third party loggers quieter
    logging.getLogger('plexapi').setLevel(100)  # disable this logger
    logging.getLogger('requests').setLevel(logging.WARNING)

    if not os.path.exists(home):
        log.debug("Creating plex_schedule directory: %s", home)
        os.makedirs(home)
        os.chmod(home, 0o700)

    os.environ['PLEX_SCHEDULE_HOME'] = home

    db_path = os.path.join(home, 'plex_schedule.db')
    schedule_db = db.get_db('sqlite:///%s' % db_path)

    # TODO: fail if database does not exist and we aren't bootstrapping?

    ctx.obj = dict(
        db_session=db.Session(),  # do this after calling get_db since get_db configures Session
        schedule_db=schedule_db,
        home=home,
    )

    if not os.path.exists(db_path):
        bootstrap(ctx)

    # TODO: run database migraitons if necessary

    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


def bootstrap(ctx):
    db_session = ctx.obj['db_session']
    home = ctx.obj['home']
    schedule_db = ctx.obj['schedule_db']

    db_path = os.path.join(home, 'plex_schedule.db')
    if not os.path.exists(db_path):
        log.info("Creating database: %s", schedule_db)
        db.Base.metadata.create_all(schedule_db)

    config_dict = {}

    plex_user = click.prompt("Plex Username")
    plex_pass = click.prompt("Plex Password", hide_input=True)

    plex_account = get_plex_account(plex_user, plex_pass)

    log.debug("plex_account.email: %s", plex_account.email)

    config_dict['plex_token'] = plex_account.authenticationToken

    # enumerate the servers and prompt which one they want
    # todo: enforce one of the valid resources is chosen
    available_servers = ", ".join(set((r.name for r in plex_account.resources())))
    config_dict['plex_server'] = click.prompt('Plex server (One of: %s)' % available_servers)

    try:
        plex_server = get_plex_server(plex_account, config_dict['plex_server'])
    except Exception:
        log.exception("Failed connecting to plex server")
        raise ctx.fail("Failed connecting to plex server")

    config_dict['plex_baseurl'] = plex_server.baseurl

    # TODO: write config dict to $home/config.yml with a safe mode since it has credentials in it
    config_path = os.path.join(home, 'config.yml')
    log.info("Saving config to %s", config_path)
    log.debug("Config: %s", pprint.pformat(config_dict))
    with open(config_path, 'wt') as f:
        yaml.dump(config_dict, f, default_flow_style=False)

    if click.confirm("Setup example database?", default=False):
        log.info("Setting up example database...")

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
    else:
        raise NotImplementedError("TODO: prompt for movies and shows to watch")

    db_session.commit()

    log.info("Bootstrap complete")


@cli.command()
@click.pass_context
def run(ctx):
    # TODO: bootstrap

    # TODO: move most of this into smaller, testable functions instead of this monolith

    db_session = ctx.obj['db_session']
    home = ctx.obj['home']

    # TODO: attempt to migrate the database

    # TODO: load the config in the main cli function if it exists and store it on ctx.obj
    config_dict = get_config(home)
    if not config_dict:
        raise ctx.fail(msg="Config not found. Data directory corrupt")

    actions = []

    actions += db_session.query(db.MarkUnwatchedAction) \
        .filter_by(completed=False) \
        .filter(db.MarkUnwatchedAction.date <= datetime.date.today()) \
        .order_by(db.MarkUnwatchedAction.date) \
        .all()

    if not actions:
        log.info("No actions due")

        # TODO: how should we handle movies?
        #       maybe automatically queue stuff for download if nothing to watch?

        currently_unwatched_show_hours = 0  # TODO: actually do this
        if currently_unwatched_show_hours > 5:
            log.info("There are enough shows already unwatched. Exiting")
            return

        log.info("Checking for future actions...")
        # TODO: what should the limit on this be?
        actions += db_session.query(db.MarkSeriesUnwatchedDailyAction) \
            .filter_by(completed=False) \
            .order_by(db.MarkSeriesUnwatchedDailyAction.date) \
            .limit(10) \
            .all()

        if not actions:
            log.info("Still no actions to take. I guess you should go outside")
            return

    log.info("Found %d action(s) to check", len(actions))
    log.debug("actions: %s", actions)

    # plex_account = get_plex_account(config_dict['plex_user'], config_dict['plex_pass'])
    # plex_server = get_plex_server(plex_account, config_dict['plex_server'])
    plex_server = get_plex_server_with_token(config_dict['plex_baseurl'], config_dict['plex_token'])

    # even though it is generally bad to commit in a loop, we call out to
    # external apis so its safer. we also aren't doing this at giant scale
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
            log.debug("Saving...")
            db_session.commit()

    log.info("Completed %d/%d actions", actions_taken, len(actions))


@cli.command()
@click.option('--server', default=None)
@click.pass_context
def shell(ctx, server):
    home = ctx.obj['home']
    schedule_db = ctx.obj['schedule_db']
    db_session = ctx.obj['db_session']

    config_dict = get_config(home)

    plex_account = get_plex_account(config_dict['plex_user'], config_dict['plex_pass'])

    plex_server = get_plex_server_with_token(config_dict['plex_baseurl'], config_dict['plex_token'])

    shell_vars = globals().copy()
    shell_vars.update(locals())

    try:
        import readline  # noqa
    except ImportError:
        log.info("install readline for up/down/history in the console")

    log.info(pprint.pformat(shell_vars))

    # TODO: bpython? ipython? some other shell with tab completion?
    shell = code.InteractiveConsole(shell_vars)
    shell.interact()


if __name__ == '__main__':
    cli()
