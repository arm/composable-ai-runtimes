use crate::service::map_snapshot_error;
use crate::snapshot::SnapshotError;
use tonic::Code;

#[test]
fn map_snapshot_error_returns_unavailable_status() {
    let status = map_snapshot_error(SnapshotError::Unavailable("pipewire unavailable".into()));

    assert_eq!(status.code(), Code::Unavailable);
    assert_eq!(status.message(), "pipewire unavailable");
}
