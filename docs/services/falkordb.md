# FalkorDB service

## Project
- URL: `https://github.com/FalkorDB/FalkorDB`
- Description: In-memory graph database optimized for fast graph traversal and graph querying.

## Compose
- File: `compose/main/40-falkordb.yml`
- Service name: `falkordb`
- Image: `falkordb/falkordb:${FALKORDB_VERSION:-v4.18.9}`

## Ports
- `6379:6379`
- `3000:3000` (browser UI)

## Storage
- Named volume: `falkordb-data`

## Make targets
- `make up-falkordb`
- `make logs-falkordb`
- `make restart-falkordb`
- `make down-falkor`

## Notes
- Runs on dedicated `falkordb-network`.
- Includes healthcheck used by downstream services.
