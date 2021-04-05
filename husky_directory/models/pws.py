"""
Models for PWS inputs and outputs. These act as declarative, typed abstractions over
the PWS API definitions at https://it-wseval1.s.uw.edu/identity/swagger/index.html#/

These are not 1:1 models of that API; only fields we care about are declared here.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, Field, validator

from .enum import AffiliationState
from ..util import camelize


class PWSBaseModel(BaseModel):
    class Config:
        use_enum_values = True
        allow_population_by_field_name = True
        validate_assignment = True
        # 'extra.Ignore' allows us to consume extra data from PWS without
        # declaring it here, so that our model doesn't have to match theirs
        # 1 for 1. Undeclared values are ignored on import; declare them
        # to preserve them.
        extra = Extra.ignore

        @staticmethod
        def generate_alias(field_name: str) -> str:
            return camelize(field_name, uppercase_first_letter=True)

        alias_generator = generate_alias

    @property
    def payload(self) -> Dict[str, Any]:
        """
        Formats the contents of the model, ensuring alias values and excluding
        None values in order to send only relevant payload details to PWS.
        """
        return self.dict(exclude_none=True, by_alias=True)


class ListResponsesOutputWrapper(PWSBaseModel):
    total_count: int
    page_size: int
    page_start: int


class ListPersonsInput(PWSBaseModel):
    """The input model for PWS search."""

    class Config:
        alias_generator = None
        use_enum_values = True

    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    employee_affiliation_state: Optional[AffiliationState] = Field(
        default=AffiliationState.current, alias="employeeAffiliationState"
    )
    student_affiliation_state: Optional[AffiliationState] = Field(
        default=None, alias="studentAffiliationState"
    )
    mail_stop: Optional[str]
    email: Optional[str]
    department: Optional[str]
    phone_number: Optional[str]
    page_size: Optional[int] = Field(
        default=250,
        description="The maximum number of records to "
        "fetch at once. The PWS default is "
        "10, which isn't practical for our "
        "needs, so we set it to a higher "
        "value. (Note that the original "
        "front end did not paginate results, "
        "so parity means this value is only "
        "for query efficiency, not our "
        "current user experience.)",
    )
    page_start: Optional[int] = Field(
        default=None,
        description="Use along with page_size to "
        "tell PWS which set of results to "
        "return.",
    )
    expand: bool = Field(
        default=True,
        alias="verbose",
        const=True,
        description="Whether the results should include the full or "
        "the abridged records. We lock this to True "
        "because the abridged records do not include the "
        "attribute declaring whether or not a user "
        "should be listed in the directory, "
        "and we require this parameter. Fetching "
        "abbreviated records is not currently supported.",
    )
    href: Optional[str] = Field(
        default=None,
        description="This is returned with a request as "
        "metadata and is not actually used when "
        "submitting a request. However, it may be set in a"
        "PWS response to indicate the next page of a large query.",
        alias="Href",
    )


class EmployeePosition(PWSBaseModel):
    department: Optional[str] = Field(None, alias="EWPDept")
    title: Optional[str] = Field(None, alias="EWPTitle")
    primary: bool


class EmployeeDirectoryListing(PWSBaseModel):
    name: Optional[str]
    publish_in_directory: bool
    phones: List[str] = []
    emails: List[str] = Field(default=[], alias="EmailAddresses")
    positions: List[EmployeePosition] = []
    faxes: List[str] = []
    voice_mails: List[str] = []
    touch_dials: List[str] = []
    pagers: List[str] = []
    mobiles: List[str] = []


class StudentDirectoryListing(PWSBaseModel):
    name: Optional[str]
    publish_in_directory: bool
    phone: Optional[str]
    email: Optional[str]
    # "class" is a reserved keyword, so we have to name this field somethign else.
    class_level: Optional[str] = Field(default=None, alias="Class")
    departments: List[str] = []


class EmployeePersonAffiliation(PWSBaseModel):
    department: Optional[str]
    mail_stop: Optional[str]
    directory_listing: EmployeeDirectoryListing = Field(..., alias="EmployeeWhitePages")


class StudentPersonAffiliation(PWSBaseModel):
    directory_listing: StudentDirectoryListing = Field(..., alias="StudentWhitePages")


class PersonAffiliations(PWSBaseModel):
    employee: Optional[EmployeePersonAffiliation] = Field(
        default=None, alias="EmployeePersonAffiliation"
    )
    student: Optional[StudentPersonAffiliation] = Field(
        default=None, alias="StudentPersonAffiliation"
    )


class PersonOutput(PWSBaseModel):
    display_name: str = Field(..., alias="DisplayName")
    affiliations: PersonAffiliations = Field(
        PersonAffiliations(), alias="PersonAffiliations"
    )
    registered_name: str
    registered_surname: str
    registered_first_middle_name: Optional[str]
    preferred_first_name: Optional[str]
    preferred_middle_name: Optional[str]
    preferred_last_name: Optional[str]
    pronouns: Optional[str]
    regid: Optional[str] = Field(None, alias="UWRegID")
    netid: Optional[str] = Field(None, alias="UWNetID")
    whitepages_publish: bool
    is_test_entity: bool
    href: Optional[str]

    @validator("href", always=True)
    def populate_href(cls, href: Optional[str], values: Dict):
        """
        While abbreviated surch results include the href, the full
        results do not, so it has to be generated.
        """
        if not href:
            regid = values.get("regid")
            if regid:
                return f"/identity/v2/person/{regid}/full.json"
        return href


class ListPersonsOutput(ListResponsesOutputWrapper):
    persons: List[PersonOutput]
    current: ListPersonsInput
    next: Optional[ListPersonsInput] = Field(
        default=None,
        description="If present, gives the URL of the next page of "
        "requests so that we don't have to calculate it.",
    )
    previous: Optional[ListPersonsInput] = Field(None, description="See `next`")
