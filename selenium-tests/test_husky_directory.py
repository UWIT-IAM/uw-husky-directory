import json

from webdriver_recorder.browser import By, Locator


def test_instance_status(session_browser, directory_url):
    session_browser.get(f'{directory_url}/health')
    with session_browser.autocapture_off():
        output = session_browser.wait_for_tag('pre', '').text
    output = json.loads(output)
    session_browser.snap(
        caption=f'Get status of of {directory_url}, version is {output["version"]}'
    )


def test_name_search(browser):
    """
    A basic use case for the directory: Search for a name,
    then click on a result to expand it.
    """
    browser.find_element(by=By.ID, value='query').click()
    browser.send('Smith')
    browser.snap(caption="Search for employees named 'Smith'")
    browser.find_element(by=By.ID, value='search').click()
    browser.wait_for(Locator(
        search_method=By.ID, search_value='employees-last-name-is-smith'),
        caption="Wait for results to load",
        timeout=15
    )
    display_name_element = browser.find_elements(
        by=By.CSS_SELECTOR, value='tr.summary-row > td'
    )[0]
    display_name = display_name_element.text.strip()
    browser.find_element(by=By.CSS_SELECTOR, value='input[name="expand-1"]').click()
    browser.wait_for_tag(
        'h4', display_name,
        caption="Click the 'More' button to expand the first record"
    )


def test_wildcard_search(browser):
    """
    Searching by wildcard is supported; just input '*' characters
    representing the letters you're not sure about.
    """
    browser.find_element(by=By.ID, value='query').click()
    browser.send('J*ns*n')
    browser.snap(caption="Search using a wildcard")
    browser.find_element(by=By.ID, value='search').click()
    browser.wait_for(Locator(
        search_method=By.ID,
        search_value="employees-name-matches-j-ns-n"
    ))
