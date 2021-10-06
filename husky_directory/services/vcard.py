from collections import defaultdict
from io import BytesIO
from typing import Dict, NoReturn, Set

from flask import render_template
from flask_injector import request
from injector import inject

from husky_directory.models.pws import PersonOutput
from husky_directory.models.vcard import VCard, VCardAddress, VCardPhone, VCardPhoneType
from husky_directory.services.pws import PersonWebServiceClient


@request
class VCardService:
    """Generates vcards from PWS output."""

    @inject
    def __init__(self, pws: PersonWebServiceClient):
        self.pws = pws

    @staticmethod
    def set_employee_vcard_attrs(vcard: VCard, person: PersonOutput) -> NoReturn:
        """
        Based on a person's employee attributes, sets appropriate vcard values.
        For people who are both students and employees email values will override
        student values, if they differ.

        Student phones will not interfere, as they are treated as "home".
        """
        employee = person.affiliations.employee
        if not employee or not employee.directory_listing:
            return {}
        employee = employee.directory_listing

        for position in employee.positions:
            vcard.titles.append(position.title)
            vcard.departments.append(position.department)

        # Populates a dictionary whose keys are phone numbers and
        # whose default values are empty sets that are later populated
        # to include the various tags attached to the number.
        phones: Dict[str, Set[VCardPhoneType]] = defaultdict(lambda: set())

        for pager in employee.pagers:
            phones[pager].add(VCardPhoneType.pager)
        for tdd in employee.touch_dials:
            phones[tdd].add(VCardPhoneType.tdd)
        for fax in employee.faxes:
            phones[fax].add(VCardPhoneType.fax)
        for mobile in employee.mobiles:
            phones[mobile].add(VCardPhoneType.cell)
        for vm in employee.voice_mails:
            phones[vm].add(VCardPhoneType.message)
        for work_phone in employee.phones:
            phones[work_phone].add(VCardPhoneType.work)

        if phones:
            vcard.phones.extend(
                [
                    # Sort the types based on their stringified values
                    # so that our vcard ordering is deterministic.
                    VCardPhone(
                        types=sorted(list(types), key=lambda t: t.value), value=phone
                    )
                    for phone, types in phones.items()
                ]
            )

        # If student email exists, we prefer employee email (in case they are different),
        # so we overwrite.
        if employee.emails:
            vcard.email = employee.emails[0]

        if employee.addresses:
            vcard.addresses = [
                VCardAddress.from_string(
                    a, box_number=person.affiliations.employee.mail_stop
                ).vcard_format
                for a in employee.addresses
            ]

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
                VCardPhone(types=[VCardPhoneType.home], value=student.phone)
            )
        if student.email:
            vcard.email = student.email

        if student.class_level:
            vcard.titles.append(student.class_level)

    def get_vcard(self, href: str) -> BytesIO:
        person = self.pws.get_explicit_href(href, output_type=PersonOutput)

        last_name, *other_names = person.canonical_tokens
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
        content = "\n".join([line.lstrip() for line in content.split("\n")])
        # Create a file-like object to send to the client
        file_ = BytesIO()
        file_.write(content.encode("UTF-8"))
        file_.seek(0)

        return file_
