#!/bin/bash

for file in generate_stac_0?.py; do
    echo "RUN python $file"
    echo "Building STACs..."
    python $file
done
