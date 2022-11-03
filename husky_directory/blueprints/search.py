from base64 import b64decode
from typing import Optional, Union

from flask import (
    Blueprint,
    Request,
    Response,
    make_response,
    render_template,
    send_file,
)
from inflection import humanize, underscore
from injector import Injector, inject, singleton
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.local import LocalProxy

from husky_directory.app_config import ApplicationConfig
from husky_directory.models.common import PreferencesCookie
from husky_directory.models.search import (
    DirectoryBaseModel,
    Person,
    SearchDirectoryFormInput,
    SearchDirectoryInput,
    SearchDirectoryOutput,
)
from husky_directory.services.search import DirectorySearchService
from husky_directory.services.vcard import VCardService
from husky_directory.util import AppLoggerMixIn


class ErrorModel(DirectoryBaseModel):
    msg: str


class RenderingContext(DirectoryBaseModel):
    class Config(DirectoryBaseModel.Config):
        validate_assignment = False

    request_input: Optional[SearchDirectoryFormInput]
    search_result: Optional[Union[SearchDirectoryOutput, Person]]
    error: Optional[ErrorModel]
    status_code: int = 200
    uwnetid: Optional[str] = None
    show_experimental: bool = False


@singleton
class SearchBlueprint(Blueprint, AppLoggerMixIn):
    @inject
    def __init__(self, injector: Injector):
        super().__init__("search", __name__)
        self.injector = injector
        self.add_url_rule("/", view_func=self.index, methods=("GET",))
        self.add_url_rule("/", view_func=self.search_listing, methods=("POST",))
        self.add_url_rule(
            "/person/listing", view_func=self.get_person_listing, methods=("POST",)
        )
        self.add_url_rule(
            "/person/vcard",
            view_func=self.get_person_vcard,
            methods=("POST",),
        )

    @staticmethod
    def index(request: Request, session: LocalProxy, settings: ApplicationConfig):
        preferences_cookie = request.cookies.get(
            settings.session_settings.preferences_cookie_name
        )
        if preferences_cookie:
            preferences = PreferencesCookie.parse_raw(preferences_cookie)
        else:
            preferences = PreferencesCookie()
        context = RenderingContext.construct(
            uwnetid=session.get("uwnetid"),
            show_experimental=settings.show_experimental,
            request_input=SearchDirectoryFormInput.construct(
                render_length=preferences.result_detail
            ),
        )
        return (
            render_template("views/index.html", **context.dict(exclude_none=True)),
            200,
        )

    def get_person_listing(
        self,
        request: Request,
        session: LocalProxy,
        service: DirectorySearchService,
    ):
        context = RenderingContext.construct(
            uwnetid=session.get("uwnetid"),
        )
        template = "views/person.html"
        try:
            request_input = SearchDirectoryFormInput.parse_obj(request.form)
            context.request_input = request_input
            context.search_result = service.get_listing(
                b64decode(request_input.person_href.encode("UTF-8")).decode("UTF-8")
            )
        except Exception as e:
            template = "views/index.html"
            self.logger.exception(str(e))
            SearchBlueprint.handle_search_exception(e, context)
        finally:
            return (
                render_template(template, **context.dict(exclude_none=True)),
                context.status_code,
            )

    @staticmethod
    def get_person_vcard(request: Request, vcard_service: VCardService):
        href_token = request.form.get("person_href")
        if not href_token:
            raise BadRequest("No href token provided")
        vcard_stream = vcard_service.get_vcard(
            b64decode(href_token.encode("UTF-8")).decode("UTF-8")
        )
        return send_file(vcard_stream, mimetype="text/vcard")

    @staticmethod
    def handle_search_exception(e: Exception, context: RenderingContext):
        if isinstance(e, ValidationError):
            context.status_code = 400
            bad_fields = []
            for error in e.errors():
                field_name = humanize(underscore(error["loc"][0])).lower()
                message = error["msg"]
                bad_fields.append(f"{field_name} ({message})")
            context.error = ErrorModel(msg=f"Invalid input for {'; '.join(bad_fields)}")
        elif isinstance(e, HTTPException):
            context.error = ErrorModel(msg=str(e))
            context.status_code = e.code
        else:
            context.status_code = 500
            context.error = ErrorModel(
                msg="Something unexpected happened. Please try again or "
                "email help@uw.edu describing your problem."
            )

    @staticmethod
    def set_preferences_for_cookie(context: RenderingContext):
        """
        When the search query is too short, the request_input data is dropped, but we still need a value for
        'result_detail'
        """
        result_detail = 'summary'
        if context.request_input and context.request_input.length:
            result_detail = context.request_input.length

        preferences = PreferencesCookie(
            result_detail=result_detail
        ).json(exclude_unset=True, exclude_none=True)
        return preferences

    def search_listing(
        self,
        request: Request,
        service: DirectorySearchService,
        session: LocalProxy,
        settings: ApplicationConfig,
    ):
        context = RenderingContext.construct(
            uwnetid=session.get("uwnetid"),
            show_experimental=settings.show_experimental,
        )
        self.logger.info(f'before context = {context}')
        self.logger.info(f'request.form = {request.form}')
        try:
            form_input = SearchDirectoryFormInput.parse_obj(request.form)
            self.logger.info('glen')
            context.request_input = form_input

            request_input = SearchDirectoryInput.from_form_input(form_input)
            self.logger.info(f'request_input = {request_input}')
            context.search_result = service.search_directory(request_input)
            self.logger.info(f'context.search_result = {context.search_result}')
        except Exception as e:
            self.logger.exception(str(e))
            SearchBlueprint.handle_search_exception(e, context)
        finally:
            if not context.request_input:
                self.logger.info('got the error')
                context.request_input = \
                    SearchDirectoryFormInput(method=request.form['method'],
                                             population=request.form['population'],
                                             length=request.form['length'],
                                             render_method=request.form['method'],
                                             render_population=request.form['population'],
                                             render_length=request.form['length'],
                                             include_test_identities=False)

            response: Response = make_response(
                render_template(
                    "views/search_results.html", **context.dict(exclude_none=True)
                ),
                context.status_code,
            )
            self.logger.info(f"context = {context}")
            self.logger.info(f"request.form = {request.form}")

            preferences = self.set_preferences_for_cookie(context)
            response.set_cookie(
                settings.session_settings.preferences_cookie_name, value=preferences
            )
            return response
