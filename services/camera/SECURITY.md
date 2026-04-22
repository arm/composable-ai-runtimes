# Camera Service Security Notes

## Intro

While the runtime user of the container is not root, the runtime deployment still grants it some host level privileges such as scheduling and device access. This is required in order for PipeWire, WirePlumber, libcamera, and udev-backed hotplug detection work reliably on the current Raspberry Pi target.

One small hardening step is already in place: the device cgroup rule no longer grants `mknod`, so the container cannot create new device nodes through the current broad rule.

## Security Areas

### `/dev` bind mount

Mounting `/dev` from the host exposes the full host device tree inside the container, not just the camera-related nodes needed for capture. This is required to allow the service to access all potentially plugged cameras.

#### Impact

- The service can reach device nodes unrelated to camera capture.
- A compromise in the media stack may expand into other host-facing device interfaces.
- This is no different to us running the service outside the container, therefore it is an acceptable risk.

#### Potential mitigations

- Replace the full `/dev` bind mount with explicit device mappings for only the required camera, media, and supporting nodes. This could be difficult, as we want the service to access any camera plugged in, and thus exposed as any node name under `/dev/`
- Tighten the access with cgroup rules.

### Broad character-device rule

`device_cgroup_rules: "c *:* rw"` permits read and write access to all character devices that are visible in the container.

#### Impact

- Isolation is much weaker than a narrow allowlist of camera devices.
- The container can interact with character devices beyond the intended V4L2 and media-controller path.

#### Potential mitigations

- Replace the broad rule with explicit character-device allowlists for the specific major/minor combinations the service needs.
- Keep `mknod` disallowed unless a concrete runtime need appears.

### Video group membership

Adding the container to the host `video` group increases access to V4L2 and DRM nodes that rely on group permissions.

#### Impact

- Access extends beyond a single camera device.
- DRM and related graphics interfaces may become reachable in addition to camera nodes.

#### Potential mitigations

- Check whether direct device ownership, ACLs, or narrower group-based permissions can replace broad `video` group membership.

### Udev state exposure

Mounting `/run/udev` read-only exposes host device inventory and hotplug metadata.

#### Impact

- The service can inspect host hardware presence and device events.
- A compromised process gains more visibility into the host hardware layout.

#### Potential mitigations

- Confirm whether the service needs the full `/run/udev` tree or only a narrower subset of device metadata.
- Replace the mount with a smaller bind mount if the required files can be identified precisely.
- If hotplug support can be handled outside the container, remove the mount and pass only the specific signals or configuration the service needs.

### Host networking

`network_mode: host` removes network namespace isolation.

#### Impact

- The service can reach host-network services that would not be reachable from an isolated bridge network.
- Network attack surface is closer to a native host process than a strongly isolated container.

#### Potential mitigations

- Re-evaluate whether host networking is still required for the current hotplug and media workflow.
- Move to a bridged network and publish only the ports that are actually needed if host networking is not strictly necessary.
- Add host-level firewall rules or service binding restrictions so the container cannot freely reach unrelated local services.

### Shared PipeWire socket permissions

The entrypoint changes the PipeWire socket to mode `666` so non-root client containers can connect through the shared runtime volume.

#### Impact

- Any process with access to the shared runtime volume can connect to the PipeWire instance.
- A compromised peer container may be able to inspect or interfere with media graph state through the shared socket.
- The socket permission is broader than a model based on a dedicated group or explicit trusted peers.

#### Potential mitigations

- Replace world-writable socket permissions with a dedicated shared group if the client set is known.
- Restrict which containers receive the shared runtime volume.
- Revisit whether all consumers need direct PipeWire socket access or whether some can use a narrower service API instead.

### Realtime scheduling privileges

`CAP_SYS_NICE`, `rtprio`, `memlock`, and the `cap_sys_nice` file capability on PipeWire and WirePlumber are required for media performance, but they still increase the impact of compromise.

#### Impact

- A compromised process may be able to abuse scheduling priority or locked memory.
- Misuse can degrade host responsiveness or create denial-of-service conditions.

#### Potential mitigations

- Confirm the minimum realtime settings needed for acceptable camera performance and lower `rtprio`, `memlock`, or capability scope where possible.
- Keep `CAP_SYS_NICE` and related file capabilities limited to the specific binaries that require them.
- Add operational monitoring for scheduling abuse, resource starvation, or repeated startup failures so privilege misuse is more visible.

## Risk Model Guidance

For now, treat the camera service as a trusted, host-adjacent workload rather than a tightly sandboxed container.

If the camera process, PipeWire, WirePlumber, libcamera, or related dependencies are compromised, the attacker may be able to:

- Access unrelated character devices exposed through `/dev`
- Interact with DRM, V4L2, media-controller, and DMA-BUF interfaces beyond the intended camera path
- Observe host device inventory and hotplug state
- Reach services on the host network stack
- Query the camera gRPC API without authentication if network reachability exists
- Connect to the shared PipeWire socket if they can access the runtime volume
- Cause local denial-of-service through device misuse or realtime scheduling abuse

This does not automatically imply full host compromise, but it does mean the service should not be modeled as having strong container isolation.

## Hardening Priorities

If stronger isolation becomes necessary, the first hardening steps should be:

1. Replace `c *:* rw` with explicit device cgroup allowlists.
2. Re-evaluate whether host networking is still required for hotplug behavior.
3. Narrow access to the gRPC endpoint and shared PipeWire socket to trusted peers only.
4. Keep only the minimum capability set needed for realtime media operation.
5. Document every privileged mount, device, capability, group membership, and exposed interface with its operational justification.
