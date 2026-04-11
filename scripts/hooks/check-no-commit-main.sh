#!/bin/sh
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" = "main" ]; then
	echo "Direct commits to main are not allowed. Use a branch and a PR."
	exit 1
fi
