## About

SimpleTwitterBot is a very simple tool to automate tweets.

It is designed with Linux systems in mind. After a simple installation, it will
search for the queries you specify and reply with whatever message you decide.
It creates its own entry in `crontab` to be launched with the frequency
specified by the user when installed.

It is hardcoded to only search for tweets in Spanish and from Spain. This can
be changed in `twitterbot.py` by tweaking the `TwitterApi.GetSearch()`
parameters.

## Requirements

- A Linux system.
- Python 3.5 or greater.
- [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/)
- A Twitter account to log into.
- The consumer key and consumer secret of a registered Twitter application (see
  [Twitter Application Management](https://apps.twitter.com/) for more
information).

## Installation
- Create a virtual environment and activate it.
- To install the necessary Python packages, fromm that virtual environment run:

	`pip install -r requirements.txt`
- Fill in the values in `install.cfg` (or create your own copy of the
  configuration file).
- Run `python3 ./install.py <YOUR_CONFIGURATION_FILE>` and follow the
  instructions
