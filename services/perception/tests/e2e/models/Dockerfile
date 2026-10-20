# syntax=docker/dockerfile:1
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

FROM docker.io/library/python:3.13.15-slim-trixie@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0

ARG OPK_REVISION=3f8a57f6c41a5549c8b8fb3fd7dacea084b0acfb
ARG MODEL_REVISION=de7e3b272d58269278b23a33cb6517be860ca2c3

WORKDIR /model-package/yolo26n-320

ADD --checksum=sha256:2d86d77a6583991875e818ac0710d518be774adb1c413d40f93b81b5f68eda2b --chmod=644 \
    https://huggingface.co/Arm/yolo26n-320-int8-onnx-raspberrypi5/resolve/${MODEL_REVISION}/arm/opk/model.json model.json
ADD --checksum=sha256:aca2e5b2a2f6386d544aad887be1a40ffbbe7f654853db0f6e41265540a7f04a --chmod=644 \
    https://huggingface.co/Arm/yolo26n-320-int8-onnx-raspberrypi5/resolve/${MODEL_REVISION}/arm/opk/opchain.json opchain.json
ADD --checksum=sha256:a64a843197d4e7697c2d834d610fba88a7ebd81a62f39d1270ea7ad1aed687fc --chmod=644 \
    https://huggingface.co/Arm/yolo26n-320-int8-onnx-raspberrypi5/resolve/${MODEL_REVISION}/yolo26n_raspberry_onnx_optimized.onnx yolo26n_raspberry_onnx_optimized.onnx

WORKDIR /model-package/byom-blazeface

ADD --checksum=sha256:54b9172b0469c762c05e4e5ae54f9fefe9f28d04ba5e9ce7f2ef7e389bdd6eda --chmod=644 \
    https://raw.githubusercontent.com/arm/open-perception-kit/${OPK_REVISION}/LICENSE LICENSE
ADD --checksum=sha256:6219e2b8c1e0dd5c605ffe0fc4bada2920f4798114e85098f8bf5f038ccf636a --chmod=644 \
    https://raw.githubusercontent.com/arm/open-perception-kit/${OPK_REVISION}/NOTICE NOTICE
ADD --checksum=sha256:3b642ff39c7cd966c15546f6f896ccdfd456a86f4fca41c89cabc2a2b2bde7e8 --chmod=644 \
    https://raw.githubusercontent.com/arm/open-perception-kit/${OPK_REVISION}/development/examples/byom-blazeface/model.json model.json
ADD --checksum=sha256:8b0335957234809e599b0b8c051df0b1218a67fbf007d093e02b125dde9a693c --chmod=644 \
    https://raw.githubusercontent.com/arm/open-perception-kit/${OPK_REVISION}/development/examples/byom-blazeface/opchain.json opchain.json
ADD --checksum=sha256:547e4e235d60cb7e17fd3712df79adc48bd4eb5a8d031962a4ca019ca14dcd1c --chmod=644 \
    https://raw.githubusercontent.com/arm/open-perception-kit/${OPK_REVISION}/development/examples/byom-blazeface/postprocess.py postprocess.py
ADD --checksum=sha256:02a04d5d37c3558dc4d5274f7f8f0f0f01ac94e46c5ffb2cee82395d47e23181 --chmod=644 \
    https://huggingface.co/fernandotonon/QtMeshEditor-blazeface-onnx/resolve/50f2c66ffbdf84beae8c267df2b49e5c5a5162e9/face_detector.onnx face_detector.onnx

WORKDIR /models

ENTRYPOINT ["cp", "-a", "/model-package/.", "/models/"]
