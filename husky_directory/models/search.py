"""
Models for the DirectorySearchService.
"""
from typing import List, Optional

from pydantic import BaseModel, Extra, Field

from husky_directory.util import camelize


class DirectoryBaseModel(BaseModel):
    class Config:
        extra = Extra.ignore
        use_enum_values = True
        allow_population_by_field_name = True
        validate_assignment = True
        alias_generator = camelize


class SearchDirectoryInput(DirectoryBaseModel):
    name: Optional[str] = Field(None, max_length=128)
    department: Optional[str] = Field(None, max_length=128)
    email: Optional[str] = Field(
        None, max_length=256
    )  # https://tools.ietf.org/html/rfc5321#section-4.5.3
    box_number: Optional[str] = Field(None, regex="^[0-9]+$", max_length=32)
    phone: Optional[str] = Field(None, regex=r"^[0-9]+$", max_length=32)
    netid: Optional[str] = Field(None)


class PhoneContactMethods(DirectoryBaseModel):
    # These aliases are for humans, instead of for computers, so use
    # human conventions for the front end to display.
    phones: List[str] = Field([], alias="phone")
    faxes: List[str] = Field([], alias="fax")
    voice_mails: List[str] = Field([], alias="voicemail")
    touch_dials: List[str] = Field([], alias="tdd")
    mobiles: List[str] = Field([], alias="mobile")
    pagers: List[str] = Field([], alias="pager")


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
    query: SearchDirectoryInput
    num_results: int
    scenarios: List[DirectoryQueryScenarioOutput]
