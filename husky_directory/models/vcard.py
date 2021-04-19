from enum import Enum
from typing import List, Optional

from husky_directory.models.base import DirectoryBaseModel


class VCardPhoneType(Enum):
    work = "work"
    home = "home"
    fax = "fax"
    pager = "pager"
    cell = "cell"
    tdd = "TTY-TDD"
    message = "MSG"


class VCardPhone(DirectoryBaseModel):
    types: List[VCardPhoneType]
    value: str


class VCard(DirectoryBaseModel):
    last_name: str
    name_extras: List[str] = []
    display_name: str
    titles: List[str] = []
    departments: List[str] = []
    email: Optional[str]
    phones: List[VCardPhone] = []
