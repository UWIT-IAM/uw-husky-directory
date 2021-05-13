from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional

from pydantic import validator

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


class VCardAddress(DirectoryBaseModel):
    box_number: Optional[str]
    ext_address: Optional[str]
    street_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    country: Optional[str]

    class Config(DirectoryBaseModel.Config):
        # Causes a recursion error if not ignored, because
        # dict() fetches property values, and this property
        # calls dict()
        validate_assignment = True
        ignored_properties = ["vcard_format"]

    @validator("box_number", always=True)
    def normalize_box_number(cls, box_number: Optional[str]) -> Optional[str]:
        if box_number:
            return f"Box {box_number}"
        return None

    @property
    def vcard_format(self) -> str:
        fmt_map = {  # Replace None values with empty strings
            k: (v if v else "") for k, v in self.dict().items()
        }
        return (
            "{box_number};{ext_address};{street_address};"
            "{city};{state};{zip_code};{country};".format_map(fmt_map)
        )

    @classmethod
    def from_string(
        cls, address_string: str, box_number: Optional[str] = None
    ) -> VCardAddress:
        """
        Attempts to parse the address value into its component fields; it doesn't try too hard to do this.
        It is acceptable (for us) for the entire address to simply be included as a street address.
        If not provided, the state field is assumed to be WA and the country is assumed to be US.

        The heuristic for parsing the address is simple:
            - If it ends in a zip code, we will assume it has the pattern 'City, ST ZIP'
            - Next we look to the token where we expect the "City," string to be based on its position relative to
              the zip code checking if it ends with a comma. If it does, we can assume it is the city,
              and the token after is the state.
            - Everything else, we treat as the street address.

        If any of the above tests fails, then we simply set whatever we haven't parsed as a street address.
        (Compared to the incumbent product which never tries to parse it, this gives us a slight edge over parity
        as the successor.)
        """
        # ['4501', '15th', 'Ave', 'NE', 'Seattle,', 'WA', '98105-4527']
        address_parts = address_string.split()
        end_index = -1
        instance = cls(
            box_number=box_number,
            state="WA",
            country="US",
            street_address=address_string,
        )
        zip_match = re.match(r"^[0-9\-]{5,10}", address_parts.pop(end_index))
        if zip_match:
            instance.zip_code = zip_match.string
            city_token_index = -2  # zip has already been popped
            city_match = address_parts[city_token_index]
            if city_match.endswith(","):
                # Don't pop city token unless we know it's legit,
                # otherwise, we consume the city and it is never
                # included in the output.
                address_parts.pop(city_token_index)
                instance.city = city_match[:end_index]
                instance.state = address_parts.pop(end_index)
            instance.street_address = " ".join(address_parts)
        return instance


class VCard(DirectoryBaseModel):
    last_name: str
    name_extras: List[str] = []
    display_name: str
    titles: List[str] = []
    departments: List[str] = []
    email: Optional[str]
    phones: List[VCardPhone] = []
    addresses: List[str] = []
