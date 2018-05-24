#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import json
import pickle
import twitter
import datetime
import random


MIN_FOLLOWERS_FOR_REPLY = 200

def main():
    # Path where the script and config files are located
    path = os.path.dirname(os.path.realpath(__file__))

    # Get consumer key and secret
    with open(os.path.join(path, 'secrets.key'), 'r') as keys:
        contents = [l.strip() for l in keys.readlines() if l.strip()]
        consumer_key = contents[0]
        consumer_secret = contents[1]

    # Get access token
    with open(os.path.join(path, 'access_token.bin'), 'rb') as src:
        access_token = pickle.load(src)

    # Load the queries and the replies
    with open(os.path.join(path, 'replies.json')) as src:
        queries_dict = json.loads(src.read())

    try:
        with open(os.path.join(path, 'already_replied.bin'), 'rb') as src:
            already_replied = pickle.load(src)
    except IOError:
        already_replied = {}

    # Load ignored accounts
    with open(os.path.join(path, 'ignored_accounts.bin'), 'rb') as src:
        ignored_accounts = pickle.load(src)

    # Load the number of replies per query
    with open(os.path.join(path, 'replies_per_query.cfg'), 'r') as src:
        replies_per_query = int(src.readline().strip())

    # Create a Twitter client
    api = twitter.Api(
        consumer_key,
        consumer_secret,
        access_token['oauth_token'.encode('utf-8')].decode('utf-8'),
        access_token['oauth_token_secret'.encode('utf-8')].decode('utf-8'))
    api.VerifyCredentials()

    today = datetime.datetime.now().date()
    a_week_ago = today - datetime.timedelta(days=7)

    for user, date in list(already_replied.items()):
        if date < a_week_ago:
            del already_replied[user]

    for query, replies in queries_dict.items():
        # Search for recent tweets in Spanish which have been written 600km
        # around Madrid (which roughly means 'Spain')
        results = api.GetSearch(query,
                                lang='es',
                                geocode=(40.416775, -3.703790, '600km'),
                                result_type='recent',
                                count=100)

        # Exclude tweets from users who we have already replied to in the last
        # week (and from ourselves!) and RTs
        results = [r for r in results
                   if (
                       r.user.screen_name not in list(already_replied.keys())
                       + ignored_accounts)
                   and (not r.retweeted_status)]

        # Reply to the first 'replies_per_query' tweets
        replied = 0
        for to_reply in results:
            if (to_reply.user.screen_name not in already_replied
                    and len(api.GetFollowers(
                        screen_name=to_reply.user.screen_name,
                        total_count=200)) >= MIN_FOLLOWERS_FOR_REPLY):
                # Pick a reply at random
                response = random.choice(replies)
                api.PostUpdate(
                    '@%s %s' % (to_reply.user.screen_name, response),
                    in_reply_to_status_id=to_reply.id)
                already_replied[to_reply.user.screen_name] = today
                replied += 1

                if replied >= replies_per_query:
                    break

        # Update the already_replied database
        with open(os.path.join(path, 'already_replied.bin'), 'wb') as dst:
            pickle.dump(already_replied, dst)


if __name__ == '__main__':
    main()
