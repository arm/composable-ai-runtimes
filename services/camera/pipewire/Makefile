CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c99 -D_GNU_SOURCE
CXX ?= g++
CXXFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c++17 -D_GNU_SOURCE

PKG_CONFIG ?= pkg-config
PW_CFLAGS := $(shell $(PKG_CONFIG) --cflags libpipewire-0.3)
PW_LIBS := $(shell $(PKG_CONFIG) --libs libpipewire-0.3)
GRPC_CFLAGS := $(shell $(PKG_CONFIG) --cflags grpc++ protobuf)
GRPC_LIBS := $(shell $(PKG_CONFIG) --libs grpc++ protobuf)
GRPC_CPP_PLUGIN := $(shell command -v grpc_cpp_plugin 2>/dev/null)

BIN := pw_server
SERVER_BIN := server
OBJ_DIR := obj

PROTO_DIR := proto
GEN_DIR := gen
TYPE_PROTO := $(PROTO_DIR)/pipewire_types.proto
EVENT_PROTO := $(PROTO_DIR)/pipewire_events.proto
SERVICE_PROTO := $(PROTO_DIR)/pipewire_service.proto
PROTO_SRCS := $(GEN_DIR)/pipewire_types.pb.cc $(GEN_DIR)/pipewire_events.pb.cc \
	$(GEN_DIR)/pipewire_service.pb.cc $(GEN_DIR)/pipewire_service.grpc.pb.cc
PROTO_HDRS := $(GEN_DIR)/pipewire_types.pb.h $(GEN_DIR)/pipewire_events.pb.h \
	$(GEN_DIR)/pipewire_service.pb.h $(GEN_DIR)/pipewire_service.grpc.pb.h
SERVER_OBJS := $(OBJ_DIR)/server.o $(OBJ_DIR)/client.o \
	$(OBJ_DIR)/pipewire_types.pb.o $(OBJ_DIR)/pipewire_service.pb.o $(OBJ_DIR)/pipewire_service.grpc.pb.o

all: proto $(SERVER_BIN)

$(SERVER_BIN): proto $(SERVER_OBJS)
	$(CXX) -o $@ $(SERVER_OBJS) $(GRPC_LIBS) $(PW_LIBS) -pthread

$(OBJ_DIR):
	mkdir -p $(OBJ_DIR)

$(OBJ_DIR)/server.o: src/server.cc src/client.h $(PROTO_HDRS) | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -Isrc -c $< -o $@

$(OBJ_DIR)/client.o: src/client.c src/client.h | $(OBJ_DIR)
	$(CC) $(CFLAGS) $(PW_CFLAGS) -c $< -o $@

$(OBJ_DIR)/pipewire_types.pb.o: $(GEN_DIR)/pipewire_types.pb.cc $(GEN_DIR)/pipewire_types.pb.h | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -c $< -o $@

$(OBJ_DIR)/pipewire_events.pb.o: $(GEN_DIR)/pipewire_events.pb.cc $(GEN_DIR)/pipewire_events.pb.h | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -c $< -o $@

$(OBJ_DIR)/pipewire_service.pb.o: $(GEN_DIR)/pipewire_service.pb.cc $(GEN_DIR)/pipewire_service.pb.h | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -c $< -o $@

$(OBJ_DIR)/pipewire_service.grpc.pb.o: $(GEN_DIR)/pipewire_service.grpc.pb.cc $(GEN_DIR)/pipewire_service.grpc.pb.h | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -c $< -o $@

proto:
	mkdir -p $(GEN_DIR)
	protoc -I $(PROTO_DIR) --cpp_out=$(GEN_DIR) $(TYPE_PROTO) $(EVENT_PROTO) $(SERVICE_PROTO)
	protoc -I $(PROTO_DIR) --grpc_out=$(GEN_DIR) --plugin=protoc-gen-grpc=$(GRPC_CPP_PLUGIN) $(SERVICE_PROTO)

clean:
	rm -f pw_server $(SERVER_BIN)
	rm -rf $(OBJ_DIR)
	rm -rf $(GEN_DIR)

.PHONY: all clean proto
