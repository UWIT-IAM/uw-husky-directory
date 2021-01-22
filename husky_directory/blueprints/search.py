from logging import Logger

from flask import Blueprint, Request, jsonify
from injector import inject, singleton
from flask import render_template

from husky_directory.models.search import SearchDirectoryInput
from husky_directory.services.search import DirectorySearchService


@singleton
class SearchBlueprint(Blueprint):
    @inject
    def __init__(self, logger: Logger):
        super().__init__("search", __name__, url_prefix="/search")
        self.logger = logger
        self.add_url_rule("/", view_func=self.search)

    def search(self, request: Request, search_service: DirectorySearchService):
        request_input = SearchDirectoryInput.parse_obj(request.args)
        self.logger.info(f"searching for {request_input}")
        request_output = search_service.search_directory(request_input)
        result = {
            descr: result.dict(by_alias=True)
            for descr, result in request_output.items()
        }
        search_result = jsonify(result)
        return render_template('index.html', search_result=search_result.get_json())
