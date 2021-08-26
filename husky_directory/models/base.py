import typing

from pydantic import BaseModel, Extra

from husky_directory.util import camelize

# This is only to make flake8 happy, we can skip this at runtime
if typing.TYPE_CHECKING:  # pragma: no cover
    from pydantic.typing import AbstractSetIntStr, DictStrAny, MappingIntStrAny


class PropertyBaseModel(BaseModel):
    """
    Workaround for serializing properties with pydantic until
    https://github.com/samuelcolvin/pydantic/issues/935
    is solved.

    This model was sourced from
    https://github.com/samuelcolvin/pydantic/issues/935#issuecomment-752987593
    """

    class Config:
        ignored_properties = []

    @classmethod
    def get_properties(cls) -> typing.List[str]:
        """
        Checks for all properties on the model, and returns them.
        :return: All defined properties on the model.
        """
        return [
            prop
            for prop in dir(cls)
            if prop not in getattr(cls.Config, "ignored_properties", [])
            and isinstance(getattr(cls, prop), property)
            and prop not in ("__values__", "fields")
        ]

    def dict(
        self,
        *,
        include: typing.Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        exclude: typing.Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        exclude_properties: bool = False,
    ) -> "DictStrAny":
        """
        Overrides the base dict() behavior to ensure that properties are
        exported, unless this behavior is configured via the
        `include` and `exclude` parameters.

        For more information about these options, see the official
        pydantic documentation:
        https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict
        """
        attribs = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

        alias_generator = getattr(self.Config, "alias_generator", None)
        if by_alias and not alias_generator:
            raise AttributeError(
                f"{self.__class__.__name__} has no alias generator, so its properties cannot be "
                f"converted to an alias."
            )

        if not exclude_properties:
            props = self.get_properties()
            if include:
                props = [prop for prop in props if prop in include]
            if exclude:
                props = [prop for prop in props if prop not in exclude]

            # update the attribute dict with the properties
            if props:
                attribs.update({prop: getattr(self, prop) for prop in props})

            if by_alias:
                for prop in props:
                    # Replace the property key with its generated alias.
                    if prop in attribs:
                        attribs[alias_generator(prop)] = attribs.pop(prop)

        return attribs


class DirectoryBaseModel(PropertyBaseModel):
    class Config:  # See https://pydantic-docs.helpmanual.io/usage/model_config/
        extra = Extra.ignore
        use_enum_values = True
        allow_population_by_field_name = True
        validate_assignment = True
        alias_generator = camelize
        anystr_strip_whitespace = True
