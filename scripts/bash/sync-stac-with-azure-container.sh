#!/bin/bash
az storage blob sync --account-name coclico --source ./current --container stac/v1
