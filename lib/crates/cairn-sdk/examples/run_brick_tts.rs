use cairn_sdk::inference_service::{
    BrickSpec, BrickType, InferenceService, RunBrickInput, RunBrickOutput,
};

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

    let result = service
        .run_brick(
            BrickSpec {
                brick_type: BrickType::Tts,
                brick_variant: "kokoro".to_string(),
            },
            RunBrickInput::Text {
                text: "Hello from Cairn SDK".to_string(),
            },
        )
        .await;

    match result {
        Ok(RunBrickOutput::Audio(audio)) => {
            println!(
                "audio response: left={} right={}",
                audio.left_channel.len(),
                audio.right_channel.len()
            );
        }
        Ok(RunBrickOutput::Detections(_)) => {
            eprintln!("unexpected detections output for TTS request");
            std::process::exit(1);
        }
        Err(err) => {
            eprintln!("run_brick failed: {err}");
            std::process::exit(1);
        }
    }
}
