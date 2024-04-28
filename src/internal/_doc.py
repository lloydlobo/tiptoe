"""Code styleguide

Linting:

    `type: ignore` can collide with other type checkers (such as mypy). To work
    around this, Pyright now supports # pyright: ignore comments (which mypy
    will not pick up on). This is documented
    [here](https://github.com/microsoft/pyright/blob/main/docs/comments.md#line-level-diagnostic-suppression).
    see source:
        https://stackoverflow.com/questions/57335636/is-it-possible-to-ignore-pyright-checking-for-one-line/70513059#70513059

        >>> foo: int = "123"  # pyright: ignore
        >>> foo: int = "123"  # pyright: ignore [reportPrivateUsage, reportGeneralTypeIssues]
"""
