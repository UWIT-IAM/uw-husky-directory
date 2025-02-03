import base64
import re
from datetime import datetime
from typing import cast
from unittest import mock

import pytest
from bs4 import BeautifulSoup
from flask import Response
from flask.testing import FlaskClient
from inflection import titleize
from werkzeug import exceptions
from werkzeug.local import LocalProxy

from husky_directory.models.enum import PopulationType, ResultDetail
from husky_directory.models.pws import ListPersonsInput, ListPersonsOutput
from husky_directory.models.search import SearchDirectoryFormInput, SearchDirectoryInput
from husky_directory.services.pws import PersonWebServiceClient


class BlueprintSearchTestBase:
    @pytest.fixture(autouse=True)
    def initialize(
        self, client: FlaskClient, mock_people, injector, html_validator, mock_injected
    ):
        self.flask_client = client
        self.session = {}
        self.html_validator = html_validator
        self.mock_people = mock_people

        with mock_injected(LocalProxy, self.session):
            self.pws_client = injector.get(PersonWebServiceClient)
            with mock_injected(PersonWebServiceClient, self.pws_client):
                self.mock_send_request = mock.patch.object(
                    self.pws_client, "_get_search_request_output"
                ).start()
                self.mock_send_request.return_value = mock_people.as_search_output(
                    mock_people.contactable_person
                )
                yield


class TestSearchBlueprint(BlueprintSearchTestBase):
    @pytest.mark.parametrize(
        "search_field, search_value, expected_value",
        [
            (
                "name",
                "",
                "Invalid input for query (Name query string must contain at least 2 characters)",
            ),
            (
                "phone",
                "",
                "Invalid input for query (Query string must contain at least 3 characters)",
            ),
            (
                "department",
                "",
                "Invalid input for query (Query string must contain at least 3 characters)",
            ),
            (
                "box_number",
                "",
                "Invalid input for query (Query string must contain at least 3 characters)",
            ),
            (
                "email",
                "",
                "Invalid input for query (Query string must contain at least 3 characters)",
            ),
        ],
    )
    def test_set_preferences_for_cookie(
        self, search_field, search_value, expected_value
    ):
        response = self.flask_client.post(
            "/",
            data={
                "query": search_value,
                "method": search_field,
                "population": "employees",
                "length": "summary",
            },
        )
        assert response.status_code == 400
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("Encountered error"))
            self.html_validator.assert_has_tag_with_text(
                "b",
                expected_value,
            )

    def test_empty_form(self):
        """
        if somehow a hacker passes an empty form to the back, we still won't return anything.
        """
        response = self.flask_client.post(
            "/",
            data={},
        )
        assert response.status_code == 200
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            self.html_validator.assert_has_tag_with_text("p", "No matches for")

    def test_render_summary_success(
        self, search_method: str = "name", search_query: str = "lovelace"
    ):
        response = self.flask_client.post(
            "/", data={"method": search_method, "query": search_query}
        )
        assert response.status_code == 200
        profile = self.mock_people.contactable_person
        with self.html_validator.validate_response(response) as html:
            with self.html_validator.scope("table", summary="results"):
                self.html_validator.assert_has_tag_with_text(
                    "td",
                    profile.affiliations.employee.directory_listing.phones[0],
                )
                self.html_validator.assert_has_tag_with_text(
                    "td",
                    profile.affiliations.employee.directory_listing.emails[0],
                )
            assert "autofocus" not in html.find("input", attrs={"name": "query"}).attrs

    def _set_up_multipage_search(self):
        page_one = self.mock_people.as_search_output(
            next_=ListPersonsInput(href="https://foo/page-2")
        )
        page_two = self.mock_send_request.return_value
        self.mock_send_request.return_value = page_one
        mock_next_page = mock.patch.object(self.pws_client, "get_explicit_href").start()
        mock_next_page.return_value = ListPersonsOutput.parse_obj(page_two)

    def test_render_multi_page_experimental_search(self):
        self._set_up_multipage_search()
        self.test_render_summary_success()

    def test_render_multi_page_classic_search(self):
        self._set_up_multipage_search()
        self.test_render_summary_success(search_method="email", search_query="foo")

    def test_copyright_footer(self):
        response = self.flask_client.get("/")
        assert response.status_code == 200
        current_year = datetime.utcnow().year
        html: BeautifulSoup
        with self.html_validator.validate_response(response) as html:
            element = html.find("p", attrs={"id": "footer-copyright"})
            assert f"© {current_year}" in element.text

    @pytest.mark.parametrize("log_in", (True, False))
    def test_render_full_success(self, log_in, app):
        if log_in:
            with app.test_client() as client:
                client.get("/saml/login", follow_redirects=True)
                assert self.session.get("uwnetid")

        response = self.flask_client.post(
            "/",
            data={
                "query": "lovelace",
                "method": "name",
                "length": "full",
                "population": "all",
            },
        )

        profile = self.mock_people.contactable_person
        with self.html_validator.validate_response(response):
            self.html_validator.assert_has_tag_with_text("h4", profile.display_name)
            self.html_validator.assert_has_scenario_anchor(
                "employees-last-name-is-lovelace"
            )
            if log_in:
                self.html_validator.assert_has_scenario_anchor(
                    "students-last-name-is-lovelace"
                )
            with self.html_validator.scope("ul", class_="dir-listing"):
                self.html_validator.assert_has_tag_with_text(
                    "li", profile.affiliations.employee.directory_listing.emails[0]
                )
                self.html_validator.assert_has_tag_with_text(
                    "li", profile.affiliations.employee.directory_listing.phones[0]
                )
                self.html_validator.assert_has_tag_with_text(
                    "li", str(profile.affiliations.employee.mail_stop)
                )

    def test_render_student_no_phone(self):
        self.flask_client.get("/saml/login", follow_redirects=True)
        profile = self.mock_people.published_student
        profile.affiliations.student.directory_listing.phone = None
        profile.affiliations.employee = None
        self.mock_send_request.return_value = self.mock_people.as_search_output(profile)

        response = self.flask_client.post(
            "/",
            data={
                "query": "lovelace",
                "method": "name",
                "length": "full",
                "population": "all",
            },
        )

        with self.html_validator.validate_response(response):
            assert response.status_code == 200
            self.html_validator.assert_not_has_tag_with_text("li", "Phone:")

    def test_render_no_results(self):
        self.mock_send_request.return_value = self.mock_people.as_search_output()
        response = self.flask_client.post("/", data={"query": "lovelace"})
        with self.html_validator.validate_response(response) as html:
            self.html_validator.assert_not_has_scenario_anchor(
                "employees-name-matches-lovelace"
            )
            self.html_validator.assert_not_has_scenario_anchor(
                "students-name-matches-lovelace"
            )
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("No matches for"))
            self.html_validator.assert_has_tag_with_text("b", 'Name is "lovelace"')

    def test_render_invalid_box_number(self):
        response = self.flask_client.post(
            "/", data={"query": "abcdef", "method": "box_number"}
        )
        assert response.status_code == 400
        with self.html_validator.validate_response(response) as html:
            assert not html.find("table", summary="results")
            assert html.find(string=re.compile("Encountered error"))
            self.html_validator.assert_has_tag_with_text(
                "b", "box number (input can only contain digits)"
            )

    def test_render_full_no_box_number(self):
        self.mock_send_request.return_value = self.mock_people.as_search_output(
            self.mock_people.published_student
        )
        self.flask_client.get("/saml/login", follow_redirects=True)
        with self.html_validator.validate_response(
            self.flask_client.post(
                "/",
                data={
                    "query": "lovelace",
                    "length": "full",
                    "population": "all",
                },
            )
        ) as html:
            assert not html.find_all("li", class_="person-box-number")
            self.html_validator.assert_has_scenario_anchor(
                "students-last-name-is-lovelace"
            )
            self.html_validator.assert_not_has_scenario_anchor(
                "employees-last-name-is-lovelace"
            )
            with self.html_validator.scope("div", class_="usebar"):
                self.html_validator.assert_has_submit_button_with_text("Download vcard")

    def test_render_unexpected_error(self):
        self.mock_send_request.side_effect = RuntimeError
        response = self.flask_client.post(
            "/", data={"query": "123456", "method": "box_number"}
        )
        with self.html_validator.validate_response(response):
            self.html_validator.assert_has_tag_with_text(
                "b", "Something unexpected happened"
            )

    def test_user_login_flow(self):
        with self.html_validator.validate_response(self.flask_client.get("/")):
            self.html_validator.assert_not_has_student_search_options()
            self.html_validator.assert_has_sign_in_link()

        with self.html_validator.validate_response(
            self.flask_client.get("/saml/login", follow_redirects=True)
        ):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

    def test_user_stays_logged_in_after_search(self):
        self.test_user_login_flow()
        with self.html_validator.validate_response(
            self.flask_client.post(
                "/",
                data={
                    "query": "lovelace",
                    "method": "name",
                },
            )
        ):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

    def test_user_stays_logged_in_revisit(self):
        self.test_user_login_flow()
        with self.html_validator.validate_response(self.flask_client.get("/")):
            self.html_validator.assert_has_student_search_options()
            self.html_validator.assert_not_has_sign_in_link()

    @pytest.mark.parametrize(
        "search_field, search_value",
        [
            ("name", "bugbear"),
            ("phone", "abcdefg"),
            ("department", "UW-IT IAM"),
            ("box_number", "12345"),
            ("email", "foo@bar.com"),
        ],
    )
    def test_render_no_matches(self, search_field, search_value):
        query_output = self.mock_people.as_search_output()
        self.mock_send_request.return_value = query_output
        with self.html_validator.validate_response(
            self.flask_client.post(
                "/", data={"method": search_field, "query": search_value}
            )
        ):
            self.html_validator.assert_has_tag_with_text(
                "p", f'no matches for {titleize(search_field)} is "{search_value}"'
            )

    def assert_form_fields_match_expected(
        self,
        response,
        expected: SearchDirectoryFormInput,
        signed_in: bool,
        recurse: bool = True,
    ):
        """
        Given a query response, ensures that the user flow thereafter is as expected; if
        the query resulted in summary results with a "more" button, this also simulates
        the button request to ensure that the same state is preserved through
        the next search request.
        """
        with self.html_validator.validate_response(response) as html:
            # Someone not signed in who posts a different population will not
            # have the population options displayed that they selected,
            # so we skip this check. (No actual user that is using
            # our website normally will encounter this situation,
            # but it's technically a possibility.)
            if signed_in or expected.population == "employees":
                assert (
                    "checked"
                    in html.find(
                        "input",
                        attrs={"id": f"population-option-{expected.population}"},
                    ).attrs
                )

            # Ensure that the sign in link is (or is not) visible, based on whether the user
            # is signed in.
            self.html_validator.has_sign_in_link(
                assert_=True, assert_expected_=not signed_in
            )

            # Ensure that the form field is filled in with the same information as was input.
            assert (
                html.find("input", attrs={"name": "query"}).attrs.get("value")
                == expected.query
            )

            # Ensure that the result detail option is preserved
            assert (
                "checked"
                in html.find("input", attrs={"id": f"length-{expected.length}"}).attrs
            )

            # Ensure that the search field is selected in the form dropdown
            assert (
                "selected"
                in html.find("option", attrs={"value": expected.method}).attrs
            )

            # We don't always expect results. For our current test ecosystem,
            # we won't see results if:
            expect_results = signed_in or expected.population != "students"

            # If we don't expect results, we do expect a message telling us
            # that there are no results.
            if not expect_results:
                self.html_validator.assert_has_tag_with_text(
                    "p",
                    f'No matches for {titleize(expected.method)} is "{expected.query}"',
                )
            # If we have "More" buttons, we simulate clicking on them to ensure that
            # the buttons properly set render_ options.
            elif recurse and expected.length == "summary":
                # Ensure that the same values are carried into the "More" render
                more_button = html.find("form", id="more-form-1")
                assert more_button, str(html)
                request_input = self._get_request_input_from_more_button(more_button)
                self.assert_form_fields_match_expected(
                    self.flask_client.post("/", data=request_input.dict()),
                    expected,
                    signed_in=signed_in,
                    recurse=False,
                )

    @staticmethod
    def _get_request_input_from_more_button(
        button: BeautifulSoup,
    ) -> SearchDirectoryFormInput:
        """This iterates through the hidden input elements that make up our
        "more form", which is a form masquerading as a button for the time being.
        The element values are serialized into the same request input that
        clicking on the button would generate, so that we can validate the
        correct options were set, and that the server renders those
        overrides correctly.
        """

        def get_field_value(field):
            return button.find("input", attrs=dict(name=field)).attrs.get("value")

        return SearchDirectoryFormInput(
            population=get_field_value("population"),
            query=get_field_value("query"),
            method=get_field_value("method"),
            length=get_field_value("length"),
            render_query=get_field_value("render_query"),
            render_method=get_field_value("render_method"),
            render_length=get_field_value("render_length"),
        )

    @pytest.mark.parametrize("search_field", SearchDirectoryInput.search_methods())
    @pytest.mark.parametrize("population", ("employees", "students", "all"))
    @pytest.mark.parametrize("sign_in", (True, False))
    @pytest.mark.parametrize("result_detail", ("full", "summary"))
    def test_render_form_option_stickiness(
        self, search_field, population, sign_in, result_detail
    ):
        """
        This uses combinatoric parametrize calls to run through every combination of
        options and ensure that, after rendering, everything is rendered as we expect
        based on the search parameters.

        This generates tests for every combination of the parametrized fields listed above,
        so that we can have a great deal of confidence that the page is rendering as expected
        based on its input.
        """
        query_value = (
            "lovelace" if search_field not in ("phone", "box_number") else "12345"
        )

        request = SearchDirectoryFormInput(
            method=search_field,
            population=PopulationType(population),
            length=ResultDetail(result_detail),
            query=query_value,
        )

        if sign_in:
            with self.html_validator.validate_response(
                self.flask_client.get("/saml/login", follow_redirects=True)
            ) as html:
                self.html_validator.assert_not_has_sign_in_link()
                assert html.find("label", attrs={"for": "population-option-students"})

        response = self.flask_client.post("/", data=request.dict())
        self.assert_form_fields_match_expected(response, request, sign_in, recurse=True)

    def test_get_person_method_not_allowed(self):
        response = self.flask_client.get("/person/listing")
        assert response.status_code == 405

    @pytest.mark.parametrize("search_term", ["Smith", "Lovelace"])
    def test_get_person_non_matching_surname(self, search_term):
        """Ensures that our name constraints work by setting
        a preferred last name that is different than the registered
        last name, and searching for the registered last name.
        """
        profile = self.mock_people.published_employee
        profile.preferred_last_name = "Smith"
        profile.display_name = "Ada Smith"

        expected_num_results = 1 if profile.preferred_last_name == search_term else 0

        self.mock_send_request.return_value = self.mock_people.as_search_output(profile)

        response = self.flask_client.post(
            "/", data={"method": "name", "query": search_term}
        )
        assert response.status_code == 200
        with self.html_validator.validate_response(response) as html:
            assert (
                len(html.find_all("tr", class_="summary-row")) == expected_num_results
            ), str(html)

    def test_list_people_sort(self, random_string):
        ada_1 = self.mock_people.published_employee.copy(
            update={
                "display_name": "Ada Zlovelace",
                "preferred_last_name": "Zlovelace",
                "registered_surname": "Alovelace",
                "netid": random_string(),
            },
            deep=True,
        )
        ada_1.affiliations.employee.directory_listing.phones = ["222-2222"]
        ada_2 = self.mock_people.published_employee.copy(
            update={
                "display_name": "Ada Blovelace",
                "registered_surname": "Blovelace",
                "netid": random_string(),
            },
            deep=True,
        )
        ada_2.affiliations.employee.directory_listing.phones = ["888-8888"]
        ada_3 = self.mock_people.published_employee.copy(
            update={
                "display_name": "Ada Alovelace",
                "preferred_last_name": "Alovelace",
                "netid": random_string(),
            },
            deep=True,
        )
        ada_3.affiliations.employee.directory_listing.phones = ["999-9999"]
        people = self.mock_people.as_search_output(ada_1, ada_2, ada_3)

        self.mock_send_request.return_value = people
        response = self.flask_client.post(
            "/",
            data={"method": "name", "query": "lovelace"},
        )
        html = response.data.decode("UTF-8")
        assert response.status_code == 200
        assert html.index("999-9999") < html.index("888-8888")
        assert html.index("888-8888") < html.index("222-2222")

    def test_get_set_cookie(self):
        # First, we make sure that the default is set to "summary"

        def assert_is_checked(rv: Response, length: str):
            with self.html_validator.validate_response(rv) as html:
                assert (
                    "checked"
                    in html.find("input", attrs={"id": f"length-{length}"}).attrs
                )

        response = cast(Response, self.flask_client.get("/"))
        assert_is_checked(response, "summary")

        # Then, we make a second request and change it to "full"
        response = cast(
            Response,
            self.flask_client.post(
                "/", data={"method": "name", "query": "lovelace", "length": "full"}
            ),
        )
        assert_is_checked(response, "full")

        # Now on a fresh get(), "full" should still be selected.
        response = cast(Response, self.flask_client.get("/"))
        assert_is_checked(response, "full")

    def test_get_person_vcard(self):
        """
        Tests that the blueprint returns the right result, but does not test
        permutations of vcards; for that see, tests/services/vcard.py
        """
        person = self.mock_people.published_employee
        href = base64.b64encode("foo".encode("UTF-8")).decode("UTF-8")
        self.mock_send_request.return_value = person.dict(by_alias=True)
        response = self.flask_client.post("/person/vcard", data={"person_href": href})
        assert response.status_code == 200
        assert response.mimetype == "text/vcard"
        vcard = response.data.decode("UTF-8")
        assert vcard.startswith("BEGIN:VCARD")
        assert vcard.endswith("END:VCARD")

    @pytest.mark.parametrize("succeed", (True, False))
    def test_get_person_listing(self, succeed: bool):
        person = self.mock_people.contactable_person
        href = base64.b64encode("foo".encode("UTF-8")).decode("UTF-8")
        if succeed:
            self.mock_send_request.return_value = person.dict(by_alias=True)
        else:
            self.mock_send_request.side_effect = exceptions.NotFound
        response = self.flask_client.post("/person/listing", data={"person_href": href})
        if succeed:
            assert response.status_code == 200
            with self.html_validator.validate_response(response):
                self.html_validator.assert_has_tag_with_text("h4", "Ada Lovelace")
        else:
            assert response.status_code == 404
            with self.html_validator.validate_response(response):
                self.html_validator.assert_has_tag_with_text("p", "404 not found")
