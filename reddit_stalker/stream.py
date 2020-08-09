import argparse
import dateparser
import datetime
import logging
import praw
import sys
import random
import socket
from ._version import get_versions
from colorama import init, Fore, Style

logger = logging.getLogger(__name__)


def receive_connection():
    """
    Wait for and then return a connected socket..
    Opens a TCP connection on port 8080, and waits for a single client.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('localhost', 8812))
    server.listen(1)
    client = server.accept()[0]
    server.close()
    return client


def send_message(client, message):
    """
    Send message to client and close the connection.
    """
    client.send('HTTP/1.1 200 OK\r\n\r\n{}'.format(message).encode('utf-8'))
    client.close()


def print_item(item, subreddit_cache):
    try:
        assert subreddit_cache[item.subreddit_id]
    except KeyError:
        subreddit_cache[item.subreddit_id] = item.subreddit_name_prefixed
    try:
        url = "https://www.reddit.com/comments/%s/_/%s/" % (item.link_id.replace("t3_", ""), item.id)
        action = "commented"
        content = item.body
    except AttributeError:
        url = "https://www.reddit.com/%s/" % item.id
        try:
            action = "crossposted from " + Fore.BLUE + item.crosspost_parent_list[0]['subreddit_name_prefixed'] + Fore.RESET
        except (AttributeError, KeyError):
            action = "posted"
        content = item.title
        if item.selftext:
            content = content + "\n" + item.selftext
    print(Style.DIM + datetime.datetime.fromtimestamp(item.created_utc).isoformat() + Style.RESET_ALL + Fore.BLUE + " " + url + Fore.RESET + "\n" + Fore.BLUE + subreddit_cache[item.subreddit_id] + Fore.RESET + " " + Fore.RED + str(item.author) + Fore.RESET + " " + action + ": " + content)
    print("==================")
    with open('/tmp/reddit_stalker_last_timestamp', 'w') as f:
        f.write(str(item.created_utc))


def main():  # pylint: disable=too-many-branches,too-many-statements
    init()

    parser = argparse.ArgumentParser()

    parser.add_argument('-v', '--verbose', action='count', default=0, help="Print extra traces (INFO level). Use twice to print DEBUG prints")
    parser.add_argument("-o", "--include-old-actions", help="Include old comments and submissions (format can be absolute or relative)", metavar="'time reference'")
    parser.add_argument("-m", "--follow-me", help="Include your own comments and submissions", action="store_true")
    parser.add_argument("-f", "--followers", help="Automatically track all users you're following", action="store_true")
    parser.add_argument("-u", "--users", nargs="+", help="List of users to follow in addition to the users you follow (aka stealth mode)")
    parser.add_argument('-V', '--version', action='version', version='%(prog)s {version}'.format(version=get_versions()["version"]))
    args = parser.parse_args()

    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels) - 1, args.verbose)]
    logging.basicConfig(level=level)
    logging.getLogger('prawcore').setLevel(logging.ERROR)

    try:
        reddit = praw.Reddit('bot', redirect_uri='http://localhost:8812')
    except praw.exceptions.ClientException:
        logger.error("Can't connect to reddit via PRAW. Did you set up a praw.ini?")
        sys.exit(1)
    try:
        reddit.user.me()
    except Exception as err:
        if (str(err) != 'invalid_grant error processing request'):
            print('LOGIN FAILURE: %s' % err)
            return 1
        else:
            state = str(random.randint(0, 65000))
            scopes = ['identity', 'account', 'history', 'read', 'mysubreddits', 'subscribe']
            url = reddit.auth.url(scopes, state, 'permanent')
            print(url)

            client = receive_connection()
            data = client.recv(1024).decode('utf-8')
            param_tokens = data.split(' ', 2)[1].split('?', 1)[1].split('&')
            params = {key: value for (key, value) in [token.split('=') for token in param_tokens]}

            if state != params['state']:
                send_message(client, 'State mismatch. Expected: {} Received: {}'.format(state, params['state']))
                return 1
            elif 'error' in params:
                send_message(client, params['error'])
                return 1

            refresh_token = reddit.auth.authorize(params["code"])
            send_message(client, "Refresh token: {}".format(refresh_token))

            print(refresh_token)
            return 0

    subreddit_cache = {}
    followings = []
    assert args.followers or args.users

    if args.followers:
        logger.info("Getting a list of users you are following")
        followings.extend([following.display_name.replace("u_", "") for following in reddit.user.subreddits() if following.display_name.startswith("u_")])
    followings.extend(args.users)
    if args.follow_me:
        followings.append(reddit.user.me().name)

    followings.sort(key=str.lower)
    logger.info("followings = %s", followings)

    include_old = False
    if args.include_old_actions:
        if args.include_old_actions == "auto":
            try:
                with open('/tmp/reddit_stalker_last_timestamp', 'r') as f:
                    start_time = dateparser.parse(f.readline()).timestamp()
                    include_old = True
            except Exception as ex:  # pylint: disable=broad-except
                logger.warning("Couldn't get last timestamp: %s", ex)
        else:
            start_time = dateparser.parse(args.include_old_actions).timestamp()
            include_old = True

    # Create streams for comments and submissions for each following user
    streams = [praw.models.Redditor(reddit, name=following).stream.comments(skip_existing=not include_old, pause_after=-1) for following in followings] + [praw.models.Redditor(reddit, name=following).stream.submissions(skip_existing=not include_old, pause_after=-1) for following in followings]
    logger.debug("Streams are %s", streams)

    # For the initial stream, sort the comments and submissions by time
    if args.include_old_actions:
        logger.info("Getting old items since %s", args.include_old_actions)
        all_items = []
        for stream in streams:
            logger.debug("Looking at stream %s", stream)
            for item in stream:
                if item is not None:
                    if item.created_utc >= start_time:
                        logger.debug("Adding item %s", item)
                        all_items.append(item)
                else:
                    break
        logger.info("Finished")
        for item in sorted(all_items, key=lambda item: item.created_utc):
            print_item(item, subreddit_cache)

    logger.info("Starting streaming")
    while True:
        for stream in streams:
            for item in stream:
                if item is None:
                    logger.debug("No items for %s", stream)
                    break
                print_item(item, subreddit_cache)


if __name__ == '__main__':
    main()
