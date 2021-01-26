import inflection
from devtools.debug import PrettyFormat
from injector import Module, provider, singleton


class UtilityInjectorModule(Module):
    @singleton
    @provider
    def provide_pretty_formatter(self) -> PrettyFormat:
        """
        Uses devtools PrettyFormat to make it easier to log models and objects readably. This singleton formatter
        can be used application wide for consistency.

        Example:

            obj = dict(foo=123, bar=234)
            print(injector.get(PrettyFormat)(obj))
        """
        return PrettyFormat(simple_cutoff=0)  # Always show list items 1 per line.


def camelize(string: str, uppercase_first_letter=False) -> str:
    """Fixes the default behavior to keep the first character lowerCased."""
    return inflection.camelize(string, uppercase_first_letter=uppercase_first_letter)
