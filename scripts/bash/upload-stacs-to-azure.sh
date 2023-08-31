#!/bin/bash
az storage blob upload-batch --account-name coclico --source ./current --destination stac/v1\n
