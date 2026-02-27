#ifndef PWC_CLIENT_H
#define PWC_CLIENT_H

#include <stdint.h>
#include <stdio.h>

#ifdef __cplusplus
extern "C" {
#endif /* PWC_CLIENT_H */

typedef enum {
    PWC_EVENT_CAMERA_ADDED = 0,
    PWC_EVENT_CAMERA_REMOVED,
    PWC_EVENT_STREAM_ADDED,
    PWC_EVENT_STREAM_REMOVED,
} pwc_event_type_t;

#define PWC_MAX_NAME_LEN 64

struct pwc_event {
    pwc_event_type_t type;
    uint32_t id;
    char name[PWC_MAX_NAME_LEN];
    uint32_t camera_node_id;
    uint32_t consumer_node_id;
    char camera_name[PWC_MAX_NAME_LEN];
    char consumer_name[PWC_MAX_NAME_LEN];
};

typedef void (*pwc_event_cb)(const struct pwc_event *event, void *userdata);

struct pwc_camera_info {
    uint32_t id;
    char name[PWC_MAX_NAME_LEN];
};

struct pwc_stream_info {
    uint32_t link_id;
    uint32_t camera_node_id;
    uint32_t consumer_node_id;
    char camera_name[PWC_MAX_NAME_LEN];
    char consumer_name[PWC_MAX_NAME_LEN];
};

struct pwc_client;

struct pwc_client *pwc_create(pwc_event_cb cb, void *userdata);
void pwc_destroy(void);

int pwc_run(void);

int pwc_list_cameras(struct pwc_camera_info **out_items,
                     size_t *out_count);
int pwc_list_streams(struct pwc_stream_info **out_items,
                     size_t *out_count);
void pwc_free_cameras(struct pwc_camera_info *items, size_t count);
void pwc_free_streams(struct pwc_stream_info *items, size_t count);

#ifdef __cplusplus
}
#endif

#endif
