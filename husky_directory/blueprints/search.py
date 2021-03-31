from logging import Logger
from typing import Optional

from flask import Blueprint, Request, jsonify, redirect, render_template
from inflection import humanize, underscore
from injector import inject, singleton
from pydantic import ValidationError
from werkzeug.local import LocalProxy

from husky_directory.models.search import (
    DirectoryBaseModel,
    SearchDirectoryInput,
    SearchDirectoryOutput,
    SearchDirectorySimpleInput,
)
from husky_directory.services.search import DirectorySearchService


class ErrorModel(DirectoryBaseModel):
    msg: str


class RenderingContext(DirectoryBaseModel):
    request_input: Optional[SearchDirectorySimpleInput]
    search_result: Optional[SearchDirectoryOutput]
    error: Optional[ErrorModel]
    status_code: int = 200
    uwnetid: Optional[str] = None


@singleton
class SearchBlueprint(Blueprint):
    @inject
    def __init__(self, logger: Logger):
        super().__init__("search", __name__, url_prefix="/search")
        self.logger = logger
        self.add_url_rule("/", view_func=self.get, methods=("GET",))
        self.add_url_rule("/", view_func=self.render, methods=("POST",))

    def get(self, request: Request, search_service: DirectorySearchService):
        # In this case, we should assume a user just typed in the /search, which is fine.
        if (
            request.content_type
            not in ("search_text/javascript", "application/javascript")
            and not request.args
        ):
            return redirect("/")
        request_input = SearchDirectoryInput.parse_obj(request.args)
        self.logger.info(f"searching for {request_input}")
        request_output = search_service.search_directory(request_input)
        return jsonify(request_output.dict(by_alias=True, exclude_none=True))

    @staticmethod
    def render(
        request: Request,
        service: DirectorySearchService,
        logger: Logger,
        session: LocalProxy,
    ):
        context = RenderingContext.construct()
        try:
            simple_query = SearchDirectorySimpleInput.parse_obj(request.form)
            context.request_input = simple_query
            request_input = SearchDirectoryInput.from_simple_input(simple_query)
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
                logger.error("WTF")
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
