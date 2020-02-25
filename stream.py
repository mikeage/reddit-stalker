import praw
import time
import argparse
import logging
import sys

subreddit_cache = {}


def print_item(item):
    global subreddit_cache  # pylint: disable=global-statement
    try:
        assert subreddit_cache[item.subreddit_id]
    except KeyError:
        subreddit_cache[item.subreddit_id] = item.subreddit.display_name
    try:
        url = "https://www.reddit.com/comments/%s/_/%s/" % (item.link_id.replace("t3_", ""), item.id)
        print("%s\nr/%s %s commented: %s" % (url, subreddit_cache[item.subreddit_id], item.author, item.body))
    except AttributeError:
        url = "https://www.reddit.com/%s/" % item.id
        print("%s\nr/%s %s posted: %s" % (url, subreddit_cache[item.subreddit_id], item.author, item.selftext))
    print("==================")


def main(include_old_actions, follow_me):

    start_time = time.time() - 3600
    try:
        reddit = praw.Reddit('bot')
    except praw.exceptions.ClientException:
        logging.error("Can't connect to reddit via PRAW. Did you set up a praw.ini?")
        sys.exit(1)

    logging.info("Getting a list of users you are following")
    followings = [following.display_name.replace("u_", "") for following in reddit.user.subreddits() if following.display_name.startswith("u_")]
    if follow_me:
        followings.append(reddit.user.me().name)
    followings.sort(key=str.lower)
    logging.info("followings = %s", followings)

    # Create streams for comments and submissions for each following user
    streams = [praw.models.Redditor(reddit, name=following).stream.comments(skip_existing=not include_old_actions, pause_after=-1) for following in followings] + [praw.models.Redditor(reddit, name=following).stream.submissions(skip_existing=not include_old_actions, pause_after=-1) for following in followings]
    logging.debug("Streams are %s", streams)

    # For the initial stream, sort the comments and submissions by time
    if include_old_actions:
        logging.info("Getting old items")
        all_items = []
        for stream in streams:
            logging.debug("Looking at stream %s", stream)
            for item in stream:
                if item is not None:
                    if item.created_utc >= start_time:
                        logging.debug("Adding item %s", item)
                        all_items.append(item)
                else:
                    break
        logging.info("Finished")
        for item in sorted(all_items, key=lambda item: item.created_utc):
            print_item(item)

    logging.info("Starting streaming")
    while True:
        for stream in streams:
            for item in stream:
                if item is None:
                    logging.debug("No items for %s", stream)
                    break
                print_item(item)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-v', '--verbose', action='count', default=0, help="Print extra traces (INFO level). Use twice to print DEBUG prints")
    parser.add_argument("-o", "--include-old-actions", help="Include old comments and submissions", action="store_true")
    parser.add_argument("-m", "--follow-me", help="Include your own comments and submissions", action="store_true")
    parsed_args = parser.parse_args()

    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels) - 1, parsed_args.verbose)]
    logging.basicConfig(level=level)
    main(parsed_args.include_old_actions, parsed_args.follow_me)
