from flask import Flask, make_response, render_template, request

from plex_schedule import cli

app = Flask(__name__)


def next_unwatched():
    m3u_lines = cli.create_playlist(
        plex_baseurl=app.config_dict['plex_baseurl'],
        plex_token=app.config_dict['plex_token'],
        limit=1,
        section='TV Shows',
    )

    # the simple video tag doesn't handle nested m3us :(
    # this also means we lose our offset/stop-time
    for line in m3u_lines:
        if line.startswith('#'):
            continue
        return line


@app.route("/")
def index():
    return render_template(
        'index.html',
        next_unwatched=next_unwatched(),
    )


@app.route("/plex.m3u8")
def plex_m3u8():
    section = request.args.get('section', 'TV Shows')
    limit = request.args.get('limit', None)
    show_name = request.args.get('show_name', None)
    start_time = request.args.get('start_time', 0, int)
    stop_time = request.args.get('stop_time', 0, int)
    only_unwatched = request.args.get('only_unwatched', 1, int)  # todo: how does bool work for this?

    if show_name:
        filename_parts = [show_name]
    else:
        filename_parts = [section]

    if only_unwatched:
        filename_parts.append('unwatched')

    filename = '-'.join((
        f.replace('-', '').replace(' ', '').replace('_', '').lower()
        for f in filename_parts
    )) + '.m3u8'

    # TODO: make the route more dynamic and allow customizing the playlist
    m3u_lines = cli.create_playlist(
        plex_baseurl=app.config_dict['plex_baseurl'],
        plex_token=app.config_dict['plex_token'],
        section=section,
        only_unwatched=only_unwatched,
        limit=limit,
        show_name=show_name,
        start_time=start_time,
        stop_time=stop_time,
    )

    response = make_response("\n".join(m3u_lines))
    response.headers["Content-Disposition"] = "attachment; filename={}".format(filename)
    return response


if __name__ == "__main__":
    app.config_dict = cli.get_config()

    # TODO: reload if the config changes
    app.run(debug=True, host='0.0.0.0')
