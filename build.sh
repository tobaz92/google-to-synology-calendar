#!/bin/bash
# Build l'image Docker sur le NAS Synology (à lancer en SSH une seule fois)
# Usage : ssh admin@NAS "cd /volume1/docker/google-to-synology && bash build.sh"

set -e

IMAGE_NAME="google-to-synology-sync:latest"

echo "Construction de l'image $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" .

echo "Image construite avec succès."
echo "Redémarrer le projet via Container Manager ou :"
echo "  docker compose down && docker compose up -d"
