fn main() {
    println!("cargo:rerun-if-changed=../services/concordia/src/inference/proto/concordia.proto");
    println!("cargo:rerun-if-changed=../services/camera/pipewire/proto/pipewire.proto");
    tonic_prost_build::compile_protos("../services/concordia/src/inference/proto/concordia.proto")
        .unwrap_or_else(|e| panic!("Failed to compile protos {:?}", e));
    tonic_prost_build::compile_protos("../services/camera/pipewire/proto/pipewire.proto")
        .unwrap_or_else(|e| panic!("Failed to compile protos {:?}", e));
}
