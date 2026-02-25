from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BrickType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BRICK_TYPE_UNSPECIFIED: _ClassVar[BrickType]
    BRICK_TYPE_TTS: _ClassVar[BrickType]
    BRICK_TYPE_OBJECT_DETECTION: _ClassVar[BrickType]
BRICK_TYPE_UNSPECIFIED: BrickType
BRICK_TYPE_TTS: BrickType
BRICK_TYPE_OBJECT_DETECTION: BrickType

class ListBricksRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListBricksResponse(_message.Message):
    __slots__ = ("bricks",)
    BRICKS_FIELD_NUMBER: _ClassVar[int]
    bricks: _containers.RepeatedCompositeFieldContainer[BrickSpec]
    def __init__(self, bricks: _Optional[_Iterable[_Union[BrickSpec, _Mapping]]] = ...) -> None: ...

class TextInput(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class ImageInput(_message.Message):
    __slots__ = ("image_bytes",)
    IMAGE_BYTES_FIELD_NUMBER: _ClassVar[int]
    image_bytes: bytes
    def __init__(self, image_bytes: _Optional[bytes] = ...) -> None: ...

class RunBrickRequest(_message.Message):
    __slots__ = ("brick", "text", "image")
    BRICK_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    brick: BrickSpec
    text: TextInput
    image: ImageInput
    def __init__(self, brick: _Optional[_Union[BrickSpec, _Mapping]] = ..., text: _Optional[_Union[TextInput, _Mapping]] = ..., image: _Optional[_Union[ImageInput, _Mapping]] = ...) -> None: ...

class RunBrickResponse(_message.Message):
    __slots__ = ("audio", "detections")
    AUDIO_FIELD_NUMBER: _ClassVar[int]
    DETECTIONS_FIELD_NUMBER: _ClassVar[int]
    audio: AudioOutput
    detections: ObjDetectionOutput
    def __init__(self, audio: _Optional[_Union[AudioOutput, _Mapping]] = ..., detections: _Optional[_Union[ObjDetectionOutput, _Mapping]] = ...) -> None: ...

class BrickSpec(_message.Message):
    __slots__ = ("type", "brick_variant")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    BRICK_VARIANT_FIELD_NUMBER: _ClassVar[int]
    type: BrickType
    brick_variant: str
    def __init__(self, type: _Optional[_Union[BrickType, str]] = ..., brick_variant: _Optional[str] = ...) -> None: ...

class Detection(_message.Message):
    __slots__ = ("box", "class_id", "score", "class_name")
    BOX_FIELD_NUMBER: _ClassVar[int]
    CLASS_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    CLASS_NAME_FIELD_NUMBER: _ClassVar[int]
    box: _containers.RepeatedScalarFieldContainer[float]
    class_id: int
    score: float
    class_name: str
    def __init__(self, box: _Optional[_Iterable[float]] = ..., class_id: _Optional[int] = ..., score: _Optional[float] = ..., class_name: _Optional[str] = ...) -> None: ...

class ObjDetectionOutput(_message.Message):
    __slots__ = ("detections",)
    DETECTIONS_FIELD_NUMBER: _ClassVar[int]
    detections: _containers.RepeatedCompositeFieldContainer[Detection]
    def __init__(self, detections: _Optional[_Iterable[_Union[Detection, _Mapping]]] = ...) -> None: ...

class AudioOutput(_message.Message):
    __slots__ = ("left_channel", "right_channel")
    LEFT_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    RIGHT_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    left_channel: _containers.RepeatedScalarFieldContainer[float]
    right_channel: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, left_channel: _Optional[_Iterable[float]] = ..., right_channel: _Optional[_Iterable[float]] = ...) -> None: ...
