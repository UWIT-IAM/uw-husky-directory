"""
Models for the DirectorySearchService.
"""

from typing import List, Optional

import inflection
from pydantic import BaseModel, Extra, Field


class DirectoryBaseModel(BaseModel):
    class Config:
        extra = Extra.ignore
        use_enum_values = True
        allow_population_by_field_name = True
        validate_assignment = True

        @staticmethod
        def to_camel(s: str) -> str:
            return inflection.camelize(s, uppercase_first_letter=False)

        alias_generator = to_camel


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


class SearchDirectoryOutput(DirectoryBaseModel):
    people: List[Person] = []
