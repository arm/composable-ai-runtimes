use cairn_sdk::inference_service::InferenceService;

#[tokio::main]
async fn main() {
    let endpoint = std::env::var("CAIRN_CONCORDIA_ENDPOINT")
        .unwrap_or_else(|_| "http://[::1]:50052".to_string());

    let mut service = match InferenceService::new(endpoint).await {
        Ok(service) => service,
        Err(err) => {
            eprintln!("failed to connect: {err}");
            std::process::exit(1);
        }
    };

    match service.list_bricks().await {
        Ok(bricks) => {
            for brick in bricks {
                println!(
                    "brick type={:?} variant={}",
                    brick.brick_type, brick.brick_variant
                );
            }
        }
        Err(err) => {
            eprintln!("list_bricks failed: {err}");
            std::process::exit(1);
        }
    }
}
