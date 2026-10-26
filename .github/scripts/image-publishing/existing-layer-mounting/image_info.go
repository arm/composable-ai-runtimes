// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"

	"github.com/containerd/platforms"
	"github.com/moby/buildkit/util/purl"
	"github.com/opencontainers/go-digest"
	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
)

type buildInput struct {
	URI    string            `json:"uri"`
	Digest map[string]string `json:"digest"`
}

type imageMetadata struct {
	ImageDigest string       `json:"image_digest"`
	BuildInputs []buildInput `json:"materials"`
}

type imageInfo struct {
	OutputImageDigest string
	SourceImageRefs   []string
}

func readImageInfo(metadataFile string, targetPlatform ocispec.Platform) (imageInfo, error) {
	data, err := os.ReadFile(metadataFile)
	if err != nil {
		return imageInfo{}, err
	}
	var metadata imageMetadata
	if err := json.Unmarshal(data, &metadata); err != nil {
		return imageInfo{}, err
	}
	if _, err := digest.Parse(metadata.ImageDigest); err != nil {
		return imageInfo{}, fmt.Errorf("invalid output image digest: %w", err)
	}
	if metadata.BuildInputs == nil {
		return imageInfo{}, fmt.Errorf("missing materials array in %s; use [] for a build with no inputs", metadataFile)
	}
	imageRefs, err := resolveSourceImageRefs(metadata.BuildInputs, targetPlatform)
	if err != nil {
		return imageInfo{}, err
	}
	return imageInfo{OutputImageDigest: metadata.ImageDigest, SourceImageRefs: imageRefs}, nil
}

// Build input:
// pkg:docker/redis@8.4?platform=linux%2Farm64
// Recorded digest: abc123…
//
// Result:
// docker.io/library/redis:8.4@sha256:abc123…
func resolveSourceImageRefs(buildInputs []buildInput, targetPlatform ocispec.Platform) ([]string, error) {
	var imageRefs []string
	for _, input := range buildInputs {
		if input.URI == "" {
			return nil, errors.New("build input is missing its URI")
		}
		// BuildKit records registry images as pkg:docker and local image sources as
		// pkg:oci. Local images do not identify a registry repository for mounting.
		// Ignore other inputs, such as Git and HTTP sources; content they contribute
		// is our responsibility when publishing.
		if strings.HasPrefix(input.URI, "pkg:oci/") {
			return nil, fmt.Errorf("unsupported local image input %s: use a registry image so upstream layers can be mounted", input.URI)
		}
		if !strings.HasPrefix(input.URI, "pkg:docker/") {
			continue
		}
		imageRef, inputPlatform, err := purl.PURLToRef(input.URI)
		if err != nil {
			return nil, err
		}
		if inputPlatform != nil && !platforms.OnlyStrict(targetPlatform).Match(*inputPlatform) {
			continue
		}
		pinnedDigest, err := digest.Parse("sha256:" + input.Digest["sha256"])
		if err != nil {
			return nil, fmt.Errorf("invalid recorded digest for %s: %w", input.URI, err)
		}
		imageName, uriDigest, pinned := strings.Cut(imageRef, "@")
		if pinned && uriDigest != pinnedDigest.String() {
			return nil, fmt.Errorf("conflicting recorded digests for %s", input.URI)
		}
		imageRefs = append(imageRefs, imageName+"@"+pinnedDigest.String())
	}
	return imageRefs, nil
}
