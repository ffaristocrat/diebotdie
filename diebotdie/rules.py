import logging

import emoji

LOG = logging.getLogger(__name__)


class UserRules:
    def __init__(self, **kwargs):
        self.screen_name_keywords = kwargs.pop('screen_name_keywords') or []
        self.profile_keywords = [
            k.lower() for k in kwargs.pop('profile_keywords') or []]
        self.emoji_count = kwargs.pop('emoji_count')

        self._rules = {
            attr: getattr(self, attr)
            for attr in dir(self)
            if callable(getattr(self, attr)) and
               (attr.startswith('user_') or attr.startswith('profile_'))
        }

    def user_screen_name_has_eight_digits(self, user):
        return [user['screen_name'][-8:]] \
            if user['screen_name'][-8:].isdigit() else []

    def user_name_has_flagged_keywords(self, user):
        found = set()
        for e in self.screen_name_keywords:
            if e in user['name']:
                found.add(e)
        return list(found)

    def profile_has_default_profile_image(self, user):
        return ['True'] if user['default_profile_image'] else []

    def profile_description_has_keywords(self, user):
        found = set()
        desc = user['description'].lower()
        for keyword in self.profile_keywords:
            if keyword in desc:
                found.add(keyword)
        return list(found)

    def profile_description_has_too_many_emojis(self, user):
        if not self.emoji_count:
            return []
        
        emojis = [e for e in user['description'] if e in emoji.EMOJI_UNICODE]
        return emojis if len(emojis) > self.emoji_count else []

    def user_name_has_too_many_emojis(self, user):
        if not self.emoji_count:
            return False
        emojis = [e for e in user['screen_name'] if e in emoji.EMOJI_UNICODE]
        return emojis if len(emojis) > self.emoji_count else []

    def check_user(self, user) -> bool:
        block = False
        for rule, func in self._rules.items():
            results = func(user)
            if results:
                LOG.debug(
                    f"{user['screen_name']}: {rule}: {' '.join(results)}")
                block = True
        return block
