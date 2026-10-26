// SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: Apache-2.0

// Discover and mount unchanged upstream layers. Emit the image and existing layer digests as JSON.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/opencontainers/go-digest"
	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
	"oras.land/oras-go/v2/content/oci"
	"oras.land/oras-go/v2/registry/remote"
	"oras.land/oras-go/v2/registry/remote/auth"
	"oras.land/oras-go/v2/registry/remote/credentials"
)

type existingLayerInfo struct {
	ImageDigest          string          `json:"image_digest"`
	ExistingLayerDigests []digest.Digest `json:"existing_layer_digests"`
}

type options struct {
	layerSourceMetadata   string
	ociLayoutDir          string
	destinationRepository string
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func parseArgs(args []string) (options, error) {
	var opts options
	flags := flag.NewFlagSet("existing-layer-mounting", flag.ContinueOnError)
	flags.StringVar(&opts.layerSourceMetadata, "layer-source-metadata", "", "Image digest and build inputs extracted from Buildx metadata")
	flags.StringVar(&opts.ociLayoutDir, "oci-layout-dir", "", "Exported OCI image layout directory")
	flags.StringVar(&opts.destinationRepository, "destination-repository", "", "Registry/repository without a tag")
	if err := flags.Parse(args); err != nil {
		return options{}, err
	}
	if opts.layerSourceMetadata == "" || opts.ociLayoutDir == "" || opts.destinationRepository == "" || flags.NArg() != 0 {
		return options{}, errors.New("supply layer source metadata, OCI layout directory, and destination repository")
	}
	return opts, nil
}

func run(args []string) error {
	opts, err := parseArgs(args)
	if err != nil {
		return err
	}
	targetPlatform := ocispec.Platform{OS: "linux", Architecture: "arm64"}
	imageInfo, err := readImageInfo(opts.layerSourceMetadata, targetPlatform)
	if err != nil {
		return err
	}
	ctx := context.Background()
	ociStore, err := openOCIStore(ctx, opts.ociLayoutDir, imageInfo.OutputImageDigest)
	if err != nil {
		return err
	}
	outputLayers, err := fetchLayerInfo(ctx, ociStore, imageInfo.OutputImageDigest, targetPlatform)
	if err != nil {
		return err
	}
	// Reuse the existing Docker login.
	store, err := credentials.NewStoreFromDocker(credentials.StoreOptions{})
	if err != nil {
		return err
	}
	registryClient := &auth.Client{
		Client:     &http.Client{Timeout: time.Minute},
		Cache:      auth.NewCache(),
		Credential: credentials.Credential(store),
	}
	destinationRepository, err := remote.NewRepository(opts.destinationRepository)
	if err != nil {
		return err
	}
	if destinationRepository.Reference.Reference != "" {
		return errors.New("supply a destination repository only (no tag or digest)")
	}
	destinationRepository.Client = registryClient
	repositoriesByLayer, err := findLayerRepositories(ctx, imageInfo.SourceImageRefs, outputLayers, targetPlatform, registryClient)
	if err != nil {
		return err
	}
	existingLayerDigests := []digest.Digest{}
	for _, layer := range outputLayers {
		sourceRepositories := repositoriesByLayer[layer.Digest]
		if len(sourceRepositories) == 0 {
			continue
		}
		exists, err := destinationRepository.Blobs().Exists(ctx, layer)
		if err != nil {
			return fmt.Errorf("check %s: %w", layer.Digest, err)
		}
		if exists {
			fmt.Fprintln(os.Stderr, "Exists", layer.Digest)
		} else if err := linkLayer(ctx, destinationRepository, sourceRepositories, layer); err != nil {
			return err
		}
		existingLayerDigests = append(existingLayerDigests, layer.Digest)
		delete(repositoriesByLayer, layer.Digest)
	}
	return json.NewEncoder(os.Stdout).Encode(existingLayerInfo{
		ImageDigest: imageInfo.OutputImageDigest, ExistingLayerDigests: existingLayerDigests,
	})
}

// Open the read-only OCI store after confirming it contains the expected output image.
func openOCIStore(ctx context.Context, directory, imageDigest string) (*oci.ReadOnlyStore, error) {
	data, err := os.ReadFile(filepath.Join(directory, ocispec.ImageIndexFile))
	if err != nil {
		return nil, err
	}
	var index ocispec.Index
	if err := json.Unmarshal(data, &index); err != nil {
		return nil, err
	}
	for _, root := range index.Manifests {
		if root.Digest.String() == imageDigest {
			return oci.NewFromFS(ctx, os.DirFS(directory))
		}
	}
	return nil, fmt.Errorf("image %s is not a root in OCI layout %s", imageDigest, directory)
}
