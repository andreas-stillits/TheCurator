### Reproducibility of the data that created an artifact

1. hash according to their contents
2. if multiple files, organize in sorted pairs [(name, content_hash), (name, content_hash), ...]
3. stream this canonical list to create a deterministic overall hash

outputs similarly obtain their name from a hash of their contents - easy to check if two outputs are identical.