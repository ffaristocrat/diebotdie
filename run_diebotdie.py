import json
import logging
import argparse
import sys
import time

import redis

from diebotdie.rules import UserRules
from diebotdie.blocker import Blocker
from diebotdie.twitter import APIClient


LOG = logging.getLogger(__name__)


def run_diebotdie(rules, twitter, r):
    blocker = Blocker(rules, twitter, r)
    rate_limit = twitter.rate_limits['search/tweets']
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
        time.sleep(60 * 15 / rate_limit)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'rules', type=str, default='rules.json', help='Rules definition')
    parser.add_argument(
        '--port', type=int, default=6379, help='Redis port')
    parser.add_argument(
        '--host', type=str, default='localhost', help='Redis host')
    parser.add_argument(
        '--db', type=int, default=0, help='Redis database')

    args = parser.parse_args()
    
    rules = UserRules(**json.load(open(args.rules, 'rt'))['rules'])
    twitter = APIClient()
    r = redis.StrictRedis(host=args.host, port=args.port, db=args.db)

    try:
        run_diebotdie(rules, twitter, r)
    except BaseException:
        print('Saving redis db')
        r.save()
        raise


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout, level=logging.INFO, format='%(message)s')
    main()
