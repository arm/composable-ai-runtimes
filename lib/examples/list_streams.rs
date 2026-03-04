use cairn_sdk_lib::camera_service::CameraService;

#[tokio::main]
async fn main() {
    let endpoint = std::env::var("CAIRN_PIPEWIRE_ENDPOINT")
        .unwrap_or_else(|_| "http://[::1]:50051".to_string());

    let mut service = match CameraService::new(endpoint).await {
        Ok(service) => service,
        Err(err) => {
            eprintln!("failed to connect: {err}");
            std::process::exit(1);
        }
    };

    match service.list_streams().await {
        Ok(streams) => {
            for stream in streams {
                println!(
                    "stream link_id={} camera_node_id={} consumer_node_id={} camera_name={} consumer_name={}",
                    stream.link_id,
                    stream.camera_node_id,
                    stream.consumer_node_id,
                    stream.camera_name,
                    stream.consumer_name
                );
            }
        }
        Err(err) => {
            eprintln!("list_streams failed: {err}");
            std::process::exit(1);
        }
    }
}
