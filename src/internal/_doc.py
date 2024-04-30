"""

```markdown

# Docs

## Code styleguide

### Linting:

`type: ignore` can collide with other type checkers (such as mypy). To work around this, Pyright now supports # pyright: ignore comments (which mypy will
not pick up on). This is documented [here](https://github.com/microsoft/pyright/blob/main/docs/comments.md#line-level-diagnostic-suppression).
See source: https://stackoverflow.com/questions/57335636/is-it-possible-to-ignore-pyright-checking-for-one-line/70513059#70513059

    >>> foo: int = "123"  # pyright: ignore
    >>> foo: int = "123"  # pyright: ignore [reportPrivateUsage, reportGeneralTypeIssues]

## Camera

When adding something new to camera like this to the world always think about how camera should apply on what one is working on. e.g. HUD does not need
camera scroll, but if working on something in the world, one needs camera scroll. also other way around, something in the world. Convert from screen
space to world space backwards. Note that halving dimensions of image gets its center for the camera 

```

"""
