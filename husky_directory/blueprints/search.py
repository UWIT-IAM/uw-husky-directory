from logging import Logger

from flask import Blueprint, Request, jsonify, render_template
from injector import inject, singleton
from pydantic import ValidationError

from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.search import DirectorySearchService


@singleton
class SearchBlueprint(Blueprint):
    @inject
    def __init__(self, logger: Logger):
        super().__init__("search", __name__, url_prefix="/search")
        self.logger = logger
        self.add_url_rule("/", view_func=self.search)
        self.add_url_rule("/render", view_func=self.render)

    def search(self, request: Request, search_service: DirectorySearchService):
        request_input = SearchDirectoryInput.parse_obj(request.args)
        self.logger.info(f"searching for {request_input}")
        request_output = search_service.search_directory(request_input)
        return jsonify(
            request_output.dict(by_alias=True, exclude_none=True, exclude_unset=True)
        )

    def render(self, request: Request, service: DirectorySearchService, logger: Logger):
        try:
            return render_template(
                "index.html", search_result=self.search(request, service).get_json()
            )
        except ValidationError as e:
            # By default, the app just returns a BadRequest error, which is fine for
            # an API context, but not so fine when we want to display something
            # meaningful. Since we want to render the view, we pass the error context.
            reportable_error = e.errors()[0]
            return render_template("index.html", error=reportable_error), 401
        except Exception as e:
            logger.exception(str(e))
            return (
                render_template(
                    "index.html",
                    error={
                        "msg": "Something unexpected happened. Please try again or "
                        "email help@uw.edu describing your problem."
                    },
                ),
                500,
            )
