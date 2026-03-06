#include <csignal>
#include <cerrno>
#include <cstring>
#include <functional>
#include <iostream>
#include <memory>
#include <string>

#include <grpcpp/grpcpp.h>

#include "client.h"
#include "pipewire.grpc.pb.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::Status;

namespace {

constexpr char kDefaultBindAddress[] = "0.0.0.0";
constexpr char kDefaultPort[] = "50051";

std::string BuildServerBindTarget(int argc, char** argv) {
  const std::string bind_address = (argc > 1) ? argv[1] : kDefaultBindAddress;
  const std::string bind_port = (argc > 2) ? argv[2] : kDefaultPort;
  return bind_address + ":" + bind_port;
}

std::unique_ptr<Server> StartGrpcServer(const std::string& bind_target,
                                        grpc::Service* service) {
  ServerBuilder builder;
  builder.AddListeningPort(bind_target, grpc::InsecureServerCredentials());
  builder.RegisterService(service);
  return builder.BuildAndStart();
}

bool ConfigureShutdownSignalSet(sigset_t* shutdown_signal_set) {
  if (shutdown_signal_set == nullptr) {
    return false;
  }
  if (sigemptyset(shutdown_signal_set) != 0) {
    std::cerr << "sigemptyset failed: " << std::strerror(errno) << "\n";
    return false;
  }
  if (sigaddset(shutdown_signal_set, SIGINT) != 0) {
    std::cerr << "sigaddset(SIGINT) failed: " << std::strerror(errno) << "\n";
    return false;
  }
  if (sigaddset(shutdown_signal_set, SIGTERM) != 0) {
    std::cerr << "sigaddset(SIGTERM) failed: " << std::strerror(errno) << "\n";
    return false;
  }
  if (sigprocmask(SIG_BLOCK, shutdown_signal_set, nullptr) != 0) {
    std::cerr << "sigprocmask failed: " << std::strerror(errno) << "\n";
    return false;
  }
  return true;
}

bool WaitForShutdownSignal(const sigset_t& shutdown_signal_set) {
  int shutdown_signal = 0;
  const int wait_rc = sigwait(&shutdown_signal_set, &shutdown_signal);
  if (wait_rc != 0) {
    std::cerr << "sigwait failed: " << std::strerror(wait_rc) << "\n";
    return false;
  }
  return true;
}

Status WithSnapshot(const std::function<void(const pwc_snapshot&)>& fill_reply) {
  std::unique_ptr<pwc_snapshot, decltype(&pwc_snapshot_destroy)> snapshot(
      pwc_create_snapshot(), &pwc_snapshot_destroy);
  if (!snapshot) {
    return Status(grpc::StatusCode::UNAVAILABLE, "Failed to fetch PipeWire snapshot");
  }
  fill_reply(*snapshot);
  return Status::OK;
}

}  // namespace

class PipewireServiceImpl final : public camera::pipewire::v1::PipewireService::Service {
 public:
  Status list_cameras(ServerContext*, const camera::pipewire::v1::ListRequest*,
                      camera::pipewire::v1::ListCamerasResponse* reply) override {
    return WithSnapshot([reply](const pwc_snapshot& snapshot) {
      for (size_t i = 0; i < snapshot.camera_count; ++i) {
        const auto& camera_info = snapshot.cameras[i];
        auto* camera = reply->add_cameras();
        camera->set_id(camera_info.id);
        camera->set_name(camera_info.name);
      }
    });
  }

  Status list_streams(ServerContext*, const camera::pipewire::v1::ListRequest*,
                      camera::pipewire::v1::ListStreamsResponse* reply) override {
    return WithSnapshot([reply](const pwc_snapshot& snapshot) {
      for (size_t i = 0; i < snapshot.stream_count; ++i) {
        const auto& stream_info = snapshot.streams[i];
        auto* stream = reply->add_streams();
        stream->set_link_id(stream_info.link_id);
        stream->set_camera_node_id(stream_info.camera_node_id);
        stream->set_consumer_node_id(stream_info.consumer_node_id);
        stream->set_camera_name(stream_info.camera_name);
        stream->set_consumer_name(stream_info.consumer_name);
      }
    });
  }
};

int main(int argc, char** argv) {
  sigset_t shutdown_signal_set;
  if (!ConfigureShutdownSignalSet(&shutdown_signal_set)) {
    return 1;
  }

  const std::string server_bind_target = BuildServerBindTarget(argc, argv);
  PipewireServiceImpl service;
  std::unique_ptr<Server> server = StartGrpcServer(server_bind_target, &service);
  if (!server) {
    std::cerr << "Failed to start server\n";
    return 1;
  }

  std::cout << "gRPC camera service listening on " << server_bind_target << std::endl;
  if (!WaitForShutdownSignal(shutdown_signal_set)) {
    server->Shutdown();
    server->Wait();
    return 1;
  }
  server->Shutdown();
  server->Wait();
  return 0;
}
