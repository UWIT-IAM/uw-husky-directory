from enum import Enum
from typing import List, Optional

from husky_directory.models.base import DirectoryBaseModel


class VCardPhoneType(Enum):
    text = "text"
    voice = "voice"
    fax = "fax"
    cell = "cell"
    pager = "pager"
    textphone = "textphone"  # TDD


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
