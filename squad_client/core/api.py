import requests
import logging
import urllib
import re


url_validator_regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


logger = logging.getLogger()


# ref: https://git.linaro.org/lava/lava-lab.git/tree/shared/lab-scripts/rerun_health_check.py#n13
class NullAuth(requests.auth.AuthBase):
    '''force requests to ignore the ``.netrc``

    Some sites do not support regular authentication, but we still
    want to store credentials in the ``.netrc`` file and submit them
    as form elements. Without this, requests would otherwise use the
    .netrc which leads, on some sites, to a 401 error.

    Use with::

        requests.get(url, auth=NullAuth())

    Copied from: https://github.com/psf/requests/issues/2773#issuecomment-174312831
    '''

    def __call__(self, r):
        return r


class ApiException(requests.exceptions.RequestException):
    pass


class SquadApi:
    url = None
    token = None
    headers = None

    @staticmethod
    def configure(url, token=None):
        if url is None or url_validator_regex.match(url) is None:
            raise ApiException('Malformed url: "%s"' % url)

        if token:
            SquadApi.token = token
            SquadApi.headers = {"Authorization": 'token %s' % token}

        SquadApi.url = url if url[-1] == '/' else url + '/'
        logger.debug('SquadApi: url = "%s" and token = "%s"' % (SquadApi.url, 'yes' if SquadApi.token else 'no'))

    @staticmethod
    def get(endpoint, params={}):
        return SquadApi.__request__('GET', endpoint, params=params)

    @staticmethod
    def post(endpoint, params={}, data={}):
        return SquadApi.__request__('POST', endpoint, params=params, data=data)

    @staticmethod
    def __request__(method, endpoint, **kwargs):
        if SquadApi.url is None:
            raise ApiException('Missing "url" in SquadApi configuration. Example: `export SQUAD_HOST=http://qa-reports.linaro.org`')

        if endpoint.startswith('http'):

            parsed_url = urllib.parse.urlparse(endpoint)
            tmp_url = '%s://%s/' % (parsed_url.scheme, parsed_url.netloc)
            if SquadApi.url != tmp_url:
                raise ApiException('Given url (%s) is does not match pre-configured one!' % tmp_url)

            endpoint = parsed_url.path

            params = kwargs.get('params', {})
            params.update(urllib.parse.parse_qs(parsed_url.query))
            kwargs['params'] = params

        url = '%s%s' % (SquadApi.url, endpoint if endpoint[0] != '/' else endpoint[1:])
        logger.debug('%s %s' % (method, url))

        if SquadApi.headers:
            kwargs['headers'] = SquadApi.headers

        try:
            response = requests.request(method, url, auth=NullAuth(), **kwargs)
            if response.status_code == 401:
                msg = 'Unauthorized access to "%s"' % url
                # logger.error(msg)
                if SquadApi.token is None:
                    raise ApiException('%s. Consider `export SQUAD_TOKEN=your-squad-token`' % msg)
            elif response.status_code == 500:
                logger.error('You hit a bug in SQUAD, please report it at https://github.com/Linaro/squad/issues/new so we can get it fixed.')

            return response

        except requests.exceptions.ConnectionError as e:
            raise ApiException('Error Connecting: %s' % e)
        except requests.exceptions.Timeout as e:
            raise ApiException('Timeout Error: %s' % e)
        except requests.exceptions.RequestException as e:
            raise ApiException('OOps: Something unexpected happened while requesting the API: %s' % e)
