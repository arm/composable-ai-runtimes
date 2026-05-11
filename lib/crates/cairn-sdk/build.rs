fn main() {
    println!(
        "cargo:rerun-if-changed=../../../services/concordia/src/inference/proto/concordia.proto"
    );
    println!("cargo:rerun-if-changed=../../../services/camera/proto/camera_service.proto");
    tonic_prost_build::compile_protos(
        "../../../services/concordia/src/inference/proto/concordia.proto",
    )
    .unwrap_or_else(|e| panic!("Failed to compile protos {:?}", e));
    tonic_prost_build::compile_protos("../../../services/camera/proto/camera_service.proto")
        .unwrap_or_else(|e| panic!("Failed to compile camera protos {:?}", e));
}
