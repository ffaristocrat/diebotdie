import json
import logging
import argparse
import sys
import time
import pprint

import redis

from diebotdie.rules import UserRules
from diebotdie.blocker import Blocker
from diebotdie.twitter import APIClient


LOG = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=4)


def main():
    rules = UserRules(**json.load(open('rules.json'))['rules'])
    twitter = APIClient(
        **json.load(open('secrets.json')),
    )
    r = redis.StrictRedis(host='localhost', port=6379, db=0)

    blocker = Blocker(rules, twitter, r)

    topics = set()

    # Clear backlog first
    blocker.process_users_queue()

    while True:
        if not topics:
            blocked_count = blocker.redis.scard('block')
            clean_count = blocker.redis.scard('clean')
            LOG.info(f'Blocked: {blocked_count}\t'
                      f'Clean: {clean_count}\t')
            topics |= blocker.collect_topics()

        topic = topics.pop()
        blocker.search_topic(topic)
        blocker.process_users_queue()

        # Space out searches to stay within the rate limit
        time.sleep(60 * 15 / 180)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout, level=logging.INFO, format='%(message)s')
    main()
