### Parameters

1. Require the user to expose a config file
2. Precedence: CLI > ENV > config passed > default config exposed
3. The user should not expose default values in their scripts - everything passes through the config file
4. For parameter hashing: resolve the config file after precedence, canonicalize (ignore any non-process-specific settings), sort, hash
5. On run end, store a resolved human-readible config.lock file with the passed parameters from all sources for future reproduction (only process specific entries)
6. Also store the canonicalized form as .json for later automated queries

How to normalize:
- control types: fall back to native so: string-like (Path) -> str, np.int64 -> int, np.float64 -> float, etc.
- transform dict to json.dumps
- sort by keys
- no whitespaces
- hash




