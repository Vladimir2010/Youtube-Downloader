#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Download and Extract FFmpeg static binary if not present
if [ ! -d "ffmpeg" ]; then
  echo "Downloading FFmpeg..."
  mkdir -p ffmpeg
  # Download static build for Linux (Render runs on Linux)
  curl -L https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-linux-64.zip -o ffmpeg.zip
  unzip ffmpeg.zip -d ffmpeg
  rm ffmpeg.zip
  chmod +x ffmpeg/ffmpeg
fi
