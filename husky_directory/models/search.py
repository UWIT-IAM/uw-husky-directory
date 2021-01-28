"""
Models for the DirectorySearchService.
"""
import re
from typing import List, Optional

from pydantic import BaseModel, Extra, Field, validator

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


class Person(DirectoryBaseModel):
    name: str
    phone: Optional[str]
    email: Optional[str]
    box_number: Optional[str]
    department: Optional[str]

    @validator("phone", pre=True)
    def remove_phone_non_digits(cls, phone: str):
        if phone:
            return re.sub("[^0-9]", "", phone)
        return phone

    @validator("name")
    def validate_name_words(cls, name: str) -> str:
        """
        Currently the search only supports up to 3 words in a user's name. Otherwise the combinatorics
        get a little ridiculous, and although there are folks with more than 3 'words' they should still be
        findable.
        """
        if name:
            assert len(name.split()) <= 5
        return name


class DirectoryQueryScenarioOutput(DirectoryBaseModel):
    description: str
    people: List[Person] = []


class SearchDirectoryOutput(DirectoryBaseModel):
    query: SearchDirectoryInput
    num_results: int
    scenarios: List[DirectoryQueryScenarioOutput]
