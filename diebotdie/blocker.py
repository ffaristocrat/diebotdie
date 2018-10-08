import logging
import json
from typing import Set, Dict

import redis
import requests

from diebotdie.rules import UserRules
from diebotdie.twitter import APIClient, TwitterException

LOG = logging.getLogger(__name__)

HAMILTON_68_URL = 'https://mario-blob-prod.azureedge.net/data/data-2.json'


class Blocker:
    def __init__(self, rules: UserRules, twitter: APIClient,
                 redis_client: redis.client):
        self.rules = rules
        self.twitter = twitter
        self.redis = redis_client

    def post_block(self, user_id):
        params = {
            'user_id': user_id,
            'skip_status': 1,
            'include_entities': False,
        }
        try:
            self.twitter.post('blocks/create', params=params)
        except requests.exceptions.RequestException:
            # 404'd because the user is gone already
            pass

    def block_user(self, user_id: str):
        self.post_block(user_id)
        self.redis.sadd('block', user_id)

    def mark_as_clean(self, user_id: str):
        self.redis.sadd('clean', user_id)

    def already_checked(self, user_id: str) -> bool:
        return (
            self.redis.sismember('block', user_id) or
            self.redis.sismember('clean', user_id))

    def add_followers_to_queue(self, user_id: str):
        params = {
            'count': 200,
            'user_id': user_id,
        }
        # just grab the first page
        data = self.twitter.get('followers/list', params=params)

        for user in data['users']:
            self.add_to_queue(user)

    def get_friends(self) -> Set:
        this_user = self.twitter.get('account/verify_credentials')

        friends = set()
        params = {
            'screen_name': this_user['screen_name']
        }

        try:
            for data in self.twitter.get_pages(
                    'friends/list', params=params, raise_rate_limit=True):
                for user in data['users']:
                    friends.add(f"to:{user['screen_name']}")
                    self.mark_as_clean(user['id_str'])
        except TwitterException:
            LOG.warning('Skipping friend collection for now')
            pass

        LOG.info(f'Collected {len(friends)} friends')
        return friends

    def get_hamilton_68_topics(self) -> Set[str]:
        categories = [
            'topHashtags',
            'breakoutHashtags',
            'topNouns',
            'breakoutNouns',
        ]
        LOG.info(f"Collecting Hamilton 68: {', '.join(categories)}")
        topics = set()

        try:
            data = requests.get(HAMILTON_68_URL).json()
        except Exception as E:
            LOG.warning(E)
            return topics

        for category in categories:
            hashtag = 'Hashtag' in category
            for row in data.get(category, {}).get('data', []):
                topic = row.get('name')
                if topic:
                    topics.add(f"{'#' if hashtag else ''}{topic.lower()}")

        LOG.debug(topics)
        return topics

    def get_twitter_trends(self, woeid=23424977) -> Set[str]:
        LOG.info(f'Collecting Twitter trends for {woeid}')
        params = {
            'id': woeid,
        }
        data = self.twitter.get('trends/place', params=params)

        trends = set(t['name'] for t in data[0]['trends'])
        LOG.debug(trends)

        return trends

    def search_topic(self, topic: str):
        LOG.info(f'Searching for tweets: "{topic}"')
        since_id = self.redis.get(f'topic-{topic}') or 0
        params = {
            'q': topic,
            'count': 100,
            'result_type': 'recent',
            'since_id': since_id,
        }
        tweets = self.twitter.get('search/tweets', params=params)

        for tweet in tweets['statuses']:
            self.add_to_queue(tweet['user'])
            self.redis.setex(
                f'topic-{topic}',
                60 * 5,
                max(self.redis.get(topic) or 0, tweet['id'],
            ))

    def get_next_in_queue(self) -> Dict:
        user_id = self.redis.spop('queue')
        if user_id:
            key = f'user-{int(user_id)}'
            user = json.loads(self.redis.get(key))
            self.redis.delete(key)
        else:
            user = None

        return user

    def add_to_queue(self, user):
        user_id = user['id_str']
        self.redis.sadd('queue', user_id)
        self.redis.set(f'user-{user_id}', json.dumps(user))

    def is_blockworthy(self, user) -> bool:
        if self.rules.check_user(user):
            return True

        self.mark_as_clean(user['id_str'])
        return False

    def process_users_queue(self):
        queue = self.redis.scard('queue')
        blocked = 0
        while True:
            user = self.get_next_in_queue()
            if not user:
                break

            if self.already_checked(user['id_str']):
                queue -= 1
                continue

            if self.is_blockworthy(user):
                self.block_user(user['id_str'])
                blocked += 1

        LOG.info(f'Blocked {blocked} users out of {queue}')

    def collect_topics(self) -> Set[str]:
        topics = set()
        topics |= self.get_hamilton_68_topics()
        topics |= self.get_twitter_trends()
        topics |= self.get_friends()
        return topics

    def collect_users_on_topics(self, topics):
        LOG.info(f'Searching topics: {", ".join(topics)}')
        for topic in list(topics):
            self.search_topic(topic)
