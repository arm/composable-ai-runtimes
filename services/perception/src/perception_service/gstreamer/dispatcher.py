# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from concurrent.futures import Future, wait

from perception_service.gstreamer.errors import DispatcherUnavailableError


def wait_for_command[T](
    completion: Future[T],
    operation: str,
    command_queue_timeout_seconds: float,
) -> T:
    done, _ = wait(
        (completion,),
        timeout=command_queue_timeout_seconds,
    )
    if done:
        return completion.result()

    if completion.cancel():
        raise DispatcherUnavailableError(
            f"timed out before the task dispatcher could {operation}"
        )

    return completion.result()
