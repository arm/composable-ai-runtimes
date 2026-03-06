CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c99 -D_GNU_SOURCE
CXX ?= g++
CXXFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c++17 -D_GNU_SOURCE

PKG_CONFIG ?= pkg-config
PW_CFLAGS := $(shell $(PKG_CONFIG) --cflags libpipewire-0.3)
PW_LIBS := $(shell $(PKG_CONFIG) --libs libpipewire-0.3)
GRPC_CFLAGS := $(shell $(PKG_CONFIG) --cflags grpc++ protobuf)
GRPC_LIBS := $(shell $(PKG_CONFIG) --libs grpc++ protobuf)

BIN := pw_server
SERVER_BIN := server
OBJ_DIR := obj

PROTO_DIR := proto
GEN_DIR := gen
PROTO := $(PROTO_DIR)/pipewire.proto
PROTO_SRCS := $(GEN_DIR)/pipewire.pb.cc $(GEN_DIR)/pipewire.grpc.pb.cc
PROTO_HDRS := $(GEN_DIR)/pipewire.pb.h $(GEN_DIR)/pipewire.grpc.pb.h
SERVER_OBJS := $(OBJ_DIR)/server.o $(OBJ_DIR)/client.o \
	$(OBJ_DIR)/pipewire.pb.o $(OBJ_DIR)/pipewire.grpc.pb.o

all: proto $(SERVER_BIN)

$(SERVER_BIN): proto $(SERVER_OBJS)
	$(CXX) -o $@ $(SERVER_OBJS) $(GRPC_LIBS) $(PW_LIBS) -pthread

$(OBJ_DIR):
	mkdir -p $(OBJ_DIR)

$(OBJ_DIR)/server.o: src/server.cc src/client.h $(PROTO_HDRS) | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -Isrc -c $< -o $@

$(OBJ_DIR)/client.o: src/client.c src/client.h | $(OBJ_DIR)
	$(CC) $(CFLAGS) $(PW_CFLAGS) -c $< -o $@

$(OBJ_DIR)/pipewire.pb.o: $(GEN_DIR)/pipewire.pb.cc $(GEN_DIR)/pipewire.pb.h | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -c $< -o $@

$(OBJ_DIR)/pipewire.grpc.pb.o: $(GEN_DIR)/pipewire.grpc.pb.cc $(GEN_DIR)/pipewire.grpc.pb.h | $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(GRPC_CFLAGS) -I$(GEN_DIR) -c $< -o $@

proto: $(PROTO_SRCS) $(PROTO_HDRS)

$(GEN_DIR)/pipewire.pb.cc $(GEN_DIR)/pipewire.pb.h $(GEN_DIR)/pipewire.grpc.pb.cc $(GEN_DIR)/pipewire.grpc.pb.h: $(PROTO)
	mkdir -p $(GEN_DIR)
	protoc -I $(PROTO_DIR) --cpp_out=$(GEN_DIR) --grpc_out=$(GEN_DIR) --plugin=protoc-gen-grpc=`which grpc_cpp_plugin` $(PROTO)

clean:
	rm -f pw_server $(SERVER_BIN)
	rm -rf $(OBJ_DIR)
	rm -rf $(GEN_DIR)

.PHONY: all clean proto
