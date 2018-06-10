# -*- coding: utf-8 -*-

import os
import shutil
import stat
import sys
import oauth2 as oauth
import urllib.parse as urlparse
import pickle

INSTALLATION_DIRECTORY = 'simpletwitter-bot'


def _clean_current_install(install_path):
    old_install = os.path.join(install_path, 'old')
    shutil.rmtree(old_install, ignore_errors=True)
    os.makedirs(old_install, exist_ok=True)

    # Move files to 'old'
    for f in os.listdir(install_path):
        if f != 'old':
            shutil.move(os.path.join(install_path, f),
                        os.path.join(old_install, f))


def _generate_access_token(install_path, keys_file):
    # Get the secret key and token
    with open(os.path.join(keys_file), 'r') as keys:
        contents = [l.strip() for l in keys.readlines() if l.strip()]
        consumer_key = contents[0]
        consumer_secret = contents[1]

    request_token_url = 'https://api.twitter.com/oauth/request_token'
    access_token_url = 'https://api.twitter.com/oauth/access_token'
    authorize_url = 'https://api.twitter.com/oauth/authorize'

    consumer = oauth.Consumer(consumer_key, consumer_secret)
    client = oauth.Client(consumer)

    # Step 1: Get a request token. This is a temporary token that is used for
    # having the user authorize an access token and to sign the request to
    # obtain said access token.
    resp, content = client.request(request_token_url, "GET")
    if resp['status'] != '200':
        raise Exception("Invalid response %s." % resp['status'])

    request_token = dict(urlparse.parse_qsl(content))

    # Step 2: Redirect to the provider. Since this is a CLI script we do not
    # redirect. In a web application you would redirect the user to the URL
    # below.
    print('Introduce PIN from {}?oauth_token={}'.format(
            authorize_url,
            request_token['oauth_token'.encode('utf-8')].decode('utf-8')))

    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can
    # usually define this in the oauth_callback argument as well.
    oauth_verifier = input('PIN: ')

    # Step 3: Once the consumer has redirected the user back to the
    # oauth_callback URL you can request the access token the user has
    # approved.  You use the request token to sign this request. After this is
    # done you throw away the request token and use the access token returned.
    # You should store this access token somewhere safe, like a database, for
    # future use.
    token = oauth.Token(
        request_token['oauth_token'.encode('utf-8')].decode('utf-8'),
        request_token['oauth_token_secret'.encode('utf-8')].decode('utf-8'))
    token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, token)

    resp, content = client.request(access_token_url, "POST")
    access_token = dict(urlparse.parse_qsl(content))

    with open(os.path.join(install_path, 'access_token.bin'), 'wb') as dst:
        pickle.dump(access_token, dst)


def main():
    if len(sys.argv) != 2:
        print('Usage: python3 %s <PATH_TO_CONFIG_FILE>' % sys.argv[0])
        return

    try:
        with open(sys.argv[1], 'r') as input_file:
            content = [l.strip() for l in input_file.readlines()]
    except IOError:
        print('Could not open file %s. Installation cancelled' % sys.argv[1])
        return

    install_path = None
    replies_file = None
    frequency = None
    secrets_file = None
    replies_per_query = None
    venv_path = None
    ignored_accounts = None

    for line in content:
        if not line or line.startswith('#'):
            continue
        if line.startswith('INSTALLATION_DIR:'):
            install_path = line.split(':')[1].strip()
        elif line.startswith('REPLIES_FILE'):
            replies_file = line.split(':')[1].strip()
        elif line.startswith('FREQUENCY:'):
            frequency = line.split(':')[1].strip()
        elif line.startswith('REPLIES_PER_QUERY:'):
            replies_per_query = int(line.split(':')[1].strip())
        elif line.startswith('VIRTUALENV_PYTHON_PATH:'):
            venv_path = line.split(':')[1].strip()
        elif line.startswith('SECRETS_FILE:'):
            secrets_file = line.split(':')[1].strip()
        elif line.startswith('IGNORED_ACCOUNTS:'):
            ignored_accounts = [e.replace(' ', '')
                                for e in line.strip().split(':')[1].split(',')]
        else:
            print('Cannot recognize line: %s' % line)
            print('Installation cancelled')
            return

    if not all((install_path, replies_file, frequency, replies_per_query,
               venv_path, secrets_file, ignored_accounts)):
        print('At least one of the configuration has not been set in the '
              'configuration file.')
        print('Installation cancelled')
        return

    install_path = os.path.join(install_path, INSTALLATION_DIRECTORY)
    if os.path.isdir(install_path):
        print('There is an instance of the bot already installed in:')
        print('\t' + install_path)
        option = input(
            'Overwrite the current installation? '
            '(contents will be saved) [Y/n]:')
        if option in ('n', 'N'):
            print('Installation cancelled')
            return
        _clean_current_install(install_path)
    else:
        os.makedirs(install_path, exist_ok=True)

    # Generate access token
    _generate_access_token(install_path, secrets_file)

    # Move the main script and the configuration files to the installation dir
    target_script = os.path.join(install_path, 'twitterbot.py')
    shutil.copy2('twitterbot.py', target_script)
    shutil.copy2(replies_file, os.path.join(install_path, 'replies.json'))

    with open(os.path.join(install_path, 'replies_per_query.cfg'), 'w') as dst:
        print(str(replies_per_query), file=dst)

    with open(os.path.join(install_path, 'ignored_accounts.txt'), 'w') as dst:
        for account in ignored_accounts:
            print(account, file=dst)
        # Print an empty line just to make sure the file is created
        print(account, file=dst)

    shutil.copy2(secrets_file, os.path.join(install_path, 'secrets.key'))

    # Update the she-bang in the installed script
    with open(target_script, 'r') as from_file:
        from_file.readline()
        with open(target_script, 'w') as to_file:
            to_file.write('#!' + venv_path + '\n')
            shutil.copyfileobj(from_file, to_file)

    # Make it executable
    st = os.stat(target_script)
    os.chmod(target_script, st.st_mode | stat.S_IEXEC)

    # Set up the crontab job
    os.system(
        '(crontab -l 2>/dev/null; echo "%s %s > /tmp/twitterbot.cronlog 2>&1") '
        '| crontab -' % (frequency, target_script))


if __name__ == '__main__':
    main()
