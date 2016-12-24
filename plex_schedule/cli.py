import datetime
import logging
import operator
import os
import pprint
import sys

from plexapi import myplex, server
import click
import IPython
import yaml

from plex_schedule import db


log = logging.getLogger(__name__)


def get_config(home=None):
    if not home:
        home = get_home()

    config_path = os.path.join(home, 'config.yml')
    if not os.path.exists(config_path):
        log.info("Config '%s' does not exist!", config_path)
        return

    # todo: cache this?
    log.info("Loading config from %s", config_path)
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_home():
    return os.environ.get('PLEX_SCHEDULE_HOME', os.path.expanduser('~/.plex_schedule'))


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
    default=get_home,
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

    # stdout is kept clean so we can do things like `plex-schedule foo >file_without_logs`
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
        # TODO: handle cleaning this up if it gets interrupted
        bootstrap(ctx)

    # TODO: run database migraitons if necessary

    ctx.obj['config_dict'] = get_config(home)

    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


def bootstrap(ctx):
    db_session = ctx.obj['db_session']
    home = ctx.obj['home']
    schedule_db = ctx.obj['schedule_db']

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

    db_path = os.path.join(home, 'plex_schedule.db')
    if not os.path.exists(db_path):
        log.info("Creating database: %s", schedule_db)
        db.Base.metadata.create_all(schedule_db)

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
        raise ctx.fail("Config not found. Data directory corrupt")

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
    config_dict = ctx.obj['config_dict']

    try:
        plex_account = get_plex_account(config_dict['plex_user'], config_dict['plex_pass'])
    except KeyError:
        pass

    plex_server = get_plex_server_with_token(config_dict['plex_baseurl'], config_dict['plex_token'])

    shell_vars = globals().copy()
    shell_vars.update(locals())

    # todo: is importing readline like this needed with ipython?
    try:
        import readline  # noqa
    except ImportError:
        log.info("install readline for up/down/history in the console")

    log.info(pprint.pformat(shell_vars))

    IPython.embed()


@cli.command('create_playlist')
@click.option('-e', 'episode_num', '--episode', default=0)
@click.option('-l', '--limit', default=None, type=int)
@click.option('-n', '--show-name', help='if none given, defaults to all unwatched shows')
@click.option('-s', '--section', default='TV Shows')  # TODO: prompt this dynamically based on the server
@click.option('start_time', '--start', default=None, type=int)
@click.option('stop_time', '--stop', default=None, type=int)
@click.option('--only-unwatched', default=False, is_flag=True)
@click.pass_context
def create_playlist_command(ctx, episode_num, limit, only_unwatched, section, show_name, start_time, stop_time):
    config_dict = ctx.obj['config_dict']

    for line in create_playlist(
        episode_num=episode_num,
        limit=limit,
        plex_baseurl=config_dict['plex_baseurl'],
        plex_token=config_dict['plex_token'],
        section=section,
        show_name=show_name,
        start_time=start_time,
        stop_time=stop_time,
        only_unwatched=only_unwatched
    ):
        click.echo(line)


def create_playlist(
    plex_baseurl,
    plex_token,
    section,
    episode_num=None,
    limit=None,
    show_name=None,
    start_time=None,
    stop_time=None,
    only_unwatched=True,
):
    if stop_time:
        assert stop_time > start_time

    plex_server = get_plex_server_with_token(plex_baseurl, plex_token)

    # TODO: reduce copypasta here
    if show_name:
        show = plex_server.library.section(section).get(show_name)
        if only_unwatched:
            episodes = show.unwatched()
        else:
            episodes = show.episodes()
    else:
        # search is limited to 10 results
        # shows = plex_server.library.section(section).search(unwatched=True)
        # TODO: this should work, but plexapi doesn't seem to support it
        # shows = plex_server.library.section(section).unwatched()
        shows = plex_server.library.section(section).all()

        episodes = []
        for show in shows:
            if only_unwatched:
                show_eps = show.unwatched()
            else:
                show_eps = show.episodes()

            if not show_eps:
                continue

            log.debug("episodes of %s: %s", show_eps[0].show().title, show_eps)

            # instead of marking watched in plex, just limit us to one per show
            episodes.append(show_eps[0])

        start_time = start_time or 0
        stop_time = stop_time or 0

    print("start_time: %s", start_time)
    print("stop_time: %s", stop_time)

    if episode_num:
        episodes = [episodes[episode_num]]

    # fix sorting
    for episode in episodes:
        if episode.originallyAvailableAt == '__NA__':
            episode.originallyAvailableAt = episode.addedAt

    # TODO: fallback to index after fixing bug in plexapi
    episodes.sort(key=operator.attrgetter("originallyAvailableAt"))

    if limit:
        episodes = episodes[:limit]

    # TODO: is originallyAvailableAt the airdate?
    for episode in episodes:
        if start_time is None:
            # TODO: can we check if there is a current status already set?
            ep_start_time = click.prompt("start time (negative to skip):", default=0)
            if ep_start_time < 0:
                continue
        else:
            ep_start_time = start_time

        if stop_time is None:
            ep_stop_time = click.prompt("end time (or 0 for the whole episode):", default=0, type=int)
        else:
            ep_stop_time = stop_time

        if ep_stop_time:
            assert ep_stop_time > ep_start_time
            assert ep_stop_time <= episode.duration

            runtime = ep_stop_time - ep_start_time
        else:
            runtime = episode.duration - ep_start_time

        # better to use offset than "EXTVLCOPT:start-time"
        episode_url = episode.getStreamURL(offset=ep_start_time)

        yield "#{runtime}, {show} - {index} {title} ({airdate})".format(
            airdate=episode.originallyAvailableAt,
            index=episode.index,
            runtime=runtime,
            show=episode.show().title,
            title=episode.title,
        )

        if ep_stop_time:
            # subtract the start time because we the start offset is in the stream url
            yield "#EXTVLCOPT:stop-time={}".format(ep_stop_time - ep_start_time)

        yield episode_url


if __name__ == '__main__':
    cli()
