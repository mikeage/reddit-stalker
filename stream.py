import praw
import time
import argparse
import logging
import sys

subreddit_cache = {}


def print_comment(comment):
    global subreddit_cache  # pylint: disable=global-statement
    try:
        assert subreddit_cache[comment.subreddit_id]
    except KeyError:
        subreddit_cache[comment.subreddit_id] = comment.subreddit.display_name
    try:
        url = "https://www.reddit.com/comments/%s/_/%s/" % (comment.link_id.replace("t3_", ""), comment.id)
        print("%s\nr/%s %s: %s" % (url, subreddit_cache[comment.subreddit_id], comment.author, comment.body))
    except AttributeError:
        url = "https://www.reddit.com/%s/" % comment.id
        print("%s\nr/%s %s: %s" % (url, subreddit_cache[comment.subreddit_id], comment.author, comment.selftext))
    print("==================")


def main(include_old_comments):

    start_time = time.time() - 3600
    try:
        reddit = praw.Reddit('bot')
    except praw.exceptions.ClientException:
        logging.error("Can't connect to reddit via PRAW. Did you set up a praw.ini?")
        sys.exit(1)

    logging.info("Getting a list of friends")
    friends = [friend.display_name.replace("u_", "") for friend in reddit.user.subreddits() if friend.display_name.startswith("u_")]
    friends.append(reddit.user.me().name)
    logging.info("Friends = %s", friends)

    streams = [praw.models.Redditor(reddit, name=friend).stream.comments(skip_existing=not include_old_comments, pause_after=-1) for friend in friends]
    streams = streams + [praw.models.Redditor(reddit, name=friend).stream.submissions(skip_existing=not include_old_comments, pause_after=-1) for friend in friends]
    logging.debug("Streams are %s", streams)

    # For the initial stream, sort the comments
    if include_old_comments:
        logging.info("Getting old comments")
        all_comments = []
        for stream in streams:
            logging.debug("Looking at stream %s", stream)
            for comment in stream:
                if comment is not None:
                    if comment.created_utc >= start_time:
                        logging.debug("Adding comment %s", comment)
                        all_comments.append(comment)
                else:
                    break
        logging.info("Finished")
        for comment in sorted(all_comments, key=lambda comment: comment.created_utc):
            print_comment(comment)

    logging.info("Starting streaming")
    while True:
        for stream in streams:
            for comment in stream:
                if comment is None:
                    logging.debug("No comments for %s", stream)
                    break
                print_comment(comment)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-v', '--verbose', action='count', default=0, help="Print extra traces (INFO level). Use twice to print DEBUG prints")
    parser.add_argument("-o", "--include-old-comments", help="Include old comments", action="store_true")
    parsed_args = parser.parse_args()

    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(len(levels) - 1, parsed_args.verbose)]
    logging.basicConfig(level=level)
    main(parsed_args.include_old_comments)
