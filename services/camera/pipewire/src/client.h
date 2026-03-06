#ifndef PWC_CLIENT_H
#define PWC_CLIENT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PWC_MAX_NAME_LEN 64

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

struct pwc_snapshot {
    struct pwc_camera_info *cameras;
    size_t camera_count;
    struct pwc_stream_info *streams;
    size_t stream_count;
};

struct pwc_snapshot *pwc_create_snapshot(void);
void pwc_snapshot_destroy(struct pwc_snapshot *snapshot);

#ifdef __cplusplus
}
#endif

#endif
