// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/opencontainers/go-digest"
	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
	"oras.land/oras-go/v2"
	"oras.land/oras-go/v2/registry"
	"oras.land/oras-go/v2/registry/remote"
	"oras.land/oras-go/v2/registry/remote/auth"
)

func fetchLayerInfo(ctx context.Context, imageSource oras.ReadOnlyTarget, reference string, targetPlatform ocispec.Platform) ([]ocispec.Descriptor, error) {
	_, data, err := oras.FetchBytes(ctx, imageSource, reference, oras.FetchBytesOptions{
		FetchOptions: oras.FetchOptions{ResolveOptions: oras.ResolveOptions{TargetPlatform: &targetPlatform}},
	})
	if err != nil {
		return nil, err
	}
	var manifest ocispec.Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return nil, err
	}
	if manifest.Layers == nil {
		return nil, fmt.Errorf("image manifest %s is missing its layers array", reference)
	}
	return manifest.Layers, nil
}

type sourceImageLayers struct {
	Repository registry.Reference
	Layers     []ocispec.Descriptor
}

func findLayerRepositories(
	ctx context.Context,
	sourceImageRefs []string,
	outputLayers []ocispec.Descriptor,
	targetPlatform ocispec.Platform,
	registryClient *auth.Client,
) (map[digest.Digest][]registry.Reference, error) {
	var sourceImages []sourceImageLayers
	for _, imageRef := range sourceImageRefs {
		source, err := remote.NewRepository(imageRef)
		if err != nil {
			return nil, err
		}
		source.Client = registryClient
		layers, err := fetchLayerInfo(ctx, source, source.Reference.Reference, targetPlatform)
		if err != nil {
			return nil, fmt.Errorf("read source image %s: %w", imageRef, err)
		}
		sourceImages = append(sourceImages, sourceImageLayers{
			Repository: source.Reference,
			Layers:     layers,
		})
	}
	return matchLayerSources(outputLayers, sourceImages), nil
}

func matchLayerSources(
	outputLayers []ocispec.Descriptor,
	sourceImages []sourceImageLayers,
) map[digest.Digest][]registry.Reference {
	repositoriesByLayer := make(map[digest.Digest][]registry.Reference)
	for _, layer := range outputLayers {
		repositoriesByLayer[layer.Digest] = nil
	}
	for _, image := range sourceImages {
		for _, layer := range image.Layers {
			if _, inOutput := repositoriesByLayer[layer.Digest]; inOutput {
				repositoriesByLayer[layer.Digest] = append(repositoriesByLayer[layer.Digest], image.Repository)
			}
		}
	}
	return repositoriesByLayer
}

// Link an existing layer into the destination repository using a registry blob mount.
// Try matching same-registry sources in order, without falling back to uploading.
// See: https://distribution.github.io/distribution/spec/api/#cross-repository-blob-mount
func linkLayer(ctx context.Context, destinationRepository *remote.Repository, sourceRepositories []registry.Reference, layer ocispec.Descriptor) error {
	var mountErrors []error
	for _, sourceRepository := range sourceRepositories {
		if err := ctx.Err(); err != nil {
			return err
		}
		if sourceRepository.Registry != destinationRepository.Reference.Registry {
			continue
		}
		err := destinationRepository.Mount(ctx, layer, sourceRepository.Repository,
			func() (io.ReadCloser, error) {
				return nil, errors.New("mounting layer failed; refusing to upload it")
			})
		if err != nil {
			if contextError := ctx.Err(); contextError != nil {
				return contextError
			}
			mountErrors = append(mountErrors, fmt.Errorf("mount %s from %s: %w", layer.Digest, sourceRepository.Repository, err))
			continue
		}
		fmt.Fprintln(os.Stderr, "Mounted", layer.Digest, "from", sourceRepository.Repository)
		return nil
	}
	if len(mountErrors) > 0 {
		return errors.Join(mountErrors...)
	}
	return fmt.Errorf("no same-registry source for upstream layer %s", layer.Digest)
}
