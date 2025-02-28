"""
Models for the DirectorySearchService.
"""
from __future__ import annotations

import base64
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import Field, PydanticValueError, validator

from husky_directory.models.base import DirectoryBaseModel
from husky_directory.models.common import UWDepartmentRole
from husky_directory.models.enum import PopulationType, ResultDetail

# There is no direct dependency on the model here, we only need it for type checking;
# this protects us from accidentally creating a cyclic dependency between the modules.
if TYPE_CHECKING:
    pass

BOX_NUMBER_REGEX = re.compile("^([0-9]+)?$")


class BoxNumberValueError(PydanticValueError):
    """
    We raise the custom BoxNumberValueError to closely match the legacy directory product,
    however we add a little extra messaging in that error to be nicer to user.
    """

    code = "invalid_mail_box"
    msg_template = "invalid mailbox number; must be value of at most 6 digits"


class SearchDirectoryFormInput(DirectoryBaseModel):
    """
    A lightweight layer to make it easier for the existing front-end
    to query. The backend was written with JSON in mind, but the front-end
    is just using a simple form that it required us to use javascript
    to correctly interact with the backend; this SimpleInput model
    removes this necessity and makes everything a lot easier.
    """

    method: str = "name"
    query: str = ""
    population: PopulationType = PopulationType.employees
    length: ResultDetail = ResultDetail.summary
    person_href: Optional[str]

    # render_ fields are provided as a way to search one thing,
    # but provide a different context to the rendering engine
    # when populating the user interface. If render_ options
    # are provided in the form input, those fields will be
    # rendered with the values provided, even if the query was
    # for a different set of options.
    # render_ fields must be declared after the above, so that these
    # fields can derive their default from their "first-class"
    # parameter name.
    render_method: Optional[str]
    render_query: Optional[str]
    render_population: Optional[PopulationType]
    render_length: Optional[ResultDetail]

    include_test_identities: bool = False  # Not currently supported

    @staticmethod
    def strip_query_illegal_chars(v: str) -> str:
        """
        PWS is OK with most special chars, and many may be found
        in our population's names.
        The '\' character is not one of them. (And maybe more?)
        For those, we'll assume a typo, and just strip them on input.
        """
        if not v:
            return ""
        v = re.sub(r"[\\]", "", v)  # remove illegal chars
        v = re.sub(r"[\t]", " ", v)  # replace whitespace chars
        tokens = list(filter(bool, v.split()))  # Condense multiple spaces to one space
        return " ".join(tokens)

    @validator("query")
    def validate_query(cls, v: str, values: Dict[str, Any]) -> str:
        v = SearchDirectoryFormInput.strip_query_illegal_chars(v)
        if values.get("method") == "name":
            if len(v) < 2:
                raise ValueError("Name query string must contain at least 2 characters")
            # Allow users to input "last, first" for names.
            if "," in v:
                tokens = reversed(v.split(","))
                v = " ".join(tokens).strip()
        elif len(v) < 3:
            raise ValueError("Query string must contain at least 3 characters")
        return v

    # These methods ensure that, by default, the render_ fields have
    # the same value as the query value.
    @validator("render_method", always=True)
    def populate_render_method(cls, method: Optional[str], values):
        if not method:
            return values.get("method")
        return method

    @validator("render_query", always=True)
    def populate_render_query(cls, query: Optional[str], values):
        if not query:
            return values.get("query")
        return query

    @validator("render_population", always=True)
    def populate_render_population(cls, population: Optional[str], values):
        if not population:
            return values.get("population")
        return population

    @validator("render_length", always=True)
    def populate_render_length(cls, length: Optional[str], values):
        if not length:
            return values.get("length")
        return length


class SearchDirectoryInput(DirectoryBaseModel):
    """
    This is the input model for the /search API endpoint.
    Fields with `search_method=True` will be included in the drop down menu as search methods.
    """

    name: Optional[str] = Field(None, max_length=128, search_method=True)
    department: Optional[str] = Field(None, max_length=128, search_method=True)
    email: Optional[str] = Field(
        None, max_length=256, search_method=True
    )  # https://tools.ietf.org/html/rfc5321#section-4.5.3
    box_number: Optional[str] = Field(
        None,
        search_method=True,
        min_length=0,
        max_length=6,
    )
    phone: Optional[str] = Field(None, search_method=True)
    population: PopulationType = PopulationType.employees
    include_test_identities: bool = False
    person_href: Optional[str]

    @classmethod
    def search_methods(cls) -> List[str]:
        fields: Dict[str, Field] = cls.__fields__
        return [
            f_name
            for f_name, f in fields.items()
            if f.field_info.extra.get("search_method")
        ]

    @property
    def sanitized_phone(self) -> Optional[str]:
        if self.phone:
            return re.sub("[^0-9]", "", self.phone)
        return self.phone

    @validator("email")
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value and value.startswith(
            "@"
        ):  # Don't let people search for everyone at @uw.edu or @washington.edu
            raise ValueError(
                "Unable to search by domain only; please start with the username portion of the address."
            )
        return value

    @validator("box_number")
    def validate_box_number(cls, value: Optional[str]) -> Optional[str]:
        """
        In order to keep users from seeing the ugly default error message
        that pydantic provides for a regex validation, we give our users
        something a little nicer.
        :param value:
        :return:
        """
        if value and not re.match(BOX_NUMBER_REGEX, value):
            raise ValueError("input can only contain digits")
        return value

    @property
    def requested_populations(self) -> List[PopulationType]:
        if self.population == PopulationType.all.value:
            return [PopulationType.employees.value, PopulationType.students.value]
        return [self.population]

    @classmethod
    def from_form_input(
        cls, simple: SearchDirectoryFormInput, validate: bool = True
    ) -> SearchDirectoryInput:
        args = simple.dict()
        args[args["method"]] = args["query"]
        if validate:
            return cls(**args)
        return cls.construct(**args)


class PhoneContactMethods(DirectoryBaseModel):
    class Config(DirectoryBaseModel.Config):
        orm_mode = True

    phones: List[str] = []
    faxes: List[str] = []
    voice_mails: List[str] = []
    touch_dials: List[str] = []
    mobiles: List[str] = []
    pagers: List[str] = []


class Person(DirectoryBaseModel):
    name: str
    phone_contacts: PhoneContactMethods = PhoneContactMethods()
    emails: List[str] = []
    box_number: Optional[str]
    departments: List[UWDepartmentRole] = []
    sort_key: Optional[str]
    populations: List[PopulationType] = []

    href: str

    @validator("href")
    def b64_encode_href(cls, value: str) -> str:
        """
        Base64 encode href only if not already encoded.
        Prevents double-encoding after browser back navigation when href
        from previous page state is already encoded.
        """
        encoding = "UTF-8"
        if not cls._is_base64_encoded(value, encoding):
            return base64.b64encode(value.encode(encoding)).decode(encoding)
        return value

    @staticmethod
    def _is_base64_encoded(value: str, encoding: str = "UTF-8") -> bool:
        """
        Check if a string is already base64 encoded.
        """
        try:
            return base64.b64decode(value.encode(encoding)).decode(encoding) is not None
        except (ValueError, UnicodeDecodeError):
            return False

    @validator("sort_key", always=True)
    def set_default_sort_key(cls, v: Optional[str], values: Dict):
        return v if v else values.get("name")


class DirectoryQueryPopulationOutput(DirectoryBaseModel):
    population: PopulationType
    people: List[Person] = []

    @property
    def num_results(self) -> int:
        return len(self.people)

    def dict(self, *args, **kwargs):
        result = super().dict(*args, **kwargs)
        sort_key = "sort_key" if not kwargs.get("by_alias") else "sortKey"
        if result and "people" in result:
            result["people"] = sorted(result["people"], key=lambda p: p[sort_key])
        return result


class DirectoryQueryScenarioOutput(DirectoryBaseModel):
    description: str
    populations: Dict[PopulationType, DirectoryQueryPopulationOutput]

    @property
    def num_results(self) -> int:
        return sum(map(lambda p: p.num_results, self.populations.values()))


class SearchDirectoryOutput(DirectoryBaseModel):
    scenarios: List[DirectoryQueryScenarioOutput] = []

    @property
    def num_results(self) -> int:
        return sum(map(lambda s: s.num_results, self.scenarios))
