#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import json
import os
import pickle
import random
import time
import twitter


# Path where the script and config files are located
PATH = os.path.dirname(os.path.realpath(__file__))
MIN_FOLLOWERS_FOR_REPLY = 200
SLEEP_BETWEEN_RATE_LIMIT_ERROR = datetime.timedelta(minutes=1)
MAX_WAIT_FOR_OPERATION = datetime.timedelta(minutes=20)

def _update_replied_users(already_replied):
    with open(os.path.join(PATH, 'already_replied.bin'), 'wb') as dst:
        pickle.dump(already_replied, dst)


def _safe_search(api, query):
    """
    Safe method to retrieve the results of a search query (sorted by recent, in
    Spanish, only in Spain, up to 100).
    This method will keep trying if the rate-limit is exceeded and only after
    having tried for MAX_WAIT_FOR_OPERATION will it throw. If the operation
    fails because of a non-rate-limit-exceeded error, this method will throw an
    exception.
    This method is necessary because sleep_on_rate_limit seems to be buggy in
    twitter-version 3.3.
    """
    first_attempt = datetime.datetime.now()

    while True:
        try:
            return api.GetSearch(query,
                                 lang='es',
                                 geocode=(40.416775, -3.703790, '600km'),
                                 result_type='recent',
                                 count=100)

        except twitter.error.TwitterError as e:
            if (not isinstance(e.message, dict)
                    or 'code' not in e.mesage
                    or e.message['code'] != 88):
                # It is not a rate-limit exceeded error, re-raise it
                raise e

            now = datetime.datetime.now()
            if now >= first_attempt + MAX_WAIT_FOR_OPERATION:
                print('Failed to search for query {} after {}'.format(
                    query, MAX_WAIT_FOR_OPERATION))
                raise e

            # We have gotten a "rate-limit exceeded" error but have not yet
            # reached the waiting limit
            time.sleep(SLEEP_BETWEEN_RATE_LIMIT_ERROR.seconds)


def _safe_reply(api, status, in_reply_to):
    """
    Safe method to reply to a given tweet with the specified status.
    This method will keep trying if the rate-limit is exceeded and only after
    having tried for MAX_WAIT_FOR_OPERATION will it throw.
    If the operation fails because of a 'Duplicate status' error, it is a no-op
    and does not throw.
    If the operation fails because of a non-rate-limit-exceeded error, this
    method will throw an exception.
    This method is necessary because sleep_on_rate_limit seems to be buggy in
    twitter-version 3.3.
    """
    first_attempt = datetime.datetime.now()

    while True:
        try:
            api.PostUpdate(
                status,
                in_reply_to_status_id=in_reply_to)

        except twitter.error.TwitterError as e:
            if (not isinstance(e.message, dict)
                    or 'code' not in e.mesage
                    or e.message['code'] not in (88, 187)):
                # It is not a rate-limit exceeded  or duplicate status error,
                # re-raise it
                raise e

            if e.message['code'] == 187:
                # Duplicate status, log an error and return
                print('Failed to reply to tweet with ID {} with status: \"{}\"'
                      '- Duplicate status'.format(in_reply_to, status))
                return

            now = datetime.datetime.now()
            if now >= first_attempt + MAX_WAIT_FOR_OPERATION:
                print('Failed to post reply to tweet with ID {} after {}'
                      .format(screen_name, MAX_WAIT_FOR_OPERATION))
                raise e

            # We have gotten a "rate-limit exceeded" error but have not yet
            # reached the waiting limit
            time.sleep(SLEEP_BETWEEN_RATE_LIMIT_ERROR.seconds)


def main():
    # Get consumer key and secret
    with open(os.path.join(PATH, 'secrets.key'), 'r') as keys:
        contents = [l.strip() for l in keys.readlines() if l.strip()]
        consumer_key = contents[0]
        consumer_secret = contents[1]

    # Get access token
    with open(os.path.join(PATH, 'access_token.bin'), 'rb') as src:
        access_token = pickle.load(src)

    # Load the queries and the replies
    with open(os.path.join(PATH, 'replies.json'), encoding='utf-8') as src:
        queries_dict = json.loads(src.read())

    try:
        with open(os.path.join(PATH, 'already_replied.bin'), 'rb') as src:
            loaded_already_replied = pickle.load(src)
            already_replied = {}
            # Always use lower-case for convenience (in case someone manually
            # modifies the list and includes upper case names)
            for user, date in loaded_already_replied.items():
                already_replied[user.lower()] = date
    except IOError:
        already_replied = {}

    # Load ignored accounts
    with open(os.path.join(PATH, 'ignored_accounts.txt'), 'r') as src:
        # Always use lower-case for convenience (in case someone manually
        # modifies the list and includes upper case names)
        ignored_accounts = [e.strip().lower() for e in src.readlines()]

    # Load the number of replies per query
    with open(os.path.join(PATH, 'replies_per_query.cfg'), 'r') as src:
        replies_per_query = int(src.readline().strip())

    # Create a Twitter client
    api = twitter.Api(
        consumer_key,
        consumer_secret,
        access_token['oauth_token'.encode('utf-8')].decode('utf-8'),
        access_token['oauth_token_secret'.encode('utf-8')].decode('utf-8'),
        sleep_on_rate_limit=True)
    self_user = api.VerifyCredentials()

    if not self_user:
        print('Failed to authenticate!')
        return

    # Add ourselves to the list of ignored accounts to avoid replying to
    # ourselves
    if self_user.screen_name.lower() not in ignored_accounts:
        ignored_accounts.append(self_user.screen_name.lower())

    today = datetime.datetime.now().date()
    a_week_ago = today - datetime.timedelta(days=7)

    for user, date in list(already_replied.items()):
        if date < a_week_ago:
            del already_replied[user]
            _update_replied_users(already_replied)

    for query, replies in queries_dict.items():
        # Search for recent tweets in Spanish which have been written 600km
        # around Madrid (which roughly means 'Spain')
        results = _safe_search(api, query)

        to_ignore = list(already_replied.keys()) + ignored_accounts

        # Exclude tweets from users who we have already replied to in the last
        # week, users we want to actively ignore and RTs
        results = [r for r in results
                   if (r.user.screen_name.lower() not in to_ignore
                       and not r.retweeted_status)]

        # Reply to the first 'replies_per_query' tweets
        replied = 0
        for to_reply in results:
            followers_count = to_reply.user.followers_count

            if (to_reply.user.screen_name.lower() in already_replied
                    or followers_count < MIN_FOLLOWERS_FOR_REPLY):
                continue

            # The user has not been interacted with for a few days and has
            # enough followers. Pick a reply at random
            response = random.choice(replies)
            _safe_reply(api,
                        '@%s %s' % (to_reply.user.screen_name, response),
                        to_reply.id)
            already_replied[to_reply.user.screen_name.lower()] = today
            _update_replied_users(already_replied)
            replied += 1

            if replied >= replies_per_query:
                break


if __name__ == '__main__':
    main()