### Reproducibility of the code that created an artifact.


Because it is difficult to judge if code changes are consequential and we need to be able to recover code:
1. require repo to be git tracked - if not display a warning!
2. let code hash be the git commit hash. Any change to your repo will then trigger a cache-miss (if you freeze your repo - no cache misses)
3. create a new artifact
4. immediately clean up:
    1. collect all artifacts of that process (by_process view) with idential: inputs, params, env, outputs (hashes)
       *clearly some code changes were made but not significant for data*
    2. only keep the latest one (by time stamp), delete the rest
