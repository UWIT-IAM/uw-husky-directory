"""
Models for the DirectorySearchService.
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional

from pydantic import Field, PydanticValueError, validator

from husky_directory.models.base import DirectoryBaseModel
from husky_directory.models.enum import PopulationType, ResultDetail


class BoxNumberValueError(PydanticValueError):
    """
    We raise the custom BoxNumberValueError to closely match the legacy directory product,
    however we add a little extra messaging in that error to be nicer to user.
    """

    code = "invalid_mail_box"
    msg_template = "invalid mailbox number; must be value of at most 6 digits"


class SearchDirectorySimpleInput(DirectoryBaseModel):
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
    include_test_identities: bool = False
    length: ResultDetail = ResultDetail.summary


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
        None, search_method=True, min_length=0, max_length=6, regex="^([0-9]+)?$"
    )
    phone: Optional[str] = Field(None, search_method=True)
    population: PopulationType = PopulationType.employees
    include_test_identities: bool = False

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

    @property
    def requested_populations(self) -> List[PopulationType]:
        if self.population == PopulationType.all.value:
            return [PopulationType.employees.value, PopulationType.students.value]
        return [self.population]

    @classmethod
    def from_simple_input(
        cls, simple: SearchDirectorySimpleInput
    ) -> SearchDirectoryInput:
        args = simple.dict()
        args[args["method"]] = args["query"]
        return cls(**args)


class PhoneContactMethods(DirectoryBaseModel):
    # These aliases are for humans, instead of for computers, so use
    # human conventions for the front end to display.
    phones: List[str] = []
    faxes: List[str] = []
    voice_mails: List[str] = []
    touch_dials: List[str] = []
    mobiles: List[str] = []
    pagers: List[str] = []


class Person(DirectoryBaseModel):
    name: str
    phone_contacts: PhoneContactMethods = PhoneContactMethods()
    email: Optional[str]
    box_number: Optional[str]
    department: Optional[str]


class DirectoryQueryPopulationOutput(DirectoryBaseModel):
    population: PopulationType
    people: List[Person] = []

    @property
    def num_results(self) -> int:
        return len(self.people)


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
