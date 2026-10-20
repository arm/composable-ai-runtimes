from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ValidationSeverity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VALIDATION_SEVERITY_UNSPECIFIED: _ClassVar[ValidationSeverity]
    VALIDATION_SEVERITY_ERROR: _ClassVar[ValidationSeverity]
    VALIDATION_SEVERITY_WARNING: _ClassVar[ValidationSeverity]

class ResolvedStageRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESOLVED_STAGE_ROLE_UNSPECIFIED: _ClassVar[ResolvedStageRole]
    RESOLVED_STAGE_ROLE_SOURCE: _ClassVar[ResolvedStageRole]
    RESOLVED_STAGE_ROLE_PROCESSING: _ClassVar[ResolvedStageRole]
    RESOLVED_STAGE_ROLE_OUTPUT: _ClassVar[ResolvedStageRole]

class SessionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SESSION_STATE_UNSPECIFIED: _ClassVar[SessionState]
    SESSION_STATE_STARTING: _ClassVar[SessionState]
    SESSION_STATE_RUNNING: _ClassVar[SessionState]
    SESSION_STATE_STOPPING: _ClassVar[SessionState]
    SESSION_STATE_STOPPED: _ClassVar[SessionState]
    SESSION_STATE_FAILED: _ClassVar[SessionState]
VALIDATION_SEVERITY_UNSPECIFIED: ValidationSeverity
VALIDATION_SEVERITY_ERROR: ValidationSeverity
VALIDATION_SEVERITY_WARNING: ValidationSeverity
RESOLVED_STAGE_ROLE_UNSPECIFIED: ResolvedStageRole
RESOLVED_STAGE_ROLE_SOURCE: ResolvedStageRole
RESOLVED_STAGE_ROLE_PROCESSING: ResolvedStageRole
RESOLVED_STAGE_ROLE_OUTPUT: ResolvedStageRole
SESSION_STATE_UNSPECIFIED: SessionState
SESSION_STATE_STARTING: SessionState
SESSION_STATE_RUNNING: SessionState
SESSION_STATE_STOPPING: SessionState
SESSION_STATE_STOPPED: SessionState
SESSION_STATE_FAILED: SessionState

class GetServiceInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetServiceInfoResponse(_message.Message):
    __slots__ = ("api_version", "service_version", "sessions_survive_restart")
    API_VERSION_FIELD_NUMBER: _ClassVar[int]
    SERVICE_VERSION_FIELD_NUMBER: _ClassVar[int]
    SESSIONS_SURVIVE_RESTART_FIELD_NUMBER: _ClassVar[int]
    api_version: str
    service_version: str
    sessions_survive_restart: bool
    def __init__(self, api_version: _Optional[str] = ..., service_version: _Optional[str] = ..., sessions_survive_restart: _Optional[bool] = ...) -> None: ...

class DebugPorts(_message.Message):
    __slots__ = ("http_port", "ws_port", "ctrl_port")
    HTTP_PORT_FIELD_NUMBER: _ClassVar[int]
    WS_PORT_FIELD_NUMBER: _ClassVar[int]
    CTRL_PORT_FIELD_NUMBER: _ClassVar[int]
    http_port: int
    ws_port: int
    ctrl_port: int
    def __init__(self, http_port: _Optional[int] = ..., ws_port: _Optional[int] = ..., ctrl_port: _Optional[int] = ...) -> None: ...

class WorkflowSpec(_message.Message):
    __slots__ = ("name", "source", "stages", "output", "output_events")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    STAGES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_EVENTS_FIELD_NUMBER: _ClassVar[int]
    name: str
    source: SourceSpec
    stages: _containers.RepeatedCompositeFieldContainer[InferenceStage]
    output: OutputSpec
    output_events: bool
    def __init__(self, name: _Optional[str] = ..., source: _Optional[_Union[SourceSpec, _Mapping]] = ..., stages: _Optional[_Iterable[_Union[InferenceStage, _Mapping]]] = ..., output: _Optional[_Union[OutputSpec, _Mapping]] = ..., output_events: _Optional[bool] = ...) -> None: ...

class SourceSpec(_message.Message):
    __slots__ = ("camera",)
    CAMERA_FIELD_NUMBER: _ClassVar[int]
    camera: StreamConfiguration
    def __init__(self, camera: _Optional[_Union[StreamConfiguration, _Mapping]] = ...) -> None: ...

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

class InferenceStage(_message.Message):
    __slots__ = ("id", "name", "model_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    model_id: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., model_id: _Optional[str] = ...) -> None: ...

class OutputSpec(_message.Message):
    __slots__ = ("debug",)
    DEBUG_FIELD_NUMBER: _ClassVar[int]
    debug: DebugOutput
    def __init__(self, debug: _Optional[_Union[DebugOutput, _Mapping]] = ...) -> None: ...

class DebugOutput(_message.Message):
    __slots__ = ("http_port", "ws_port", "ctrl_port")
    HTTP_PORT_FIELD_NUMBER: _ClassVar[int]
    WS_PORT_FIELD_NUMBER: _ClassVar[int]
    CTRL_PORT_FIELD_NUMBER: _ClassVar[int]
    http_port: int
    ws_port: int
    ctrl_port: int
    def __init__(self, http_port: _Optional[int] = ..., ws_port: _Optional[int] = ..., ctrl_port: _Optional[int] = ...) -> None: ...

class ValidateWorkflowRequest(_message.Message):
    __slots__ = ("workflow",)
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    workflow: WorkflowSpec
    def __init__(self, workflow: _Optional[_Union[WorkflowSpec, _Mapping]] = ...) -> None: ...

class ValidateWorkflowResponse(_message.Message):
    __slots__ = ("valid", "issues", "stages")
    VALID_FIELD_NUMBER: _ClassVar[int]
    ISSUES_FIELD_NUMBER: _ClassVar[int]
    STAGES_FIELD_NUMBER: _ClassVar[int]
    valid: bool
    issues: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    stages: _containers.RepeatedCompositeFieldContainer[ResolvedStage]
    def __init__(self, valid: _Optional[bool] = ..., issues: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ..., stages: _Optional[_Iterable[_Union[ResolvedStage, _Mapping]]] = ...) -> None: ...

class ValidationIssue(_message.Message):
    __slots__ = ("severity", "code", "message", "field_path", "stage_id")
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    STAGE_ID_FIELD_NUMBER: _ClassVar[int]
    severity: ValidationSeverity
    code: str
    message: str
    field_path: str
    stage_id: str
    def __init__(self, severity: _Optional[_Union[ValidationSeverity, str]] = ..., code: _Optional[str] = ..., message: _Optional[str] = ..., field_path: _Optional[str] = ..., stage_id: _Optional[str] = ...) -> None: ...

class ResolvedStage(_message.Message):
    __slots__ = ("id", "name", "role", "controllable", "model_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTROLLABLE_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    role: ResolvedStageRole
    controllable: bool
    model_id: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., role: _Optional[_Union[ResolvedStageRole, str]] = ..., controllable: _Optional[bool] = ..., model_id: _Optional[str] = ...) -> None: ...

class DeployWorkflowRequest(_message.Message):
    __slots__ = ("workflow",)
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    workflow: WorkflowSpec
    def __init__(self, workflow: _Optional[_Union[WorkflowSpec, _Mapping]] = ...) -> None: ...

class DeployWorkflowResponse(_message.Message):
    __slots__ = ("accepted", "rejected")
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    REJECTED_FIELD_NUMBER: _ClassVar[int]
    accepted: DeploymentAccepted
    rejected: DeploymentRejected
    def __init__(self, accepted: _Optional[_Union[DeploymentAccepted, _Mapping]] = ..., rejected: _Optional[_Union[DeploymentRejected, _Mapping]] = ...) -> None: ...

class DeploymentAccepted(_message.Message):
    __slots__ = ("session",)
    SESSION_FIELD_NUMBER: _ClassVar[int]
    session: PerceptionSession
    def __init__(self, session: _Optional[_Union[PerceptionSession, _Mapping]] = ...) -> None: ...

class DeploymentRejected(_message.Message):
    __slots__ = ("issues",)
    ISSUES_FIELD_NUMBER: _ClassVar[int]
    issues: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    def __init__(self, issues: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ...) -> None: ...

class GetSessionRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class ListSessionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListSessionsResponse(_message.Message):
    __slots__ = ("sessions",)
    SESSIONS_FIELD_NUMBER: _ClassVar[int]
    sessions: _containers.RepeatedCompositeFieldContainer[PerceptionSession]
    def __init__(self, sessions: _Optional[_Iterable[_Union[PerceptionSession, _Mapping]]] = ...) -> None: ...

class StopSessionRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class StageControlRequest(_message.Message):
    __slots__ = ("session_id", "stage_id")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STAGE_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    stage_id: str
    def __init__(self, session_id: _Optional[str] = ..., stage_id: _Optional[str] = ...) -> None: ...

class PerceptionSession(_message.Message):
    __slots__ = ("id", "workflow_name", "stages", "debug_endpoint", "topics")
    ID_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_NAME_FIELD_NUMBER: _ClassVar[int]
    STAGES_FIELD_NUMBER: _ClassVar[int]
    DEBUG_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    TOPICS_FIELD_NUMBER: _ClassVar[int]
    id: str
    workflow_name: str
    stages: _containers.RepeatedCompositeFieldContainer[ResolvedStage]
    debug_endpoint: DebugPorts
    topics: SessionTopics
    def __init__(self, id: _Optional[str] = ..., workflow_name: _Optional[str] = ..., stages: _Optional[_Iterable[_Union[ResolvedStage, _Mapping]]] = ..., debug_endpoint: _Optional[_Union[DebugPorts, _Mapping]] = ..., topics: _Optional[_Union[SessionTopics, _Mapping]] = ...) -> None: ...

class SessionTopics(_message.Message):
    __slots__ = ("results", "events")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    results: str
    events: str
    def __init__(self, results: _Optional[str] = ..., events: _Optional[str] = ...) -> None: ...

class SessionSnapshot(_message.Message):
    __slots__ = ("status", "disabled_stage_ids")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DISABLED_STAGE_IDS_FIELD_NUMBER: _ClassVar[int]
    status: SessionStatus
    disabled_stage_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, status: _Optional[_Union[SessionStatus, _Mapping]] = ..., disabled_stage_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class SessionStatus(_message.Message):
    __slots__ = ("state", "info")
    STATE_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    state: SessionState
    info: StatusInfo
    def __init__(self, state: _Optional[_Union[SessionState, str]] = ..., info: _Optional[_Union[StatusInfo, _Mapping]] = ...) -> None: ...

class StatusInfo(_message.Message):
    __slots__ = ("code", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...
