#!/bin/bash

# for file in "generate_stac_??.py"; do
#     echo "RUN python $file"
#     echo "Building STACs..."
#     python $file
#     echo "Done!"
# done

for file in generate_stac_??.py; do
    echo "RUN python $file"
    echo "Building STACs..."
    python $file
done
