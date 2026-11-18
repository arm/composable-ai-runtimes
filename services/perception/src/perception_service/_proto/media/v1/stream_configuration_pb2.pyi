from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StreamConfiguration(_message.Message):
    __slots__ = ("target", "camera_id", "format")
    TARGET_FIELD_NUMBER: _ClassVar[int]
    CAMERA_ID_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    target: str
    camera_id: int
    format: StreamFormat
    def __init__(self, target: _Optional[str] = ..., camera_id: _Optional[int] = ..., format: _Optional[_Union[StreamFormat, _Mapping]] = ...) -> None: ...

class StreamFormat(_message.Message):
    __slots__ = ("resolution", "pixel_format", "frame_rate")
    RESOLUTION_FIELD_NUMBER: _ClassVar[int]
    PIXEL_FORMAT_FIELD_NUMBER: _ClassVar[int]
    FRAME_RATE_FIELD_NUMBER: _ClassVar[int]
    resolution: Resolution
    pixel_format: str
    frame_rate: FrameRate
    def __init__(self, resolution: _Optional[_Union[Resolution, _Mapping]] = ..., pixel_format: _Optional[str] = ..., frame_rate: _Optional[_Union[FrameRate, _Mapping]] = ...) -> None: ...

class Resolution(_message.Message):
    __slots__ = ("width", "height")
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    width: int
    height: int
    def __init__(self, width: _Optional[int] = ..., height: _Optional[int] = ...) -> None: ...

class FrameRate(_message.Message):
    __slots__ = ("numerator", "denominator")
    NUMERATOR_FIELD_NUMBER: _ClassVar[int]
    DENOMINATOR_FIELD_NUMBER: _ClassVar[int]
    numerator: int
    denominator: int
    def __init__(self, numerator: _Optional[int] = ..., denominator: _Optional[int] = ...) -> None: ...
