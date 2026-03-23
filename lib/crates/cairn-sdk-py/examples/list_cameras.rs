use cairn_sdk::camera_service::CameraService;

#[tokio::main]
async fn main() {
    let endpoint = std::env::var("CAMERA_SERVICE_ENDPOINT")
        .unwrap_or_else(|_| "http://127.0.0.1:50051".to_string());

    let mut service = match CameraService::new(Some(endpoint)).await {
        Ok(service) => service,
        Err(err) => {
            eprintln!("failed to connect: {err}");
            std::process::exit(1);
        }
    };

    match service.list_camera_metadata().await {
        Ok(cameras) => {
            for camera in cameras {
                println!("camera id={} name={}", camera.id, camera.name);
            }
        }
        Err(err) => {
            eprintln!("list_cameras failed: {err}");
            std::process::exit(1);
        }
    }
}
