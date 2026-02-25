CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c99 -D_GNU_SOURCE

PKG_CONFIG ?= pkg-config
PW_CFLAGS := $(shell $(PKG_CONFIG) --cflags libpipewire-0.3)
PW_LIBS := $(shell $(PKG_CONFIG) --libs libpipewire-0.3)

BIN := pw_camera_monitor
SRC := src/main.c src/pipewire_client.c

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) $(PW_CFLAGS) -o $@ $(SRC) $(PW_LIBS)

clean:
	rm -f $(BIN)

.PHONY: all clean
