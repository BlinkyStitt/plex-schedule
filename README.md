Developing:

  virtualenv -p python3 .pyenv
  . .pyenv/bin/activate
  pip install -U -r requirements.txt -e .


Upgrading requirements:

  pip install pip-tools
  pip-compile requirements.in
  pip install -U -r requirements.txt -e .


Todo:
 - how do dev requirements work with pip tools? and how should pip tools track its own version?
 - pip-sync instead of pip install?
 - Ctrl+C while plex is connecting breaks. i dont think their threading likes it
 - better log format for human readability