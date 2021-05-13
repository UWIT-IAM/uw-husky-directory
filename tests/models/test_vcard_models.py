import pytest

from husky_directory.models.vcard import VCardAddress


class TestVCardAddress:
    @pytest.fixture(autouse=True)
    def initialize(self):
        pass

    @pytest.mark.parametrize(
        "pws_value, box_number, expected",
        [
            # Standard address formatting
            (
                "123 Main St. Anytown, WA 12345-1234",
                "351234",
                "Box 351234;;123 Main St.;Anytown;WA;12345-1234;US;",
            ),
            # Has accurate zip, but city/state not parseable, so uses defaults
            # and includes original as street address
            (
                "123 Main St. Anytown WA 12345",
                None,
                ";;123 Main St. Anytown WA;;WA;12345;US;",
            ),
            # No zip parseable, so all parsing fails; defaults used
            # for state/country; original used as street address
            (
                "123 Main St. Anytown, WA",
                "351235",
                "Box 351235;;123 Main St. Anytown, WA;;WA;;US;",
            ),
        ],
    )
    def test_from_string(self, pws_value, box_number, expected):
        assert VCardAddress.from_string(pws_value, box_number).vcard_format == expected
