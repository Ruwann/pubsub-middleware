import typing

Environ = typing.MutableMapping[str, typing.Any]

Headers = typing.List[typing.Tuple[str, str]]
StartResponse = typing.Callable[[str, Headers, typing.Optional[typing.Any]], None]

WSGIApp = typing.Callable[[Environ, StartResponse], typing.Iterable[bytes]]
