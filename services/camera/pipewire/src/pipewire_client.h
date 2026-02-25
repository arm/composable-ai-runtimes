#ifndef PWC_PIPEWIRE_CLIENT_H
#define PWC_PIPEWIRE_CLIENT_H

#include <stdint.h>
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif /* PWC_PIPEWIRE_CLIENT_H */

typedef enum {
    PWC_EVENT_CAMERA_ADDED = 0,
    PWC_EVENT_CAMERA_REMOVED,
    PWC_EVENT_STREAM_ADDED,
    PWC_EVENT_STREAM_REMOVED,
} pwc_event_type_t;

struct pwc_event {
    pwc_event_type_t type;
    uint32_t id;
    const char *name;
    uint32_t camera_node_id;
    uint32_t consumer_node_id;
    const char *camera_name;
    const char *consumer_name;
};

typedef void (*pwc_event_cb)(const struct pwc_event *event, void *userdata);

struct pwc_client;

struct pwc_client *pwc_create(pwc_event_cb cb, void *userdata);
void pwc_destroy(struct pwc_client *client);

int pwc_run(struct pwc_client *client);
void pwc_list_cameras(FILE *out, const struct pwc_client *client);
void pwc_list_streams(FILE *out, const struct pwc_client *client);

#ifdef __cplusplus
}
#endif

#endif
