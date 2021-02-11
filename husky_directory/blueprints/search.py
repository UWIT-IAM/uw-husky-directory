from enum import Enum
from logging import Logger
from typing import Optional

from flask import Blueprint, Request, jsonify, redirect, render_template
from injector import inject, singleton
from pydantic import validate_model

from husky_directory.models.search import (
    DirectoryBaseModel,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.search import DirectorySearchService


class ErrorModel(DirectoryBaseModel):
    msg: str


class ResultDetail(Enum):
    full = "full"
    summary = "summary"


class DisplayPreferences(DirectoryBaseModel):
    length: ResultDetail = ResultDetail.summary
    show_count: bool = False


class RenderingContext(DirectoryBaseModel):
    request_input: Optional[SearchDirectoryInput]
    search_result: Optional[SearchDirectoryOutput]
    error: Optional[ErrorModel]
    status_code: int = 200
    display: DisplayPreferences = DisplayPreferences()


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
            request.content_type not in ("text/javascript", "application/javascript")
            and not request.args
        ):
            return redirect("/")
        request_input = SearchDirectoryInput.parse_obj(request.args)
        self.logger.info(f"searching for {request_input}")
        request_output = search_service.search_directory(request_input)
        return jsonify(
            request_output.dict(by_alias=True, exclude_none=True, exclude_unset=True)
        )

    @staticmethod
    def render(request: Request, service: DirectorySearchService, logger: Logger):
        # In order to make sure that even if the user input is wrong, we can still
        # re-populate the html form the way the user submitted, we bypass the
        # pydantic error-raising by using its `validate_model` function instead,
        # which will find errors without raising them . . .
        *_, validation_error = validate_model(SearchDirectoryInput, request.form)
        # . . . then, we use the `construct` method to bypass the validation of the model,
        # since we have already manually validated it above. This has the effect of
        # preserving the user input, even if it was wrong, without sacrificing
        # the actual validation we want to perform.
        request_input = SearchDirectoryInput.construct(**request.form)
        context = RenderingContext(
            # No matter what, we pass back the original request input.
            request_input=request_input,
            # We also populate any display preferences from the form data;
            # if those preferences aren't defined for some reason, the default values will be used.
            display=DisplayPreferences.parse_obj(request.form),
        )
        # Now we handle our validation errors (that pydantic would have thrown),
        # and set the error in the rendering context.
        if validation_error:
            context.error = ErrorModel.parse_obj(validation_error.errors()[0])
            context.status_code = 400
        else:
            # If we've made it this far, the user has given us valid input,
            # so we can attempt to query the information they asked for.
            try:
                context.search_result = service.search_directory(request_input)
            except Exception as e:
                # But if we meet an exception here, we probably aren't expecting it,
                # and should give the user a next step (as well as emit an error
                # so that developers can debug and fix). We do this by setting
                # the error context (just as we would have above in case of a validation error).
                logger.exception(str(e))
                context.status_code = 500
                context.error = ErrorModel(
                    msg="Something unexpected happened. Please try again or "
                    "email help@uw.edu describing your problem."
                )
        return (
            # Now we render the template with the full context every time!
            render_template("index.html", **context.dict(exclude_none=True)),
            context.status_code,
        ), context.status_code
