from base64 import b64decode
from logging import Logger
from typing import Optional

from flask import Blueprint, Request, redirect, render_template, send_file
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

    def get(self, request: Request):
        """
        The /search endpoint only supports POST, but because it
        will appear in users' browser histories, we set a default GET
        path to nicely redirect back to the home page.
        """
        return redirect("/")

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
                form_input = SearchDirectoryFormInput(
                    render_query=request.form.get("query"),
                    render_method=request.form.get("method"),
                    render_population=request.form.get("population"),
                    render_length=request.form.get("length"),
                )
                context.request_input = form_input
                bad_fields = []
                for error in e.errors():
                    field_name = humanize(underscore(error["loc"][0])).lower()
                    message = error["msg"]
                    bad_fields.append(f"{field_name} ({message})")
                context.error = ErrorModel(
                    msg=f"Invalid input for {'; '.join(bad_fields)}"
                )
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
