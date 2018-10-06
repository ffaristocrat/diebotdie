import time
import logging
from typing import Dict

import requests
from requests_oauthlib import OAuth1

LOG = logging.getLogger(__name__)


class TwitterException(Exception):
    pass


class APIClient:
    def __init__(self, consumer_key: str=None, consumer_secret: str=None,
                 access_token_key: str=None, access_token_secret: str=None):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token_key = access_token_key
        self.access_token_secret = access_token_secret

        self.session = requests.session()
        self.rate_limits = {}
        self.reset_time = 0

        self.base_url = 'https://api.twitter.com/1.1'

        self.fail_limit = 5
        self.retry_time = 10

        self._refresh_access_token()
    
    def update_rate_limits(self):
        data = self.get('/application/rate_limit_status')

        for resource, endpoints in data['resources'].items():
            for url, limits in endpoints.items():
                self.rate_limits[url] = limits['limit']
                self.reset_time = max(self.reset_time, limits['reset'])

    def _refresh_access_token(self):
        auth_list = [
            self.consumer_key, self.consumer_secret,
            self.access_token_key, self.access_token_secret]
        self.session.auth = OAuth1(*auth_list)

    def call_api(self, method: str, endpoint: str, params: Dict=None,
                 body: Dict=None, raise_rate_limit=False, **kwargs):
        url = f"{self.base_url}/{endpoint.lstrip('/')}.json"
        LOG.debug(f'{method} {endpoint}')

        fail = 0
        retry_in = 0

        while True:
            if retry_in:
                LOG.info(f'Waiting {retry_in} seconds to retry...')
                time.sleep(retry_in)

            error_dict = {
                'method': method,
                'endpoint': endpoint,
                'params': params,
            }
            status_code = None
            try:
                response = self.session.request(
                    method, url, json=body, params=params, **kwargs)

                status_code = response.status_code

                error_dict.update({
                    'encoded_url': response.url,
                    'status_code': status_code,
                })

                try:
                    data = response.json()
                except (ValueError, TypeError) as E:
                    LOG.warning(E)
                    data = {}

                if 'errors' in data:
                    error_dict.update({
                        'errors': data['errors'],
                    })

                if status_code in [401, 403]:
                    self._refresh_access_token()
                    continue

                elif status_code in [429]:
                    # Rate Limit
                    self.update_rate_limits()
                    LOG.warning(error_dict)
                    if raise_rate_limit:
                        raise TwitterException('Rate limit exceeded')
                    LOG.warning('Rate limit exceeded')
                    retry_in = max(self.reset_time - time.time(), 0)
                    continue

                response.raise_for_status()

            except requests.exceptions.RequestException as E:
                if status_code in [404]:
                    raise

                error_dict['stack_trace'] = E

                if fail >= self.fail_limit:
                    raise TwitterException(error_dict)
                else:
                    fail += 1
                    retry_in = fail * self.retry_time
                continue

            else:
                break
                
        return data

    def post(self, endpoint: str, params: Dict=None, body: Dict=None,
             **kwargs):
        return self.call_api('POST', endpoint, params, body, **kwargs)
    
    def get(self, endpoint: str, params: Dict=None, body: Dict=None,
            **kwargs):
        return self.call_api('GET', endpoint, params, body, **kwargs)
    
    def get_pages(self, endpoint: str, params: Dict=None, body: Dict=None,
                  **kwargs):
        cursor = -1
        while True:
            params.update({'cursor': cursor})
            data = self.get(endpoint, params=params, body=body, **kwargs)
            cursor = data['next_cursor']
            yield data

            if cursor == 0:
                break
