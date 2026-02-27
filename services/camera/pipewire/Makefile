CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c99 -D_GNU_SOURCE

PKG_CONFIG ?= pkg-config
PW_CFLAGS := $(shell $(PKG_CONFIG) --cflags libpipewire-0.3)
PW_LIBS := $(shell $(PKG_CONFIG) --libs libpipewire-0.3)

BIN := pw_camera_monitor
SRC := src/main.c src/client.c

PROTO_DIR := proto
GEN_DIR := gen
PROTO := $(PROTO_DIR)/pipewire.proto
PROTO_SRCS := $(GEN_DIR)/pipewire.pb.cc $(GEN_DIR)/pipewire.grpc.pb.cc
PROTO_HDRS := $(GEN_DIR)/pipewire.pb.h $(GEN_DIR)/pipewire.grpc.pb.h

all: $(BIN) proto

$(BIN): $(SRC)
	$(CC) $(CFLAGS) $(PW_CFLAGS) -o $@ $(SRC) $(PW_LIBS)

proto: $(PROTO_SRCS) $(PROTO_HDRS)

$(GEN_DIR)/pipewire.pb.cc $(GEN_DIR)/pipewire.pb.h $(GEN_DIR)/pipewire.grpc.pb.cc $(GEN_DIR)/pipewire.grpc.pb.h: $(PROTO)
	mkdir -p $(GEN_DIR)
	protoc -I $(PROTO_DIR) --cpp_out=$(GEN_DIR) --grpc_out=$(GEN_DIR) --plugin=protoc-gen-grpc=`which grpc_cpp_plugin` $(PROTO)

clean:
	rm -f $(BIN)
	rm -rf $(GEN_DIR)

.PHONY: all clean proto
