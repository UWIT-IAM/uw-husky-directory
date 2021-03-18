"""
Models for the DirectorySearchService.
"""
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Extra, Field, PydanticValueError, validator

from husky_directory.models.enum import PopulationType
from husky_directory.util import camelize


class DirectoryBaseModel(BaseModel):
    class Config:  # See https://pydantic-docs.helpmanual.io/usage/model_config/
        extra = Extra.ignore
        use_enum_values = True
        allow_population_by_field_name = True
        validate_assignment = True
        alias_generator = camelize
        anystr_strip_whitespace = True


class BoxNumberValueError(PydanticValueError):
    """
    We raise the custom BoxNumberValueError to closely match the legacy directory product,
    however we add a little extra messaging in that error to be nicer to user.
    """

    code = "invalid_mail_box"
    msg_template = "invalid mailbox number; must be value of at most 6 digits"


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
    box_number: Optional[str] = Field(None, search_method=True)
    phone: Optional[str] = Field(None, search_method=True)
    population: PopulationType = PopulationType.employees

    @classmethod
    def search_methods(cls) -> List[str]:
        fields: Dict[str, Field] = cls.__fields__
        return [
            f_name for f_name, f in fields.items() if f.field_info.extra.get('search_method')
        ]

    @property
    def sanitized_phone(self) -> Optional[str]:
        if self.phone:
            return re.sub("[^0-9]", "", self.phone)
        return self.phone

    @validator("box_number")
    def validate_box_number(cls, box_number: Optional[str]) -> Optional[str]:
        if not box_number:
            return box_number

        # We don't do a lot of input validation in the legacy directory product, but
        # this is one of them! This regex guarantees the result is a string of at most 6 digits.
        if not re.match("^[0-9]{1,6}", box_number):
            raise BoxNumberValueError()
        return box_number

    @validator("email")
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value and value.startswith(
            "@"
        ):  # Don't let people search for everyone at @uw.edu or @washington.edu
            raise ValueError(
                "Unable to search by domain only; please start with the username portion of the address."
            )
        return value


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


class DirectoryQueryScenarioOutput(DirectoryBaseModel):
    description: str
    people: List[Person] = []


class SearchDirectoryOutput(DirectoryBaseModel):
    num_results: int = 0
    scenarios: List[DirectoryQueryScenarioOutput] = []
