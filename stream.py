import argparse
import dateparser
import datetime
import logging
import praw
import sys


logger = logging.getLogger(__name__)


def print_item(item, subreddit_cache):
    try:
        assert subreddit_cache[item.subreddit_id]
    except KeyError:
        subreddit_cache[item.subreddit_id] = item.subreddit.display_name
    try:
        url = "https://www.reddit.com/comments/%s/_/%s/" % (item.link_id.replace("t3_", ""), item.id)
        action = "commented"
        content = item.body
    except AttributeError:
        url = "https://www.reddit.com/%s/" % item.id
        action = "posted"
        content = item.selftext
    print("%s %s\nr/%s %s %s: %s" % (datetime.datetime.fromtimestamp(item.created_utc).isoformat(), url, subreddit_cache[item.subreddit_id], item.author, action, content))
    print("==================")


def main(include_old_actions, follow_me):  # pylint: disable=too-many-branches

    try:
        reddit = praw.Reddit('bot')
    except praw.exceptions.ClientException:
        logger.error("Can't connect to reddit via PRAW. Did you set up a praw.ini?")
        sys.exit(1)

    subreddit_cache = {}
    logger.info("Getting a list of users you are following")
    followings = [following.display_name.replace("u_", "") for following in reddit.user.subreddits() if following.display_name.startswith("u_")]
    if follow_me:
        followings.append(reddit.user.me().name)
    followings.sort(key=str.lower)
    logger.info("followings = %s", followings)

    if include_old_actions:
        start_time = dateparser.parse(include_old_actions).timestamp()
        skip_existing = False
    else:
        skip_existing = True

    # Create streams for comments and submissions for each following user
    streams = [praw.models.Redditor(reddit, name=following).stream.comments(skip_existing=skip_existing, pause_after=-1) for following in followings] + [praw.models.Redditor(reddit, name=following).stream.submissions(skip_existing=skip_existing, pause_after=-1) for following in followings]
    logger.debug("Streams are %s", streams)

    # For the initial stream, sort the comments and submissions by time
    if include_old_actions:
        logger.info("Getting old items since %s", include_old_actions)
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
    parser = argparse.ArgumentParser()

    parser.add_argument('-v', '--verbose', action='count', default=0, help="Print extra traces (INFO level). Use twice to print DEBUG prints")
    parser.add_argument("-o", "--include-old-actions", help="Include old comments and submissions (format can be absolute or relative)", metavar="'time reference'")
    parser.add_argument("-m", "--follow-me", help="Include your own comments and submissions", action="store_true")
    parsed_args = parser.parse_args()

    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels) - 1, parsed_args.verbose)]
    logging.basicConfig(level=level)
    main(parsed_args.include_old_actions, parsed_args.follow_me)
