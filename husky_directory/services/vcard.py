from collections import defaultdict
from io import BytesIO
from typing import Dict, List, NoReturn, Set, Tuple

from flask import Flask, render_template
from injector import Injector, inject
from werkzeug.exceptions import Forbidden
from werkzeug.local import LocalProxy

from husky_directory.models.enum import PopulationType
from husky_directory.models.pws import NamedIdentity, PersonOutput
from husky_directory.models.vcard import VCard, VCardPhone, VCardPhoneType
from husky_directory.services.pws import PersonWebServiceClient
from husky_directory.services.translator import (
    ListPersonsOutputTranslator,
    PersonOutputFilter,
)


class VCardService:
    """Generates vcards from PWS output."""

    @inject
    def __init__(
        self,
        pws: PersonWebServiceClient,
        app: Flask,
        injector: Injector,
    ):
        self.pws = pws
        self.flask = app
        self.injector = injector

    @property
    def request_is_authenticated(self):
        # Lazily bound to constrain request scopes
        session = self.injector.get(LocalProxy)
        return bool(session.get("uwnetid"))

    @property
    def translator(self) -> ListPersonsOutputTranslator:
        # Lazily bound to constrain request scopes
        return self.injector.get(ListPersonsOutputTranslator)

    @staticmethod
    def set_employee_vcard_attrs(vcard: VCard, person: PersonOutput) -> NoReturn:
        """
        Based on a person's employee attributes, sets appropriate vcard values.
        For people who are both students and employees, employee phones and email
        selections will override student selections, if they differ.
        """
        employee = person.affiliations.employee
        if not employee or not employee.directory_listing:
            return {}
        employee = employee.directory_listing

        for position in employee.positions:
            vcard.titles.append(position.title)
            vcard.departments.append(position.department)

        phones: Dict[str, Set[VCardPhoneType]] = defaultdict(lambda: set())

        for pager in employee.pagers:
            phones[pager].add(VCardPhoneType.pager)
        for tdd in employee.touch_dials:
            phones[tdd].add(VCardPhoneType.textphone)
        for fax in employee.faxes:
            phones[fax].add(VCardPhoneType.fax)
        for phone in employee.mobiles:
            phones[phone].add(VCardPhoneType.text)
            phones[phone].add(VCardPhoneType.voice)
        for phone in employee.voice_mails + employee.phones:
            phones[phone].add(VCardPhoneType.voice)

        # If student phones exist, we prefer employee phones, so we overwrite.
        if phones:
            vcard.phones = [
                # Sort the types based on their stringified values
                # so that our vcard ordering is deterministic.
                VCardPhone(
                    types=sorted(list(types), key=lambda t: t.value), value=phone
                )
                for phone, types in phones.items()
            ]

        # If student email exists, we prefer employee email (in case they are different),
        # so we overwrite.
        if employee.emails:
            vcard.email = employee.emails[0]

    @staticmethod
    def parse_person_name(person: NamedIdentity) -> Tuple[str, List[str]]:
        """
        Naming is hard, and we can't necessarily rely on a sanitized data set every time.
        So, we'll apply the following heuristic:

         - If preferred name is set, always fill preferred values first
         - Otherwise, default to registered values
         - Otherwise(?), guess based on the display name, which is _likely_ the same values
            as the registered values, so this might not ever happen, but
            we don't control the data, so this use case is thus accounted for.

        :param person:
        :return: A tuple whose first value is the "Last" name, and whose second value is a list of "extra" names,
        that are in the order of ["<first>", "<middle>", "extra +1", "extra +2", . . . ]
        """
        first = person.preferred_first_name
        middle = person.preferred_middle_name
        last = person.preferred_last_name

        if not first:
            middles = None
            rfm = person.registered_first_middle_name
            if rfm:
                # 'A B C' becomes 'A', ['B', 'C']
                first, *middles_ = rfm.split()
                if not middle:
                    # In case the middle name is already set, don't automatically override
                    middles = middles_
            else:
                first, *middles = person.display_name.split()

            if middles:
                middle = " ".join(middles)

        if not last:
            if person.registered_surname:
                last = person.registered_surname
            else:
                last = person.display_name.split()[-1]

        # When we explode the display name to calculate this value
        # "Firsty First Middly Last" might set "middle names" to
        # "First Middly Last", but still with a "Last" surname, so the
        # entry looks like: "Last;Firsty;First;Middly;Last".
        # this block prevents the the second occurence of `Last`
        if middle and last in middle:
            middle = middle.replace(last, "").strip()

        extras = list(filter(bool, [first, middle]))
        return last, extras

    @staticmethod
    def set_student_vcard_attrs(vcard: VCard, person: PersonOutput) -> NoReturn:
        student = person.affiliations.student
        # If there is no student directory data, then return an empty dict.
        if not student or not student.directory_listing:
            return {}
        student = student.directory_listing
        vcard.departments.extend([dept for dept in student.departments])

        if student.phone:
            vcard.phones.append(
                VCardPhone(types=[VCardPhoneType.voice], value=student.phone)
            )
        if student.email:
            vcard.email = student.email

        if student.class_level:
            vcard.titles.append(student.class_level)

    def get_vcard(self, href: str) -> BytesIO:
        person = self.pws.get_explicit_href(href, output_type=PersonOutput)

        if not self.translator.filter_person(
            # We set "PopulationType.all" here because when searching
            # for a specific person, we expect to get all of their attributes.
            # The filter will exclude student data if the requester is not
            # authenticated.
            person,
            PersonOutputFilter(allowed_populations=[PopulationType.all]),
        ):  # This is the case if the resulting person is a student,
            # but the request isn't authenticated
            raise Forbidden(href)

        last_name, other_names = self.parse_person_name(person)
        vcard = VCard.construct(
            last_name=last_name,
            name_extras=other_names,
            display_name=person.display_name,
        )
        self.set_student_vcard_attrs(vcard, person)
        self.set_employee_vcard_attrs(vcard, person)
        # Render the vcard template with the user's data,
        content = render_template("vcard.vcf.jinja2", **vcard.dict())
        # Remove all the extra lines that jinja2 leaves in there. (ugh.)
        content = "\n".join(
            filter(lambda line: bool(line.strip()), content.split("\n"))
        )
        # Create a file-like object to send to the client
        file_ = BytesIO()
        file_.write(content.encode("UTF-8"))
        file_.seek(0)

        return file_
