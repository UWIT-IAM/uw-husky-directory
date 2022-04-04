import pytest
import requests
from webdriver_recorder.browser import BrowserRecorder


def pytest_addoption(parser):
    parser.addoption(
        '--uw-directory-url',
        dest="uw_directory_url",
        action='store',
        default='prod',
        help='Either an explicit url, or one of dev|eval|prod.'
    )


@pytest.fixture(scope='session')
def directory_instance_version(directory_url):
    status_url = f'{directory_url}/status'
    status = requests.get(status_url).json()
    return status['version']


@pytest.fixture(scope='session')
def report_title(request, directory_instance_version):
    short_url: str = request.config.getoption('uw_directory_url')
    return f'UW Directory [{short_url.title()}@v{directory_instance_version}] Validation Tests'


@pytest.fixture(scope='session')
def directory_url(request) -> str:
    url = request.config.getoption('uw_directory_url')
    if not url.startswith('http'):
        url = f'https://directory.iam{url}.s.uw.edu'
    return url


@pytest.fixture
def browser(browser, directory_url) -> BrowserRecorder:
    with browser.autocapture_off():
        browser.get(directory_url)
        browser.wait_for_tag('h2', 'UW Directory')
    return browser
