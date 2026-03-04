use tonic::Request;
use tonic::transport::Channel;

pub(super) mod pipewire {
    tonic::include_proto!("camera.pipewire.v1");
}

use pipewire::ListRequest;
use pipewire::pipewire_service_client::PipewireServiceClient;

pub struct Camera {
    pub id: u32,
    pub name: String,
}

pub struct Stream {
    pub link_id: u32,
    pub camera_node_id: u32,
    pub consumer_node_id: u32,
    pub camera_name: String,
    pub consumer_name: String,
}

pub struct CameraService {
    client: PipewireServiceClient<Channel>,
}

impl CameraService {
    pub async fn new(endpoint: String) -> Result<Self, tonic::Status> {
        let client = PipewireServiceClient::connect(endpoint)
            .await
            .map_err(|e| tonic::Status::unavailable(e.to_string()))?;

        Ok(Self { client })
    }

    // we have to do a mutable borrow of the client due to the way tonic's generated client works
    pub async fn list_cameras(&mut self) -> Result<Vec<Camera>, tonic::Status> {
        let response = self
            .client
            .list_cameras(Request::new(ListRequest {}))
            .await?
            .into_inner();
        Ok(response
            .cameras
            .into_iter()
            .map(|proto_camera| Camera {
                id: proto_camera.id,
                name: proto_camera.name,
            })
            .collect())
    }

    pub async fn list_streams(&mut self) -> Result<Vec<Stream>, tonic::Status> {
        let response = self
            .client
            .list_streams(Request::new(ListRequest {}))
            .await?
            .into_inner();
        Ok(response
            .streams
            .into_iter()
            .map(|proto_stream| Stream {
                link_id: proto_stream.link_id,
                camera_node_id: proto_stream.camera_node_id,
                consumer_node_id: proto_stream.consumer_node_id,
                camera_name: proto_stream.camera_name,
                consumer_name: proto_stream.consumer_name,
            })
            .collect())
    }
}
