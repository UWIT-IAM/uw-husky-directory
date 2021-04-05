from base64 import b64decode
from logging import Logger
from typing import Optional

from flask import Blueprint, Request, jsonify, render_template, send_file
from inflection import humanize, underscore
from injector import Injector, inject, singleton
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest
from werkzeug.local import LocalProxy

from husky_directory.models.search import (
    DirectoryBaseModel,
    SearchDirectoryFormInput,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.search import DirectorySearchService
from husky_directory.services.vcard import VCardService


class ErrorModel(DirectoryBaseModel):
    msg: str


class RenderingContext(DirectoryBaseModel):
    request_input: Optional[SearchDirectoryFormInput]
    search_result: Optional[SearchDirectoryOutput]
    error: Optional[ErrorModel]
    status_code: int = 200
    uwnetid: Optional[str] = None


@singleton
class SearchBlueprint(Blueprint):
    @inject
    def __init__(self, logger: Logger, injector: Injector):
        super().__init__("search", __name__, url_prefix="/search")
        self.injector = injector
        self.logger = logger
        self.add_url_rule("/", view_func=self.get, methods=("GET",))
        self.add_url_rule("/", view_func=self.render, methods=("POST",))
        # When no output format is provided, defaults to html
        self.add_url_rule(
            "/person/<href_token>",
            defaults={"output_format": "html"},
            view_func=self.get_person,
            methods=("GET", "POST"),
        )
        # /person/{token}/vcard
        # defaults to 'html' (above)
        self.add_url_rule(
            "/person/<href_token>/<output_format>",
            view_func=self.get_person,
            methods=("GET", "POST"),
        )

    @property
    def vcard_service(self):
        # Create an ad-hoc instance so that it has access to
        # request session parameters (as opposed to a
        # singleton instance)
        return self.injector.get(VCardService)

    def get(self, request: Request, search_service: DirectorySearchService):
        """
        An API call, returning JSON output. Not actively used by
        any existing flows, but useful for testing/debugging,
        and may be useful to customers. Uses the SearchDirectoryInput model
        by way of query parameters.
            directory.uw.edu/search?name=foo&population=employees

        Returns a jsonified instance of SearchDirectoryOutput
        """
        request_input = SearchDirectoryInput.parse_obj(request.args)
        self.logger.info(f"searching for {request_input}")
        request_output = search_service.search_directory(request_input)
        return jsonify(request_output.dict(by_alias=True, exclude_none=True))

    def get_person(
        self,
        request: Request,
        href_token: str,
        output_format: str,
    ):
        """
        Given a specific person HREF, retrieves the person and returns their results.
        For this, the population is always "all," but student data will be excluded
        for requests that are not authenticated.
        """
        if output_format == "vcard":
            return self.get_person_vcard(href_token)
        else:  # We can expand this as needed.
            raise BadRequest("Invalid output type requested")

    def get_person_vcard(self, href_token: str):
        vcard_stream = self.vcard_service.get_vcard(
            b64decode(href_token.encode("UTF-8")).decode("UTF-8")
        )
        return send_file(vcard_stream, mimetype="text/vcard")

    @staticmethod
    def render(
        request: Request,
        service: DirectorySearchService,
        logger: Logger,
        session: LocalProxy,
    ):
        context = RenderingContext.construct()
        try:
            form_input = SearchDirectoryFormInput.parse_obj(request.form)
            context.uwnetid = session.get("uwnetid")
            context.request_input = form_input

            request_input = SearchDirectoryInput.from_form_input(form_input)
            context.search_result = service.search_directory(request_input)

        except Exception as e:
            # But if we meet an exception here, we probably aren't expecting it,
            # and should give the user a next step (as well as emit an error
            # so that developers can debug and fix). We do this by setting
            # the error context (just as we would have above in case of a validation error).
            logger.exception(str(e))
            if isinstance(e, ValidationError):
                context.status_code = 400
                bad_fields = [humanize(underscore(err["loc"][0])) for err in e.errors()]
                context.error = ErrorModel(msg=f"Invalid {', '.join(bad_fields)}")
            else:
                context.status_code = 500
                context.error = ErrorModel(
                    msg="Something unexpected happened. Please try again or "
                    "email help@uw.edu describing your problem."
                )
        finally:
            return (
                # Now we render the template with the full context every time!
                render_template("index.html", **context.dict(exclude_none=True)),
                context.status_code,
            )
